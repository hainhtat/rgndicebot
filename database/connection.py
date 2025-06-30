"""Database connection management for PostgreSQL."""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# Create the declarative base
Base = declarative_base()

# Global variables for database connection
engine = None
SessionLocal = None

def get_database_url():
    """Get database URL from environment variables."""
    # Try DATABASE_URL first (for production/Render)
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Handle postgres:// vs postgresql:// URL schemes
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url
    
    # Fallback to individual components (for local development)
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME', 'dicebot_db')
    user = os.getenv('DB_USER', 'dicebot_user')
    password = os.getenv('DB_PASSWORD', '')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"

def init_database():
    """Initialize database connection and create tables."""
    global engine, SessionLocal
    
    try:
        database_url = get_database_url()
        logger.info(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
        
        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False  # Set to True for SQL debugging
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Import models to register them with Base
        from . import models
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        return False

@contextmanager
def get_db_session():
    """Get a database session with automatic cleanup."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()

def get_engine():
    """Get the database engine."""
    return engine

def close_database():
    """Close database connections."""
    global engine
    if engine:
        engine.dispose()
        logger.info("Database connections closed")