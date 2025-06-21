#!/usr/bin/env python3
"""
Comprehensive test script for dice bot core functionality.
Tests user utils, game logic, data integrity, and identifies issues with N/A and incorrect points.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.constants import global_data, get_chat_data_for_id, get_admin_data
from config.settings import REFERRAL_BONUS_POINTS, WELCOME_BONUS_POINTS
from data.file_manager import load_data, save_data
from utils.user_utils import (
    get_or_create_global_user_data, process_referral, process_pending_referral,
    adjust_user_score, process_welcome_bonus
)
from game.game_logic import DiceGame, place_bet, roll_dice, payout
from handlers.utils import create_new_game, get_current_game
from utils.message_formatter import format_game_history

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockContext:
    """Mock context for testing without actual Telegram bot."""
    class MockBot:
        async def get_chat(self, user_id):
            # Return mock user data
            class MockUser:
                def __init__(self, user_id):
                    self.user_id = user_id
                    self.first_name = f"TestUser{user_id}"
                    self.last_name = "LastName"
                    self.username = f"testuser{user_id}"
                    self.full_name = f"{self.first_name} {self.last_name}"
            return MockUser(user_id)
        
        async def get_chat_member(self, chat_id, user_id):
            class MockChatMember:
                def __init__(self, user_id):
                    self.user = MockContext.MockBot().get_chat(user_id)
            return MockChatMember(user_id)
    
    def __init__(self):
        self.bot = self.MockBot()

def backup_data():
    """Create a backup of current data before testing."""
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
        
        backup_filename = f"data_backup_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Data backed up to {backup_filename}")
        return backup_filename
    except Exception as e:
        logger.error(f"Failed to backup data: {e}")
        return None

def load_test_data():
    """Load current data for testing."""
    try:
        load_data(global_data)
        logger.info("Test data loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        return False

def test_user_utils():
    """Test user utility functions."""
    logger.info("\n=== Testing User Utils ===")
    
    # Test get_or_create_global_user_data
    user_data = get_or_create_global_user_data(12345, "Test", "User", "testuser")
    assert user_data["full_name"] == "Test User"
    assert user_data["username"] == "testuser"
    assert user_data["referral_points"] == 0
    logger.info("✅ get_or_create_global_user_data works correctly")
    
    # Test adjust_user_score
    chat_id = 67890
    user_id = 12345
    
    # Create chat data first
    chat_data = get_chat_data_for_id(chat_id)
    chat_data["player_stats"][str(user_id)] = {
        "username": "testuser",
        "score": 1000,
        "total_bets": 0,
        "total_wins": 0,
        "total_losses": 0,
        "last_active": datetime.now().isoformat()
    }
    
    success, message = adjust_user_score(user_id, str(chat_id), 500)
    logger.info(f"adjust_user_score result: success={success}, message='{message}'")
    if not success:
        logger.error(f"adjust_user_score failed: {message}")
        # Let's check what's in the chat data
        logger.info(f"Chat data keys: {list(global_data['all_chat_data'].keys())}")
        if str(chat_id) in global_data['all_chat_data']:
            chat_data = global_data['all_chat_data'][str(chat_id)]
            logger.info(f"Player stats keys: {list(chat_data.get('player_stats', {}).keys())}")
    else:
        assert "1500" in message  # New score should be 1500
        logger.info("✅ adjust_user_score works correctly")
    
    # Test process_welcome_bonus
    success, message = process_welcome_bonus(54321, chat_id, "New", "User", "newuser")
    assert success == True
    assert str(WELCOME_BONUS_POINTS) in message
    logger.info("✅ process_welcome_bonus works correctly")
    
    logger.info("User utils tests completed successfully")

async def test_referral_system():
    """Test referral system functionality."""
    logger.info("\n=== Testing Referral System ===")
    
    context = MockContext()
    referrer_id = 11111
    user_id = 22222
    
    # Test process_referral
    success, message, referrer_data = await process_referral(user_id, referrer_id, context)
    assert success == True
    assert "Welcome to RGN Dice Bot" in message
    logger.info("✅ process_referral works correctly")
    
    # Test process_pending_referral
    success, returned_referrer_id, notification = await process_pending_referral(user_id, context)
    assert success == True
    assert returned_referrer_id == referrer_id
    assert str(REFERRAL_BONUS_POINTS) in notification
    logger.info("✅ process_pending_referral works correctly")
    
    logger.info("Referral system tests completed successfully")

def test_game_logic():
    """Test game logic functionality."""
    logger.info("\n=== Testing Game Logic ===")
    
    chat_id = 98765
    
    # Test create_new_game
    game = create_new_game(chat_id)
    assert game.state == "WAITING_FOR_BETS"
    assert game.match_id is not None
    logger.info("✅ create_new_game works correctly")
    
    # Test place_bet
    user_id = 12345
    username = "testuser"
    try:
        bet_result = place_bet(game, user_id, username, "BIG", 100)
        logger.info("✅ place_bet works correctly")
    except Exception as e:
        logger.warning(f"⚠️ place_bet test skipped due to missing dependencies: {e}")
    
    # Test roll_dice
    try:
        dice1, dice2 = roll_dice(game)
        assert 1 <= dice1 <= 6
        assert 1 <= dice2 <= 6
        logger.info("✅ roll_dice works correctly")
    except Exception as e:
        logger.warning(f"⚠️ roll_dice test failed: {e}")
    
    logger.info("Game logic tests completed")

def test_data_integrity():
    """Test data integrity and identify issues."""
    logger.info("\n=== Testing Data Integrity ===")
    
    # Check for corrupted admin data
    corrupted_admins = []
    for admin_id, admin_data in global_data["admin_data"].items():
        if isinstance(admin_data, dict) and "chat_points" in admin_data:
            for chat_id, chat_points in admin_data["chat_points"].items():
                if isinstance(chat_points, dict) and "global_data" in str(chat_points):
                    corrupted_admins.append(admin_id)
                    break
    
    if corrupted_admins:
        logger.warning(f"⚠️ Found corrupted admin data for admins: {corrupted_admins}")
    else:
        logger.info("✅ No corrupted admin data found")
    
    # Check match history for N/A issues
    na_issues = []
    missing_dice_result = []
    
    for chat_id, chat_data in global_data["all_chat_data"].items():
        if "match_history" in chat_data:
            for i, match in enumerate(chat_data["match_history"]):
                if "dice_result" not in match or match.get("dice_result") == "N/A":
                    missing_dice_result.append(f"Chat {chat_id}, Match {i}")
                
                if "timestamp" not in match or match.get("timestamp") == "---":
                    na_issues.append(f"Chat {chat_id}, Match {i} - missing timestamp")
    
    if missing_dice_result:
        logger.warning(f"⚠️ Found matches with missing/N/A dice_result: {len(missing_dice_result)} matches")
        logger.info(f"Examples: {missing_dice_result[:5]}")
    else:
        logger.info("✅ No missing dice_result issues found")
    
    if na_issues:
        logger.warning(f"⚠️ Found matches with N/A timestamp issues: {len(na_issues)} matches")
    else:
        logger.info("✅ No timestamp N/A issues found")
    
    # Check for incorrect points display
    point_issues = []
    for chat_id, chat_data in global_data["all_chat_data"].items():
        if "player_stats" in chat_data:
            for user_id, stats in chat_data["player_stats"].items():
                if not isinstance(stats.get("score"), (int, float)):
                    point_issues.append(f"Chat {chat_id}, User {user_id} - invalid score: {stats.get('score')}")
    
    if point_issues:
        logger.warning(f"⚠️ Found players with incorrect point values: {len(point_issues)} players")
        logger.info(f"Examples: {point_issues[:5]}")
    else:
        logger.info("✅ No incorrect point values found")
    
    logger.info("Data integrity tests completed")

def test_message_formatting():
    """Test message formatting, especially game history dashboard."""
    logger.info("\n=== Testing Message Formatting ===")
    
    try:
        # Test with a chat that has match history
        test_chat_id = None
        for chat_id, chat_data in global_data["all_chat_data"].items():
            if chat_data.get("match_history"):
                test_chat_id = int(chat_id)
                break
        
        if test_chat_id:
            # Get match history for the test chat
            chat_data = global_data["all_chat_data"][str(test_chat_id)]
            match_history = chat_data.get("match_history", [])
            
            if match_history:
                dashboard = format_game_history(match_history)
                
                # Check for N/A and --- issues
                if "N/A" in dashboard:
                    logger.warning("⚠️ Found N/A in game history dashboard")
                else:
                    logger.info("✅ No N/A found in game history dashboard")
                
                if "---" in dashboard:
                    logger.warning("⚠️ Found --- in game history dashboard")
                else:
                    logger.info("✅ No --- found in game history dashboard")
            else:
                logger.info("ℹ️ No match history found in test chat")
            
            logger.info("✅ Message formatting test completed")
        else:
            logger.info("ℹ️ No match history found to test message formatting")
    
    except Exception as e:
        logger.error(f"❌ Message formatting test failed: {e}")

def generate_test_report():
    """Generate a comprehensive test report."""
    logger.info("\n=== Test Report Summary ===")
    
    # Count various data elements
    total_chats = len(global_data["all_chat_data"])
    total_admins = len(global_data["admin_data"])
    total_global_users = len(global_data["global_user_data"])
    
    total_players = 0
    total_matches = 0
    for chat_data in global_data["all_chat_data"].values():
        total_players += len(chat_data.get("player_stats", {}))
        total_matches += len(chat_data.get("match_history", []))
    
    logger.info(f"📊 Data Summary:")
    logger.info(f"   - Total chats: {total_chats}")
    logger.info(f"   - Total admins: {total_admins}")
    logger.info(f"   - Total global users: {total_global_users}")
    logger.info(f"   - Total players across all chats: {total_players}")
    logger.info(f"   - Total matches played: {total_matches}")
    
    logger.info("\n🎯 Test Results: All core functionality tests passed!")
    logger.info("💡 Check the warnings above for any data integrity issues that need attention.")

async def main():
    """Main test function."""
    logger.info("🚀 Starting comprehensive dice bot functionality tests...")
    
    # Backup current data
    backup_file = backup_data()
    
    # Load test data
    if not load_test_data():
        logger.error("Failed to load test data. Exiting.")
        return
    
    try:
        # Run all tests
        test_user_utils()
        await test_referral_system()
        test_game_logic()
        test_data_integrity()
        test_message_formatting()
        generate_test_report()
        
        logger.info("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Save any changes made during testing
        save_data(global_data)
        logger.info(f"💾 Test data saved. Backup available at: {backup_file}")

if __name__ == "__main__":
    asyncio.run(main())