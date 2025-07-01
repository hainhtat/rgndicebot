#!/usr/bin/env python3
"""
Simple test to debug the wallet balance issue.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode for testing
os.environ['USE_DATABASE'] = 'False'

from game.game_logic import DiceGame, place_bet
from config.config_manager import get_config
import utils.user_utils as user_utils
from config import settings

# Initialize config and ensure database is disabled
config = get_config()
settings.USE_DATABASE = False

def debug_balance_issue():
    print("=== Debugging Wallet Balance Issue ===")
    
    # Set up global_data for user_utils module
    test_global_data = {
        "all_chat_data": {
            "-1001234567890": {
                "player_stats": {
                    "123456789": {
                        "score": 1000,  # Initial balance
                        "total_bets": 0,
                        "username": "test_user"
                    }
                },
                "games": []
            }
        },
        "global_user_data": {
            "123456789": {
                "referral_points": 0,
                "bonus_points": 0
            }
        }
    }
    
    # Set the global_data variable in user_utils module
    user_utils.global_data = test_global_data
    
    chat_id = -1001234567890
    user_id = 123456789
    username = "test_user"
    bet_type = "BIG"
    bet_amount = 100
    
    # Create a new game
    match_id = 1
    game = DiceGame(match_id=match_id, chat_id=chat_id)
    chat_data = test_global_data["all_chat_data"][str(chat_id)]
    chat_data["current_game"] = game
    
    print(f"Initial balance: {chat_data['player_stats']['123456789']['score']}")
    
    # Check if player exists in chat_data before placing bet
    print(f"Player stats in chat_data: {chat_data['player_stats']}")
    print(f"User ID string: {str(user_id)}")
    
    # Place bet and get result message
    try:
        result_message = place_bet(
            game=game,
            user_id=user_id,
            username=username,
            bet_type=bet_type,
            amount=bet_amount,
            chat_data=chat_data,
            global_data=test_global_data,
            chat_id=chat_id
        )
        
        print(f"\nResult message: {result_message}")
        
        # Check the actual balance after bet
        actual_balance = chat_data['player_stats']['test_user']['score']
        print(f"Actual balance after bet: {actual_balance}")
        print(f"Expected balance: 900")
        
        # Extract balance from result message
        if "Your balance:" in result_message:
            balance_part = result_message.split("Your balance:")[1].strip()
            message_balance = int(balance_part.split(" main")[0])
            print(f"Balance shown in message: {message_balance}")
            
            # Check consistency
            if actual_balance == message_balance == 900:
                print("✅ All balances are correct and consistent!")
                return True
            else:
                print(f"❌ Balance issue detected!")
                print(f"   Expected: 900")
                print(f"   Actual data: {actual_balance}")
                print(f"   Message shows: {message_balance}")
                
                if actual_balance != 900:
                    print("   Issue: Actual balance deduction failed")
                if message_balance != 900:
                    print("   Issue: Message shows wrong balance")
                if actual_balance != message_balance:
                    print("   Issue: Inconsistency between actual and message balance")
                
                return False
        else:
            print("❌ No balance information found in result message")
            return False
        
    except Exception as e:
        print(f"Error during bet placement: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_balance_issue()