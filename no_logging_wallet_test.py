#!/usr/bin/env python3
"""
Simple wallet balance test without any logging to avoid recursion issues
"""

import os
import sys

# Disable all logging to avoid recursion issues
os.environ['PYTHONPATH'] = '/Users/heinhtetaung/Desktop/dicebot'
os.environ['USE_DATABASE'] = 'False'

# Add project root to path
sys.path.insert(0, '/Users/heinhtetaung/Desktop/dicebot')

# Disable logging completely
import logging
logging.disable(logging.CRITICAL)

# Import required modules
from config import settings
from utils import user_utils
from game.game_logic import place_bet

# Mock save_data_unified to avoid recursion
def mock_save_data_unified(data):
    pass

# Replace the save function
import game.game_logic
game.game_logic.save_data_unified = mock_save_data_unified

# Explicitly disable database
settings.USE_DATABASE = False

def test_wallet_balance():
    """Test wallet balance without any logging"""
    
    # Setup test data
    global_data = {
        "users": {
            "123456789": {
                "user_id": 123456789,
                "username": "testuser",
                "score": 1000,
                "bonus_points": 0,
                "referral_points": 0,
                "total_bets": 0,
                "total_wins": 0,
                "total_losses": 0,
                "win_streak": 0,
                "loss_streak": 0,
                "last_bet_time": None,
                "daily_bonus_claimed": False,
                "last_daily_bonus": None,
                "referral_code": "TEST123",
                "referred_by": None,
                "referrals": [],
                "is_admin": False,
                "is_banned": False,
                "ban_reason": None,
                "created_at": "2024-01-01T00:00:00",
                "last_active": "2024-01-01T00:00:00"
            }
        },
        "global_user_data": {
            "123456789": {
                "full_name": "testuser",
                "username": "testuser",
                "bonus_points": 0,
                "referral_points": 0,
                "referred_by": None,
                "welcome_bonus_received": False,
                "last_cashback_date": None
            }
        },
        "groups": {},
        "settings": {
            "min_bet": 10,
            "max_bet": 1000,
            "house_edge": 0.01
        }
    }
    
    # Set global data
    user_utils.global_data = global_data
    
    print("=== WALLET BALANCE TEST ===")
    print(f"Initial balance: {global_data['users']['123456789']['score']}")
    
    try:
        # Create a mock game object
        from game.game_logic import DiceGame
        game = DiceGame(match_id=1, chat_id=0)
        
        # Create chat_data with player_stats
        chat_data = {
            "player_stats": {
                "123456789": {
                    "username": "testuser",
                    "score": 1000,
                    "total_bets": 0,
                    "total_wins": 0,
                    "total_losses": 0,
                    "last_active": "2024-01-01T00:00:00"
                }
            }
        }
        
        # Place a bet with correct parameters
        result = place_bet(game, 123456789, "testuser", "BIG", 100, chat_data, global_data, 0)
        
        print(f"Bet result: {result}")
        
        # Check actual balance after bet (from chat_data where the deduction happens)
        actual_balance = chat_data['player_stats']['123456789']['score']
        expected_balance = 900  # 1000 - 100
        
        print(f"Actual balance after bet: {actual_balance}")
        print(f"Expected balance: {expected_balance}")
        
        # Extract balance from message
        if "Balance:" in result:
            balance_part = result.split("Balance:")[1].strip()
            extracted_balance = int(balance_part.split()[0])
            print(f"Balance from message: {extracted_balance}")
            
            # Check consistency
            if actual_balance == expected_balance:
                print("✅ Actual balance calculation is CORRECT")
            else:
                print("❌ Actual balance calculation is WRONG")
                
            if extracted_balance == actual_balance:
                print("✅ Message balance matches actual balance")
            else:
                print("❌ Message balance does NOT match actual balance")
                print(f"   Message shows: {extracted_balance}, Actual: {actual_balance}")
                
            if extracted_balance == 765:
                print("🔍 CONFIRMED: Hardcoded balance 765 detected in message!")
                
        return True
        
    except Exception as e:
        print(f"Error during bet: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wallet_balance()
    print(f"\nTest result: {'PASS' if success else 'FAIL'}")