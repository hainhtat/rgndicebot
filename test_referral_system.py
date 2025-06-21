#!/usr/bin/env python3

"""
Test script to verify that the referral system works correctly for multiple users.
This tests that:
1. Multiple users can join via the same referral link
2. The referrer gets points for each new user
3. The same user cannot generate multiple referral bonuses
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import necessary modules
from config.constants import global_data
from data.file_manager import save_data, load_data
from config.settings import REFERRAL_BONUS_POINTS
from utils.user_utils import get_or_create_global_user_data, process_referral, process_pending_referral

# Mock context for testing
class MockBot:
    async def get_chat(self, chat_id):
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
                self.first_name = f"User{chat_id}"
                self.last_name = "Test"
                self.username = f"user{chat_id}"
                self.full_name = f"User{chat_id} Test"
        return MockChat(chat_id)

class MockContext:
    def __init__(self):
        self.bot = MockBot()

# Test functions
async def test_multiple_referrals():
    """
    Test that multiple users can join via the same referral link and the referrer gets points for each.
    """
    logger.info("\n=== Testing Multiple Referrals ===\n")
    
    # Load data
    load_data(global_data)
    
    # Create a mock context
    context = MockContext()
    
    # Create a referrer
    referrer_id = 1001
    get_or_create_global_user_data(referrer_id, "Referrer", "User", "referrer_user")
    
    # Initial referral points
    initial_points = global_data["global_user_data"][str(referrer_id)].get("referral_points", 0)
    logger.info(f"Initial referral points for referrer: {initial_points}")
    
    # Create multiple users who join via the referral link
    new_users = [1002, 1003, 1004]
    
    for i, user_id in enumerate(new_users):
        logger.info(f"\nProcessing user {user_id} (#{i+1})...")
        
        # Process the referral (simulates clicking the referral link)
        success, message, _ = await process_referral(user_id, referrer_id, context)
        logger.info(f"process_referral result: {success}, message: {message}")
        
        # Process the pending referral (simulates joining the group)
        success, ref_id, notification = await process_pending_referral(user_id, context)
        logger.info(f"process_pending_referral result: {success}, referrer_id: {ref_id}, notification: {notification}")
        
        # Check current points
        current_points = global_data["global_user_data"][str(referrer_id)].get("referral_points", 0)
        logger.info(f"Current referral points: {current_points}")
        
        # Verify points increased
        expected_points = initial_points + REFERRAL_BONUS_POINTS * (i + 1)
        assert current_points == expected_points, f"Expected {expected_points} points, got {current_points}"
    
    logger.info("\n✅ Multiple referrals test passed!")

async def test_duplicate_referral():
    """
    Test that the same user cannot generate multiple referral bonuses.
    """
    logger.info("\n=== Testing Duplicate Referral ===\n")
    
    # Create a mock context
    context = MockContext()
    
    # Create a referrer
    referrer_id = 2001
    get_or_create_global_user_data(referrer_id, "Referrer2", "User", "referrer_user2")
    
    # Create a user
    user_id = 2002
    get_or_create_global_user_data(user_id, "User2", "Test", "user2_test")
    
    # Initial referral points
    initial_points = global_data["global_user_data"][str(referrer_id)].get("referral_points", 0)
    logger.info(f"Initial referral points for referrer: {initial_points}")
    
    # First referral (should work)
    logger.info("\nProcessing first referral...")
    success1, message1, _ = await process_referral(user_id, referrer_id, context)
    logger.info(f"First process_referral result: {success1}, message: {message1}")
    
    success1_pending, ref_id1, notification1 = await process_pending_referral(user_id, context)
    logger.info(f"First process_pending_referral result: {success1_pending}, notification: {notification1}")
    
    # Check points after first referral
    points_after_first = global_data["global_user_data"][str(referrer_id)].get("referral_points", 0)
    logger.info(f"Points after first referral: {points_after_first}")
    
    # Try second referral with same user (should not work)
    logger.info("\nProcessing second referral with same user...")
    success2, message2, _ = await process_referral(user_id, referrer_id, context)
    logger.info(f"Second process_referral result: {success2}, message: {message2}")
    
    success2_pending, ref_id2, notification2 = await process_pending_referral(user_id, context)
    logger.info(f"Second process_pending_referral result: {success2_pending}, notification: {notification2}")
    
    # Check points after attempted second referral
    points_after_second = global_data["global_user_data"][str(referrer_id)].get("referral_points", 0)
    logger.info(f"Points after second referral attempt: {points_after_second}")
    
    # Verify points didn't increase on second attempt
    assert points_after_second == points_after_first, f"Points should not increase on duplicate referral. Expected {points_after_first}, got {points_after_second}"
    
    logger.info("\n✅ Duplicate referral test passed!")

async def main():
    logger.info("Starting referral system test suite...")
    
    # Run tests
    await test_multiple_referrals()
    await test_duplicate_referral()
    
    logger.info("\nAll referral system tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())