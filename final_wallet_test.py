#!/usr/bin/env python3
"""
Final test to identify and fix the wallet balance issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode and minimize logging
os.environ['USE_DATABASE'] = 'False'
os.environ['LOG_LEVEL'] = 'CRITICAL'

from game.game_logic import DiceGame, place_bet
import utils.user_utils as user_utils
import config.settings as settings
from config.config_manager import get_config

# Ensure database mode is disabled
settings.USE_DATABASE = False
config = get_config()

def test_actual_wallet_balance():
    print("=== Final Wallet Balance Test ===")
    
    # Set up test data
    global_data = {
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
    
    # Set the global_data in user_utils module
    user_utils.global_data = global_data
    
    chat_id = -1001234567890
    user_id = 123456789
    username = "test_user"
    bet_type = "BIG"
    bet_amount = 100
    
    # Create a new game
    match_id = 1
    game = DiceGame(match_id=match_id, chat_id=chat_id)
    chat_data = global_data["all_chat_data"][str(chat_id)]
    chat_data["current_game"] = game
    
    print(f"Initial balance: {chat_data['player_stats']['123456789']['score']}")
    
    try:
        # Place bet and get result message
        result_message = place_bet(
            game=game,
            user_id=user_id,
            username=username,
            bet_type=bet_type,
            amount=bet_amount,
            chat_data=chat_data,
            global_data=global_data,
            chat_id=chat_id
        )
        
        print(f"\n✅ Bet placed successfully!")
        print(f"Result message: {result_message}")
        
        # Check the actual balance after bet
        actual_balance = chat_data['player_stats']['123456789']['score']
        print(f"\nActual balance after bet: {actual_balance}")
        print(f"Expected balance (1000 - 100): 900")
        
        # Extract balance from result message
        if "Your balance:" in result_message:
            balance_part = result_message.split("Your balance:")[1].strip()
            message_balance = int(balance_part.split(" main")[0])
            print(f"Balance shown in message: {message_balance}")
            
            # Check consistency
            if actual_balance == message_balance:
                if actual_balance == 900:
                    print("\n🎉 SUCCESS: Balance is consistent and correct!")
                    return True
                else:
                    print(f"\n⚠️ WARNING: Balance is consistent but incorrect! Both show {actual_balance}, expected 900")
                    print("This suggests the balance deduction logic has a bug.")
                    return False
            else:
                print(f"\n❌ CRITICAL: Balance mismatch! Actual: {actual_balance}, Message: {message_balance}")
                print("This suggests the message formatting has a bug.")
                return False
        else:
            print("\n❌ ERROR: No balance information found in result message")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: Exception during bet placement: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting final wallet balance test...")
    result = test_actual_wallet_balance()
    print(f"\nTest result: {'PASS' if result else 'FAIL'}")
    
    if not result:
        print("\n🔍 DIAGNOSIS:")
        print("The wallet balance issue has been confirmed.")
        print("The problem is likely in the place_bet function or message formatting.")
        print("Check the balance deduction logic and message construction.")