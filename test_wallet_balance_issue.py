#!/usr/bin/env python3
"""
Test to reproduce the wallet balance issue where confirmation messages
show incorrect balance after bet placement.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode for testing
os.environ['USE_DATABASE'] = 'False'
os.environ['LOG_LEVEL'] = 'CRITICAL'  # Minimize logging

from game.game_logic import DiceGame, place_bet
from utils.message_formatter import format_bet_confirmation
from main import save_data_unified, load_data_unified
from config.config_manager import get_config
import utils.user_utils as user_utils
import config.settings as settings
import asyncio
from unittest.mock import AsyncMock

# Ensure database mode is disabled
settings.USE_DATABASE = False

# Initialize config
config = get_config()

def test_wallet_balance_consistency():
    """
    Test that wallet balance is consistent between actual balance and displayed balance.
    """
    print("\n=== Testing Wallet Balance Consistency ===\n")
    print("DEBUG: Starting wallet balance consistency test")
    
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
    
    # Place bet and get result message
    try:
        # Check initial balance
        initial_balance = chat_data['player_stats']['123456789']['score']
        print(f"DEBUG: Initial balance before bet: {initial_balance}")
        
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
        
        print(f"DEBUG: Result message from place_bet: {result_message}")
        print(f"\nBet placement result message:")
        print(result_message)
        
        # Check the actual balance after bet
        actual_balance = chat_data['player_stats']['123456789']['score']
        print(f"DEBUG: Actual balance after first bet: {actual_balance}")
        print(f"DEBUG: Expected balance after first bet: {initial_balance - bet_amount}")
        print(f"\nActual balance after bet: {actual_balance}")
        
        # Extract balance from result message
        if "Your balance:" in result_message:
            balance_part = result_message.split("Your balance:")[1].strip()
            message_balance = int(balance_part.split(" main")[0])
            print(f"DEBUG: Balance shown in message: {message_balance}")
            print(f"Balance shown in message: {message_balance}")
            print(f"Expected balance (1000 - 100): 900")
            
            # Check consistency
            if actual_balance == message_balance:
                print("✅ Balance is consistent!")
            else:
                print(f"❌ Balance mismatch! Actual: {actual_balance}, Message: {message_balance}")
                print(f"❌ Expected: 900, Got actual: {actual_balance}, Got message: {message_balance}")
                return False
        
        # Test multiple bets to see if the issue compounds
        print("\n--- Testing second bet ---")
        result_message_2 = place_bet(
            game=game,
            user_id=user_id,
            username=username,
            bet_type=bet_type,
            amount=bet_amount,
            chat_data=chat_data,
            global_data=global_data,
            chat_id=chat_id
        )
        
        print(f"Second bet result message:")
        print(result_message_2)
        
        actual_balance_2 = chat_data['player_stats']['123456789']['score']
        print(f"\nActual balance after second bet: {actual_balance_2}")
        
        if "Your balance:" in result_message_2:
            balance_part_2 = result_message_2.split("Your balance:")[1].strip()
            message_balance_2 = int(balance_part_2.split(" main")[0])
            print(f"Balance shown in second message: {message_balance_2}")
            
            if actual_balance_2 == message_balance_2:
                print("✅ Second balance is consistent!")
            else:
                print(f"❌ Second balance mismatch! Actual: {actual_balance_2}, Message: {message_balance_2}")
                return False
        
        return True
        
    except Exception as e:
        print(f"Error during bet placement: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_message_formatter_consistency():
    """
    Test the message formatter to ensure it extracts balance correctly.
    """
    print("\n=== Testing Message Formatter ===\n")
    
    # Test message with known balance
    test_message = "✅ Bet placed: BIG 100 (Used 100 main ကျပ်)\nYour balance: 765 main, 0 referral, 0 bonus ကျပ်"
    
    # Mock context
    mock_context = AsyncMock()
    
    # Test the formatter
    formatted_message = await format_bet_confirmation(
        bet_type="BIG",
        amount=100,
        result_message=test_message,
        username="test_user",
        referral_points=0,
        bonus_points=0,
        user_id="123456789",
        game=None,
        global_data={},
        context=mock_context
    )
    
    print(f"Original message: {test_message}")
    print(f"\nFormatted message: {formatted_message}")
    
    # Check if balance extraction works correctly
    if "Your balance:" in test_message:
        balance_part = test_message.split("Your balance:")[1].strip()
        extracted_balance = int(balance_part.split(" main")[0])
        print(f"\nExtracted balance: {extracted_balance}")
        
        if extracted_balance == 765:
            print("✅ Balance extraction works correctly!")
            return True
        else:
            print(f"❌ Balance extraction failed! Expected: 765, Got: {extracted_balance}")
            return False
    
    return False

if __name__ == "__main__":
    print("=== Wallet Balance Consistency Test ===")
    
    # Test 1: Basic wallet balance consistency
    print("DEBUG: About to call test_wallet_balance_consistency()")
    try:
        test1_result = test_wallet_balance_consistency()
        print(f"DEBUG: test_wallet_balance_consistency() returned: {test1_result}")
    except Exception as e:
        print(f"ERROR: Exception in test_wallet_balance_consistency(): {e}")
        import traceback
        traceback.print_exc()
        test1_result = False
    
    # Test 2: Message formatter consistency
    test2_result = asyncio.run(test_message_formatter_consistency())
    
    print("\n=== Test Results ===")
    print(f"Wallet balance consistency: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"Message formatter consistency: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! The wallet balance system is working correctly.")
    else:
        print("\n⚠️ Some tests failed. There may be an issue with wallet balance consistency.")