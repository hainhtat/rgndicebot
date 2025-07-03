#!/usr/bin/env python3
"""
Render Database Migration Script
This script adds missing columns to the production database on Render.

Run this script on Render to fix the missing bonus_points and welcome_bonuses_received columns.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

@contextmanager
def get_db_session():
    """Get a database session with automatic cleanup."""
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
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
        engine.dispose()

def check_and_add_columns():
    """Check for missing columns and add them if necessary."""
    try:
        with get_db_session() as session:
            logger.info("Checking for missing columns in users table...")
            
            # Check if columns already exist
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('bonus_points', 'welcome_bonuses_received')
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Existing columns: {existing_columns}")
            
            # Add bonus_points column if it doesn't exist
            if 'bonus_points' not in existing_columns:
                logger.info("Adding bonus_points column to users table...")
                session.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN bonus_points INTEGER DEFAULT 0
                """))
                logger.info("✅ bonus_points column added successfully")
            else:
                logger.info("✅ bonus_points column already exists")
            
            # Add welcome_bonuses_received column if it doesn't exist
            if 'welcome_bonuses_received' not in existing_columns:
                logger.info("Adding welcome_bonuses_received column to users table...")
                session.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN welcome_bonuses_received JSON DEFAULT '{}'
                """))
                logger.info("✅ welcome_bonuses_received column added successfully")
            else:
                logger.info("✅ welcome_bonuses_received column already exists")
            
            # Verify the columns were added
            result = session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('bonus_points', 'welcome_bonuses_received')
                ORDER BY column_name
            """))
            
            logger.info("\n=== Column Verification ===")
            for row in result.fetchall():
                logger.info(f"Column: {row[0]}, Type: {row[1]}, Default: {row[2]}")
            
            logger.info("\n🎉 Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Error during migration: {e}")
        raise

def main():
    """Main migration function."""
    logger.info("=== Render Database Migration Started ===")
    logger.info(f"Database URL: {get_database_url().split('@')[1] if '@' in get_database_url() else 'local'}")
    
    try:
        check_and_add_columns()
        logger.info("=== Migration Completed Successfully ===")
        return True
    except Exception as e:
        logger.error(f"=== Migration Failed: {e} ===")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)