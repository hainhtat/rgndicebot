#!/usr/bin/env python3
"""
Simple test to debug the wallet balance issue without logging complications.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode and logging for testing
os.environ['USE_DATABASE'] = 'False'
os.environ['LOG_LEVEL'] = 'CRITICAL'  # Minimize logging

from game.game_logic import DiceGame
from config.config_manager import get_config
import utils.user_utils as user_utils
from config import settings

# Initialize config and ensure database is disabled
config = get_config()
settings.USE_DATABASE = False

def test_balance_directly():
    print("=== Simple Balance Test ===")
    
    # Set up test data
    test_global_data = {
        "all_chat_data": {
            "-1001234567890": {
                "player_stats": {
                    "123456789": {
                        "score": 1000,
                        "total_bets": 0,
                        "total_wins": 0,
                        "total_losses": 0,
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
    bet_amount = 100
    
    # Create a new game
    match_id = 1
    game = DiceGame(match_id=match_id, chat_id=chat_id)
    chat_data = test_global_data["all_chat_data"][str(chat_id)]
    chat_data["current_game"] = game
    
    print(f"Initial balance: {chat_data['player_stats']['123456789']['score']}")
    
    # Manually simulate the balance check logic from place_bet
    player_stats = chat_data["player_stats"]
    current_player = player_stats[str(user_id)]
    
    # Get global user data for referral points and bonus points
    global_user_data = test_global_data["global_user_data"][str(user_id)]
    
    # Calculate available funds
    main_score = current_player["score"]
    referral_points = global_user_data.get("referral_points", 0)
    bonus_points = global_user_data.get("bonus_points", 0)
    total_available = main_score + referral_points + bonus_points
    
    print(f"Main score: {main_score}")
    print(f"Referral points: {referral_points}")
    print(f"Bonus points: {bonus_points}")
    print(f"Total available: {total_available}")
    print(f"Bet amount: {bet_amount}")
    
    if total_available >= bet_amount:
        # Simulate successful bet placement
        current_player["score"] -= bet_amount
        print(f"✅ Bet would be successful!")
        print(f"New balance after bet: {current_player['score']}")
        
        # Simulate the balance message format
        balance_message = f"Your balance: {current_player['score']} main, {referral_points} referral, {bonus_points} bonus ကျပ်"
        print(f"Balance message: {balance_message}")
        
        # Extract balance from message (like message_formatter does)
        if "Your balance:" in balance_message:
            balance_part = balance_message.split("Your balance:")[1].strip()
            message_balance = int(balance_part.split(" main")[0])
            print(f"Extracted balance: {message_balance}")
            
            if current_player['score'] == message_balance == 900:
                print("✅ SUCCESS: All balances are consistent!")
                return True
            else:
                print(f"❌ INCONSISTENCY DETECTED:")
                print(f"   Expected: 900")
                print(f"   Actual balance: {current_player['score']}")
                print(f"   Message balance: {message_balance}")
                return False
    else:
        print(f"❌ Insufficient funds: {total_available} < {bet_amount}")
        return False

if __name__ == "__main__":
    success = test_balance_directly()
    if success:
        print("\n🎉 Balance logic is working correctly!")
    else:
        print("\n⚠️ Balance issue detected!")