#!/usr/bin/env python3
"""
Simple wallet balance debug script without logging complications
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode and logging for testing
os.environ['USE_DATABASE'] = 'False'
os.environ['LOG_LEVEL'] = 'CRITICAL'  # Minimize logging

from game.game_logic import DiceGame, place_bet
import utils.user_utils as user_utils
import config.settings as settings
from config.config_manager import get_config

# Ensure database mode is disabled
settings.USE_DATABASE = False

# Initialize config
config = get_config()

def test_wallet_balance():
    print("=== Simple Wallet Balance Test ===")
    
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
        
        print(f"\nBet placement successful!")
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
            if actual_balance == message_balance == 900:
                print("✅ Balance is consistent and correct!")
                return True
            elif actual_balance == message_balance:
                print(f"⚠️ Balance is consistent but incorrect! Both show {actual_balance}, expected 900")
                return False
            else:
                print(f"❌ Balance mismatch! Actual: {actual_balance}, Message: {message_balance}, Expected: 900")
                return False
        else:
            print("❌ No balance information found in result message")
            return False
            
    except Exception as e:
        print(f"Error during bet placement: {e}")
        return False

if __name__ == "__main__":
    test_wallet_balance()