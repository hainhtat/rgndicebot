#!/usr/bin/env python3
"""
Environment Check Script for Render Deployment

This script helps diagnose environment and database connection issues.
Run this on Render to check if all required environment variables are set.

Usage:
python3 check_env.py
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_environment():
    """
    Check all required environment variables and database connectivity.
    """
    print("🔍 Environment Check for Dice Bot")
    print("=" * 50)
    
    # Required environment variables
    required_vars = [
        'BOT_TOKEN',
        'DATABASE_URL',
        'USE_DATABASE'
    ]
    
    optional_vars = [
        'TIMEZONE',
        'SUPER_ADMINS',
        'ALLOWED_GROUP_IDS'
    ]
    
    print("\n📋 Required Environment Variables:")
    missing_required = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'TOKEN' in var or 'URL' in var:
                masked_value = value[:10] + "..." + value[-10:] if len(value) > 20 else "***"
                print(f"  ✅ {var}: {masked_value}")
            else:
                print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: NOT SET")
            missing_required.append(var)
    
    print("\n📋 Optional Environment Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚠️  {var}: NOT SET (using default)")
    
    # Check database connectivity if DATABASE_URL is set
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        print("\n🗄️  Database Connectivity Check:")
        try:
            import psycopg
            from urllib.parse import urlparse
            
            # Parse database URL
            parsed = urlparse(database_url)
            
            print(f"  📍 Host: {parsed.hostname}")
            print(f"  📍 Port: {parsed.port or 5432}")
            print(f"  📍 Database: {parsed.path[1:] if parsed.path else 'N/A'}")
            print(f"  📍 Username: {parsed.username}")
            
            # Test connection
            conn = psycopg.connect(conninfo=database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"  ✅ Connection successful")
            print(f"  📊 PostgreSQL version: {version}")
            
            # Check if users table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                );
            """)
            users_table_exists = cursor.fetchone()[0]
            print(f"  📋 Users table exists: {'✅ Yes' if users_table_exists else '❌ No'}")
            
            if users_table_exists:
                # Check for required columns
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name IN ('bonus_points', 'welcome_bonuses_received')
                    ORDER BY column_name;
                """)
                existing_columns = [row[0] for row in cursor.fetchall()]
                
                required_columns = ['bonus_points', 'welcome_bonuses_received']
                for col in required_columns:
                    if col in existing_columns:
                        print(f"  ✅ Column '{col}' exists")
                    else:
                        print(f"  ❌ Column '{col}' missing - MIGRATION NEEDED")
            
            cursor.close()
            conn.close()
            
        except ImportError:
            print("  ❌ psycopg2 not installed")
        except Exception as e:
            print(f"  ❌ Database connection failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    if missing_required:
        print(f"❌ DEPLOYMENT WILL FAIL - Missing required variables: {', '.join(missing_required)}")
        return False
    else:
        print("✅ Environment check passed - Ready for deployment")
        return True

if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)