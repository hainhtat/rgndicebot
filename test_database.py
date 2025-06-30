#!/usr/bin/env python3
"""Test script to verify database setup and functionality."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.adapter import db_adapter
from utils.logging_utils import get_logger
from config.settings import USE_DATABASE

logger = get_logger(__name__)

def test_database_connection():
    """Test basic database connectivity."""
    print("🔍 Testing Database Connection")
    print("=" * 40)
    
    print(f"Database mode: {'PostgreSQL' if USE_DATABASE else 'JSON'}")
    
    if USE_DATABASE:
        try:
            from database.connection import init_database
            if init_database():
                print("✅ Database connection successful")
                return True
            else:
                print("❌ Database connection failed")
                return False
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
    else:
        print("✅ JSON mode - no database connection needed")
        return True

def test_adapter_operations():
    """Test basic adapter operations."""
    print("\n🧪 Testing Adapter Operations")
    print("=" * 40)
    
    test_user_id = 12345
    test_chat_id = -67890
    
    try:
        # Test user operations
        print("Testing user operations...")
        initial_points = db_adapter.get_user_referral_points(test_user_id)
        print(f"  Initial referral points: {initial_points}")
        
        db_adapter.update_user_referral_points(test_user_id, 100)
        updated_points = db_adapter.get_user_referral_points(test_user_id)
        print(f"  Updated referral points: {updated_points}")
        
        # Test player stats
        print("\nTesting player stats...")
        initial_score = db_adapter.get_player_score(test_user_id, test_chat_id)
        print(f"  Initial score: {initial_score}")
        
        db_adapter.update_player_stats(test_user_id, test_chat_id, 50, True, 10)
        updated_score = db_adapter.get_player_score(test_user_id, test_chat_id)
        print(f"  Updated score: {updated_score}")
        
        # Test chat operations
        print("\nTesting chat operations...")
        match_counter = db_adapter.get_chat_match_counter(test_chat_id)
        print(f"  Current match counter: {match_counter}")
        
        new_counter = db_adapter.increment_chat_match_counter(test_chat_id)
        print(f"  New match counter: {new_counter}")
        
        # Test leaderboard
        print("\nTesting leaderboard...")
        leaderboard = db_adapter.get_chat_leaderboard(test_chat_id, 5)
        print(f"  Leaderboard entries: {len(leaderboard)}")
        for i, entry in enumerate(leaderboard[:3], 1):
            print(f"    {i}. User {entry['user_id']}: {entry['score']} points")
        
        # Test admin operations
        print("\nTesting admin operations...")
        admin_points = db_adapter.get_admin_points(test_user_id, test_chat_id)
        print(f"  Admin points: {admin_points}")
        
        db_adapter.update_admin_points(test_user_id, test_chat_id, 500)
        updated_admin_points = db_adapter.get_admin_points(test_user_id, test_chat_id)
        print(f"  Updated admin points: {updated_admin_points}")
        
        print("\n✅ All adapter operations completed successfully")
        return True
        
    except Exception as e:
        print(f"\n❌ Adapter test failed: {e}")
        logger.error(f"Adapter test error: {e}", exc_info=True)
        return False

def test_match_history():
    """Test match history operations."""
    print("\n📊 Testing Match History")
    print("=" * 40)
    
    test_chat_id = -67890
    
    try:
        # Add a test match
        match_data = {
            'match_id': 'test_001',
            'timestamp': '2023-12-01T12:00:00',
            'result': 'win',
            'dice_result': [3, 4, 5],
            'winning_type': 'straight',
            'total_bets': 100
        }
        
        success = db_adapter.add_match_to_history(test_chat_id, match_data)
        print(f"Add match result: {'✅ Success' if success else '❌ Failed'}")
        
        # Get recent matches
        recent_matches = db_adapter.get_recent_matches(test_chat_id, 5)
        print(f"Recent matches found: {len(recent_matches)}")
        
        for match in recent_matches[-3:]:  # Show last 3
            print(f"  Match {match['match_id']}: {match['result']} - {match.get('total_bets', 0)} points")
        
        print("\n✅ Match history operations completed")
        return True
        
    except Exception as e:
        print(f"\n❌ Match history test failed: {e}")
        logger.error(f"Match history test error: {e}", exc_info=True)
        return False

def main():
    """Run all database tests."""
    print("🚀 DiceBot Database Test Suite")
    print("=" * 50)
    
    tests = [
        test_database_connection,
        test_adapter_operations,
        test_match_history
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📋 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Database setup is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)