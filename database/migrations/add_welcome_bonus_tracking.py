#!/usr/bin/env python3
"""
Database migration script to add welcome bonus tracking columns to User model.
This migration adds:
- bonus_points: Integer column to track user bonus points
- welcome_bonuses_received: JSON column to track welcome bonuses per chat

Run this script after updating the User model to add the new columns.
"""

import logging
from sqlalchemy import text
from database.connection import get_db_session, init_database
from database.models import User

logger = logging.getLogger(__name__)

def migrate_add_welcome_bonus_tracking():
    """Add welcome bonus tracking columns to User table."""
    try:
        # Initialize database first
        init_database()
        
        with get_db_session() as session:
            # Check if columns already exist
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('bonus_points', 'welcome_bonuses_received')
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            
            # Add bonus_points column if it doesn't exist
            if 'bonus_points' not in existing_columns:
                logger.info("Adding bonus_points column to users table...")
                session.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN bonus_points INTEGER DEFAULT 0
                """))
                logger.info("bonus_points column added successfully")
            else:
                logger.info("bonus_points column already exists")
            
            # Add welcome_bonuses_received column if it doesn't exist
            if 'welcome_bonuses_received' not in existing_columns:
                logger.info("Adding welcome_bonuses_received column to users table...")
                session.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN welcome_bonuses_received JSON DEFAULT '{}'
                """))
                logger.info("welcome_bonuses_received column added successfully")
            else:
                logger.info("welcome_bonuses_received column already exists")
            
            session.commit()
            logger.info("Welcome bonus tracking migration completed successfully")
            
    except Exception as e:
        logger.error(f"Error during welcome bonus tracking migration: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_add_welcome_bonus_tracking()