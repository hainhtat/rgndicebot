#!/usr/bin/env python3
"""
Test script to verify PostgreSQL database integration fixes.
"""

import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import USE_DATABASE
from database.adapter import DatabaseAdapter
from database.connection import init_database
from game.game_logic import DiceGame, place_bet, payout
from config.constants import BET_TYPE_BIG, GAME_STATE_WAITING, GAME_STATE_CLOSED
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def test_database_connection():
    """Test basic database connection."""
    print("\n=== Testing Database Connection ===")
    
    if not USE_DATABASE:
        print("❌ Database mode is disabled. Set USE_DATABASE=True in settings.")
        return False
    
    try:
        success = init_database()
        if success:
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database initialization failed")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_player_stats_operations():
    """Test player stats database operations."""
    print("\n=== Testing Player Stats Operations ===")
    
    if not USE_DATABASE:
        print("⏭️  Skipping database tests (USE_DATABASE=False)")
        return True
    
    try:
        db_adapter = DatabaseAdapter()
        
        # Test user and chat IDs
        test_user_id = 999999999
        test_chat_id = -999999999
        test_username = "TestUser"
        
        # Test get_or_create_player_stats
        print("Testing get_or_create_player_stats...")
        stats = db_adapter.get_or_create_player_stats(test_user_id, test_chat_id, test_username)
        print(f"✅ Created/retrieved player stats: {stats}")
        
        # Test update_player_stats (bet placement)
        print("Testing update_player_stats (bet placement)...")
        initial_score = stats['score']
        bet_amount = 100
        success = db_adapter.update_player_stats(test_user_id, test_chat_id, -bet_amount, False, 0)
        if success:
            print(f"✅ Player stats updated for bet placement")
        else:
            print(f"❌ Failed to update player stats for bet placement")
            return False
        
        # Test update_player_stats (game result)
        print("Testing update_player_stats (game result)...")
        winnings = 200
        net_result = winnings - bet_amount  # Net profit
        success = db_adapter.update_player_stats(test_user_id, test_chat_id, net_result, True, 1)
        if success:
            print(f"✅ Player stats updated for game result")
        else:
            print(f"❌ Failed to update player stats for game result")
            return False
        
        # Verify final stats
        final_stats = db_adapter.get_or_create_player_stats(test_user_id, test_chat_id)
        expected_score = initial_score + net_result
        if final_stats['score'] == expected_score:
            print(f"✅ Final score correct: {final_stats['score']} (expected: {expected_score})")
        else:
            print(f"❌ Final score incorrect: {final_stats['score']} (expected: {expected_score})")
            return False
        
        print(f"✅ All player stats operations successful")
        return True
        
    except Exception as e:
        print(f"❌ Player stats operations error: {e}")
        return False

def test_place_bet_integration():
    """Test place_bet function with database integration."""
    print("\n=== Testing place_bet Database Integration ===")
    
    try:
        # Create test data
        test_user_id = 888888888
        test_chat_id = -888888888
        test_username = "BetTestUser"
        
        # Create game
        game = DiceGame(match_id=1, chat_id=test_chat_id)
        
        # Create test data structures
        chat_data = {
            "player_stats": {},
            "match_counter": 1
        }
        
        global_data = {
            "users": {
                str(test_user_id): {
                    "full_name": "Test User",
                    "referral_points": 50,
                    "bonus_points": 25
                }
            },
            "global_user_data": {
                str(test_user_id): {
                    "referral_points": 50,
                    "bonus_points": 25
                }
            }
        }
        
        # Mock save_data_unified to prevent recursion
        import main
        original_save = main.save_data_unified
        main.save_data_unified = lambda x: None
        
        try:
            # Test placing a bet
            result = place_bet(
                game=game,
                user_id=test_user_id,
                username=test_username,
                bet_type=BET_TYPE_BIG,
                amount=100,
                chat_data=chat_data,
                global_data=global_data,
                chat_id=test_chat_id
            )
            
            print(f"✅ Bet placed successfully: {result}")
            
            # Verify bet was recorded in game
            if str(test_user_id) in game.bets[BET_TYPE_BIG]:
                bet_amount = game.bets[BET_TYPE_BIG][str(test_user_id)]
                print(f"✅ Bet recorded in game: {bet_amount}")
            else:
                print(f"❌ Bet not found in game data")
                return False
            
            return True
            
        finally:
            # Restore original function
            main.save_data_unified = original_save
            
    except Exception as e:
        print(f"❌ place_bet integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_payout_integration():
    """Test payout function with database integration."""
    print("\n=== Testing Payout Database Integration ===")
    
    try:
        # Create test data
        test_user_id = 777777777
        test_chat_id = -777777777
        test_username = "PayoutTestUser"
        
        # Create game with result
        game = DiceGame(match_id=2, chat_id=test_chat_id)
        game.state = GAME_STATE_CLOSED
        game.result = (4, 5)  # Sum = 9, should be BIG
        
        # Add a bet to the game
        game.bets[BET_TYPE_BIG][str(test_user_id)] = 100
        game.participants.add(str(test_user_id))
        
        # Create test data structures
        chat_data = {
            "player_stats": {
                str(test_user_id): {
                    "username": test_username,
                    "score": 900,  # After bet deduction
                    "total_wins": 0,
                    "total_losses": 0,
                    "total_bets": 1,
                    "last_active": datetime.now().isoformat()
                }
            },
            "match_history": []
        }
        
        global_data = {
            "users": {
                str(test_user_id): {
                    "full_name": "Payout Test User"
                }
            }
        }
        
        # Mock save_data_unified
        import main
        original_save = main.save_data_unified
        main.save_data_unified = lambda x: None
        
        try:
            # Test payout processing
            result = payout(
                game=game,
                chat_data=chat_data,
                global_data=global_data,
                chat_id=test_chat_id
            )
            
            print(f"✅ Payout processed successfully")
            print(f"   Winners: {len(result['winners'])}")
            print(f"   Total payout: {result['total_payout']}")
            
            # Verify winner data
            if result['winners']:
                winner = result['winners'][0]
                print(f"   Winner balance: {winner['wallet_balance']}")
                print(f"   Winner winnings: {winner['winnings']}")
            
            return True
            
        finally:
            # Restore original function
            main.save_data_unified = original_save
            
    except Exception as e:
        print(f"❌ Payout integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all database integration tests."""
    print("🎲 Database Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_database_connection,
        test_player_stats_operations,
        test_place_bet_integration,
        test_payout_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Database integration is working correctly.")
        return True
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)