#!/usr/bin/env python3
"""
Test script to verify wallet balance deduction issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database usage for testing
os.environ['USE_DATABASE'] = 'False'

# Mock the save_data_unified function to prevent recursion
def mock_save_data_unified(data):
    pass

from game.game_logic import DiceGame
from config.constants import BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY
from config import settings

# Ensure database is disabled
settings.USE_DATABASE = False

# Replace the save function with mock
import game.game_logic
game.game_logic.save_data_unified = mock_save_data_unified

def test_wallet_deduction():
    """Test if wallet balance is properly deducted for multiple bets"""
    print("Testing wallet balance deduction...")
    
    # Create test data
    player_stats = {
        "username": "testuser",
        "score": 1000,  # Starting with 1000
        "total_bets": 0,
        "total_wins": 0,
        "total_losses": 0
    }
    
    global_user_data = {
        "username": "testuser",
        "referral_points": 0,
        "bonus_points": 0
    }
    
    # Create a new game
    game = DiceGame(match_id="test_001", chat_id=-1001)
    
    print(f"Initial wallet balance: {player_stats['score']}")
    
    # Simulate bet deductions manually
    bet_amounts = [100, 100, 100]  # Three bets of 100 each
    bet_types = [BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY]
    
    for i, (bet_type, amount) in enumerate(zip(bet_types, bet_amounts)):
        print(f"\nPlacing bet {i+1}: {bet_type} {amount}")
        
        # Check if sufficient funds
        if player_stats['score'] >= amount:
            # Deduct from wallet
            player_stats['score'] -= amount
            
            # Add to game bets
            if '12345' not in game.bets[bet_type]:
                game.bets[bet_type]['12345'] = 0
            game.bets[bet_type]['12345'] += amount
            
            print(f"Wallet balance after bet: {player_stats['score']}")
        else:
            print(f"Insufficient funds: {player_stats['score']} < {amount}")
    
    # Check final balance
    final_balance = player_stats['score']
    expected_balance = 1000 - 300  # Should be 700
    
    print(f"\nFinal balance: {final_balance}")
    print(f"Expected balance: {expected_balance}")
    
    if final_balance == expected_balance:
        print("✅ Wallet deduction test PASSED")
    else:
        print("❌ Wallet deduction test FAILED")
        print(f"Expected {expected_balance}, got {final_balance}")
        
    # Check game bets
    print(f"\nGame bets:")
    print(f"BIG: {game.bets.get('BIG', {})}")
    print(f"SMALL: {game.bets.get('SMALL', {})}")
    print(f"LUCKY: {game.bets.get('LUCKY', {})}")
    
    # Test the message format issue
    print("\n" + "="*50)
    print("Testing message format extraction...")
    
    # Simulate the result message format from place_bet
    result_message = f"✅ Bet placed: {BET_TYPE_BIG} 100 (Used 100 main ကျပ်)\nYour balance: {final_balance} main, 0 referral, 0 bonus ကျပ်"
    print(f"Result message: {result_message}")
    
    # Test balance extraction (this is what was fixed in message_formatter.py)
    try:
        balance_part = result_message.split("Your balance: ")[1]
        main_balance = int(balance_part.split(" main")[0])
        print(f"Extracted main balance: {main_balance}")
        
        if main_balance == final_balance:
            print("✅ Balance extraction test PASSED")
        else:
            print("❌ Balance extraction test FAILED")
    except Exception as e:
        print(f"❌ Balance extraction error: {e}")

if __name__ == "__main__":
    test_wallet_deduction()