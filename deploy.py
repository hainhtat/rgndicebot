#!/usr/bin/env python3
"""
Deployment script for Render.com

This script ensures the database is properly migrated before starting the bot.
Run this script on Render instead of main.py for automatic migration.

Usage on Render:
1. Set the start command to: python3 deploy.py
2. Or run manually: python3 deploy.py
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_deployment():
    """
    Run the deployment process:
    1. Check environment
    2. Run database migration
    3. Start the bot
    """
    logger.info("🚀 Starting deployment process...")
    
    # Check if we're using database
    use_database = os.getenv('USE_DATABASE', 'true').lower() == 'true'
    
    if not use_database:
        logger.info("Database not enabled, skipping migration")
    else:
        logger.info("Database enabled, running migration check...")
        
        try:
            # Import and run migration
            from render_migration import run_migration
            run_migration()
            logger.info("✅ Migration completed successfully")
        except ImportError:
            logger.warning("Migration script not found, continuing without migration")
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            # Don't exit - let the bot try to start anyway
            logger.info("Continuing with bot startup despite migration failure")
    
    # Start the main bot
    logger.info("🤖 Starting Telegram bot...")
    try:
        from main import main
        main()
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_deployment()