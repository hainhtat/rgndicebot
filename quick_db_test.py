#!/usr/bin/env python3
"""
Quick test for database connection and basic operations.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database.connection import init_database, get_db_session
    from database.adapter import DatabaseAdapter
    print("✅ Imports successful")
    
    # Test database initialization
    print("Testing database initialization...")
    success = init_database()
    if success:
        print("✅ Database initialized successfully")
    else:
        print("❌ Database initialization failed")
        sys.exit(1)
    
    # Test basic session
    print("Testing database session...")
    from sqlalchemy import text
    with get_db_session() as session:
        result = session.execute(text("SELECT 1 as test")).fetchone()
        print(f"✅ Database query successful: {result}")
    
    # Test adapter
    print("Testing database adapter...")
    adapter = DatabaseAdapter()
    test_user_id = 123456789
    test_chat_id = -987654321
    
    stats = adapter.get_or_create_player_stats(test_user_id, test_chat_id, "TestUser")
    print(f"✅ Player stats: {stats}")
    
    print("🎉 All basic database tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)