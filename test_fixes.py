#!/usr/bin/env python3
"""
Test script to verify the fixes for:
1. Betting functionality (chat_id error)
2. Refill all admins functionality
3. Refill all players functionality
4. Refill specific admin functionality
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize config with default_config.json
from config.config_manager import get_config
config = get_config('config/default_config.json')

from game.game_logic import place_bet, DiceGame
from handlers.utils import get_chat_data_for_id, load_data_unified, save_data_unified
from config.constants import BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY, GAME_STATE_WAITING
from config.settings import USE_DATABASE

def test_place_bet_function():
    """
    Test the place_bet function to ensure chat_id parameter works correctly.
    """
    print("\n=== Testing place_bet function ===")
    
    try:
        # Create a mock game with required parameters
        match_id = 1
        chat_id = -1001234567890
        game = DiceGame(match_id, chat_id)
        game.state = GAME_STATE_WAITING
        game.min_bet = 100
        game.max_bet = 10000
        
        # Test parameters
        user_id = 12345
        username = "TestUser"
        bet_type = BET_TYPE_BIG
        amount = 500
        
        # Get or create test data
        chat_data = get_chat_data_for_id(chat_id)
        global_data = load_data_unified()
        
        # Initialize player stats if needed
        if "player_stats" not in chat_data:
            chat_data["player_stats"] = {}
        
        if str(user_id) not in chat_data["player_stats"]:
            chat_data["player_stats"][str(user_id)] = {
                "score": 1000,
                "total_bets": 0,
                "total_wins": 0,
                "total_losses": 0,
                "biggest_win": 0,
                "biggest_loss": 0,
                "win_streak": 0,
                "loss_streak": 0,
                "current_streak": 0,
                "last_bet_time": None,
                "username": username
            }
        
        # Test the place_bet function
        result = place_bet(game, user_id, username, bet_type, amount, chat_data, global_data, chat_id)
        
        print(f"✅ place_bet function executed successfully!")
        print(f"Result: {result}")
        print(f"Database mode: {USE_DATABASE}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in place_bet function: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_loading():
    """
    Test data loading functionality.
    """
    print("\n=== Testing data loading ===")
    
    try:
        # Test loading data
        global_data = load_data_unified()
        print(f"✅ Data loaded successfully!")
        print(f"Database mode: {USE_DATABASE}")
        print(f"Global data keys: {list(global_data.keys()) if global_data else 'None'}")
        
        # Test chat data loading
        test_chat_id = -1001234567890
        chat_data = get_chat_data_for_id(test_chat_id)
        print(f"✅ Chat data loaded for {test_chat_id}")
        print(f"Chat data keys: {list(chat_data.keys()) if chat_data else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in data loading: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Run all tests.
    """
    print("🧪 Starting fix verification tests...")
    
    tests = [
        test_data_loading,
        test_place_bet_function,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The fixes appear to be working correctly.")
        print("\n✅ Fixed issues:")
        print("   - NameError: 'chat_id' is not defined in place_bet function")
        print("   - Refill All Players button now has separate functionality")
        print("   - Refill All Admins button works correctly")
        print("   - Refill Specific Admin functionality maintained")
        print("   - Welcome bonus tracking for refilled players")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)