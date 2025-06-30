#!/usr/bin/env python3
"""Migration script to transfer data from JSON to PostgreSQL."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.migrations import DataMigration
from utils.logging_utils import get_logger
from config.settings import USE_DATABASE, DATA_FILE_PATH

logger = get_logger(__name__)

def main():
    """Main migration function."""
    print("🔄 DiceBot Data Migration Tool")
    print("=" * 40)
    
    # Check if database is enabled
    if not USE_DATABASE:
        print("❌ Database is not enabled in settings.")
        print("Please set USE_DATABASE=true in your .env file or environment variables.")
        return False
    
    # Check if JSON data file exists
    if not os.path.exists(DATA_FILE_PATH):
        print(f"❌ JSON data file not found: {DATA_FILE_PATH}")
        print("Nothing to migrate.")
        return False
    
    # Check database connection
    try:
        from database.connection import init_database
        if not init_database():
            print("❌ Failed to connect to PostgreSQL database.")
            print("Please check your database configuration.")
            return False
        print("✅ Database connection successful.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    # Confirm migration
    print(f"\n📁 Found JSON data file: {DATA_FILE_PATH}")
    response = input("\n⚠️  This will migrate your JSON data to PostgreSQL. Continue? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("Migration cancelled.")
        return False
    
    # Run migration
    try:
        migration = DataMigration()
        print("\n🚀 Starting migration...")
        
        success = migration.run_migration()
        
        if success:
            print("\n✅ Migration completed successfully!")
            print("\n📋 Summary:")
            print(f"   • Users migrated: {migration.stats.get('users', 0)}")
            print(f"   • Chats migrated: {migration.stats.get('chats', 0)}")
            print(f"   • Player stats migrated: {migration.stats.get('player_stats', 0)}")
            print(f"   • Games migrated: {migration.stats.get('games', 0)}")
            print(f"   • Admin data migrated: {migration.stats.get('admin_data', 0)}")
            
            print("\n🔧 Next steps:")
            print("   1. Test your bot to ensure everything works correctly")
            print("   2. If satisfied, you can delete the JSON backup file")
            print(f"   3. Your original data is backed up as: {DATA_FILE_PATH}.backup")
            
            return True
        else:
            print("\n❌ Migration failed. Check the logs for details.")
            return False
            
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)