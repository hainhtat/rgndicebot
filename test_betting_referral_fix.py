#!/usr/bin/env python3
"""
Test script to verify that betting uses referral points first and doesn't cause them to disappear.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.game_logic import DiceGame, place_bet
from config.constants import (
    GAME_STATE_WAITING, BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY,
    global_data
)
from utils.user_utils import get_or_create_global_user_data
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def setup_test_data():
    """Set up test data for betting scenarios."""
    # Clear any existing data
    global_data.clear()
    
    # Initialize global_data structure
    global_data["global_user_data"] = {}
    
    # Test chat data
    chat_id = -1001234567890
    chat_data = {
        "player_stats": {},
        "current_game": None
    }
    
    # Test user data
    user_id = 12345
    username = "testuser"
    
    # Initialize player stats with main wallet points
    chat_data["player_stats"][str(user_id)] = {
        "username": username,
        "score": 1000,  # Main wallet
        "total_bets": 0,
        "total_wins": 0,
        "total_losses": 0,
        "last_active": datetime.now().isoformat()
    }
    
    # Initialize global user data with referral points
    global_user_data = get_or_create_global_user_data(user_id, username=username)
    global_user_data["referral_points"] = 500  # Referral points
    
    return chat_data, user_id, username, chat_id

def test_referral_points_used_first():
    """Test that referral points are used before main wallet."""
    logger.info("\n=== Test: Referral Points Used First ===")
    
    chat_data, user_id, username, chat_id = setup_test_data()
    
    # Create a new game
    game = DiceGame(match_id=1, chat_id=chat_id)
    
    # Initial balances
    initial_main_score = chat_data["player_stats"][str(user_id)]["score"]
    initial_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
    
    logger.info(f"Initial main score: {initial_main_score}")
    logger.info(f"Initial referral points: {initial_referral_points}")
    
    # Place a bet that should use only referral points
    bet_amount = 300  # Less than referral points (500)
    
    try:
        result = place_bet(game, user_id, username, BET_TYPE_BIG, bet_amount, chat_data, global_data)
        logger.info(f"Bet result: {result}")
        
        # Check balances after bet
        final_main_score = chat_data["player_stats"][str(user_id)]["score"]
        final_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
        
        logger.info(f"Final main score: {final_main_score}")
        logger.info(f"Final referral points: {final_referral_points}")
        
        # Assertions
        assert final_main_score == initial_main_score, f"Main score should not change! Expected {initial_main_score}, got {final_main_score}"
        assert final_referral_points == initial_referral_points - bet_amount, f"Referral points should decrease by {bet_amount}! Expected {initial_referral_points - bet_amount}, got {final_referral_points}"
        
        logger.info("✅ Test passed: Referral points used first")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_mixed_payment():
    """Test betting with amount greater than referral points (should use both)."""
    logger.info("\n=== Test: Mixed Payment (Referral + Main) ===")
    
    chat_data, user_id, username, chat_id = setup_test_data()
    
    # Create a new game
    game = DiceGame(match_id=2, chat_id=chat_id)
    
    # Initial balances
    initial_main_score = chat_data["player_stats"][str(user_id)]["score"]
    initial_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
    
    logger.info(f"Initial main score: {initial_main_score}")
    logger.info(f"Initial referral points: {initial_referral_points}")
    
    # Place a bet that requires both referral points and main wallet
    bet_amount = 800  # More than referral points (500), less than total (1500)
    
    try:
        result = place_bet(game, user_id, username, BET_TYPE_SMALL, bet_amount, chat_data, global_data)
        logger.info(f"Bet result: {result}")
        
        # Check balances after bet
        final_main_score = chat_data["player_stats"][str(user_id)]["score"]
        final_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
        
        logger.info(f"Final main score: {final_main_score}")
        logger.info(f"Final referral points: {final_referral_points}")
        
        # Expected: All referral points used (500), remaining 300 from main wallet
        expected_main_score = initial_main_score - (bet_amount - initial_referral_points)
        expected_referral_points = 0
        
        # Assertions
        assert final_main_score == expected_main_score, f"Main score incorrect! Expected {expected_main_score}, got {final_main_score}"
        assert final_referral_points == expected_referral_points, f"Referral points incorrect! Expected {expected_referral_points}, got {final_referral_points}"
        
        logger.info("✅ Test passed: Mixed payment works correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_insufficient_funds():
    """Test betting with amount greater than total available funds."""
    logger.info("\n=== Test: Insufficient Funds ===")
    
    chat_data, user_id, username, chat_id = setup_test_data()
    
    # Create a new game
    game = DiceGame(match_id=3, chat_id=chat_id)
    
    # Initial balances
    initial_main_score = chat_data["player_stats"][str(user_id)]["score"]
    initial_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
    total_available = initial_main_score + initial_referral_points
    
    logger.info(f"Initial main score: {initial_main_score}")
    logger.info(f"Initial referral points: {initial_referral_points}")
    logger.info(f"Total available: {total_available}")
    
    # Place a bet that exceeds total available funds
    bet_amount = total_available + 100
    
    try:
        result = place_bet(game, user_id, username, BET_TYPE_LUCKY, bet_amount, chat_data, global_data)
        logger.error(f"❌ Test failed: Bet should have been rejected but got: {result}")
        return False
        
    except Exception as e:
        logger.info(f"Expected error: {e}")
        
        # Check that balances remain unchanged
        final_main_score = chat_data["player_stats"][str(user_id)]["score"]
        final_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
        
        assert final_main_score == initial_main_score, f"Main score should not change on failed bet! Expected {initial_main_score}, got {final_main_score}"
        assert final_referral_points == initial_referral_points, f"Referral points should not change on failed bet! Expected {initial_referral_points}, got {final_referral_points}"
        
        logger.info("✅ Test passed: Insufficient funds handled correctly")
        return True

def test_multiple_bets():
    """Test multiple bets to ensure referral points don't disappear unexpectedly."""
    logger.info("\n=== Test: Multiple Bets ===")
    
    chat_data, user_id, username, chat_id = setup_test_data()
    
    # Create a new game
    game = DiceGame(match_id=4, chat_id=chat_id)
    
    # Initial balances
    initial_main_score = chat_data["player_stats"][str(user_id)]["score"]
    initial_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
    
    logger.info(f"Initial main score: {initial_main_score}")
    logger.info(f"Initial referral points: {initial_referral_points}")
    
    # Place first bet (should use referral points)
    bet1_amount = 200
    
    try:
        result1 = place_bet(game, user_id, username, BET_TYPE_BIG, bet1_amount, chat_data, global_data)
        logger.info(f"Bet 1 result: {result1}")
        
        # Check balances after first bet
        mid_main_score = chat_data["player_stats"][str(user_id)]["score"]
        mid_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
        
        logger.info(f"After bet 1 - Main score: {mid_main_score}, Referral points: {mid_referral_points}")
        
        # Verify first bet used only referral points
        expected_mid_main = initial_main_score  # Should be unchanged
        expected_mid_referral = initial_referral_points - bet1_amount  # Should decrease
        
        assert mid_main_score == expected_mid_main, f"After bet 1: Main score should be {expected_mid_main}, got {mid_main_score}"
        assert mid_referral_points == expected_mid_referral, f"After bet 1: Referral points should be {expected_mid_referral}, got {mid_referral_points}"
        
        # Place second bet on same type (should use remaining referral points)
        bet2_amount = 250
        
        result2 = place_bet(game, user_id, username, BET_TYPE_BIG, bet2_amount, chat_data, global_data)
        logger.info(f"Bet 2 result: {result2}")
        
        # Check final balances
        final_main_score = chat_data["player_stats"][str(user_id)]["score"]
        final_referral_points = global_data["global_user_data"][str(user_id)]["referral_points"]
        
        logger.info(f"Final main score: {final_main_score}")
        logger.info(f"Final referral points: {final_referral_points}")
        
        # Expected: First bet uses 200 referral points, second bet uses 250 referral points
        # Total referral points used: 200 + 250 = 450, remaining: 500 - 450 = 50
        expected_referral_points = 50
        expected_main_score = initial_main_score  # No main score should be deducted
        
        # Assertions
        assert final_main_score == expected_main_score, f"Main score incorrect! Expected {expected_main_score}, got {final_main_score}"
        assert final_referral_points == expected_referral_points, f"Referral points incorrect! Expected {expected_referral_points}, got {final_referral_points}"
        
        logger.info("✅ Test passed: Multiple bets work correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting betting referral points test suite...")
    
    tests = [
        test_referral_points_used_first,
        test_mixed_payment,
        test_insufficient_funds,
        test_multiple_bets
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            logger.error(f"Test {test.__name__} crashed: {e}")
    
    logger.info(f"\n=== Test Results ===")
    logger.info(f"Passed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All tests passed! Betting logic is working correctly.")
        return True
    else:
        logger.error(f"❌ {total - passed} test(s) failed. There are issues with the betting logic.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)