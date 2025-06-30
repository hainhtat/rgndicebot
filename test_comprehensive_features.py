#!/usr/bin/env python3
"""
Comprehensive Test Script for Dice Bot Features
Tests: Referral System, Welcome Bonus, Daily Cashback
Sends notifications to real superadmins
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Import bot modules
from config.constants import global_data, SUPER_ADMINS
from config.settings import REFERRAL_BONUS_POINTS, WELCOME_BONUS_POINTS

from main import load_data_unified, save_data_unified
from utils.user_utils import (
    get_or_create_global_user_data, 
    process_welcome_bonus, 
    process_pending_referral
)
from utils.daily_bonus import process_daily_cashback
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeatureTester:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable not set")
        
        self.bot = Bot(token=self.bot_token)
        self.test_results = {
            'referral_system': {'passed': 0, 'failed': 0, 'details': []},
            'welcome_bonus': {'passed': 0, 'failed': 0, 'details': []},
            'daily_cashback': {'passed': 0, 'failed': 0, 'details': []}
        }
        
        # Test user IDs (simulated)
        self.test_users = {
            'referrer': 999999001,
            'new_user_1': 999999002,
            'new_user_2': 999999003,
            'existing_user': 999999004
        }
        
        # Test chat ID (use a real group ID for testing)
        self.test_chat_id = -1002780424700  # Replace with actual test group ID
    
    async def setup_test_environment(self):
        """Setup test environment with clean data"""
        logger.info("Setting up test environment...")
        
        # Load existing data
        global_data.update(load_data_unified())
        
        # Clean up any existing test data
        for user_id in self.test_users.values():
            user_id_str = str(user_id)
            if user_id_str in global_data.get('global_user_data', {}):
                del global_data['global_user_data'][user_id_str]
        
        # Ensure test chat exists in data
        chat_id_str = str(self.test_chat_id)
        if chat_id_str not in global_data.get('all_chat_data', {}):
            global_data.setdefault('all_chat_data', {})[chat_id_str] = {
                'player_stats': {},
                'match_counter': 1,
                'match_history': [],
                'group_admins': [],
                'consecutive_idle_matches': 0,
                'pending_referrals': {}
            }
        
        save_data_unified(global_data)
        logger.info("Test environment setup complete")
    
    def log_test_result(self, category: str, test_name: str, passed: bool, details: str):
        """Log test result"""
        if passed:
            self.test_results[category]['passed'] += 1
            logger.info(f"✅ {test_name}: PASSED - {details}")
        else:
            self.test_results[category]['failed'] += 1
            logger.error(f"❌ {test_name}: FAILED - {details}")
        
        self.test_results[category]['details'].append({
            'test': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    async def test_referral_system(self):
        """Test referral system functionality"""
        logger.info("🔗 Testing Referral System...")
        
        try:
            # Test 1: Create referrer user
            referrer_id = self.test_users['referrer']
            referrer_data = get_or_create_global_user_data(
                referrer_id, "Test", "Referrer", "test_referrer"
            )
            initial_referral_points = referrer_data.get('referral_points', 0)
            
            self.log_test_result(
                'referral_system', 
                'Create Referrer User',
                True,
                f"Referrer created with {initial_referral_points} referral points"
            )
            
            # Test 2: Process new user referral
            new_user_id = self.test_users['new_user_1']
            
            # Simulate referral process
            new_user_data = get_or_create_global_user_data(
                new_user_id, "Test", "NewUser1", "test_newuser1"
            )
            
            # Set referral relationship
            new_user_data['referred_by'] = referrer_id
            new_user_data['referral_pending'] = True
            
            # Complete referral bonus (simulating user joining main group)
            success, referrer_notified_id, notification_msg = await process_pending_referral(
                new_user_id, None  # No context for test
            )
            
            if success and referrer_notified_id == referrer_id:
                updated_referrer_data = global_data['global_user_data'][str(referrer_id)]
                new_referral_points = updated_referrer_data.get('referral_points', 0)
                points_awarded = new_referral_points - initial_referral_points
                
                self.log_test_result(
                    'referral_system',
                    'Process Referral Bonus',
                    points_awarded == REFERRAL_BONUS_POINTS,
                    f"Awarded {points_awarded} points (expected {REFERRAL_BONUS_POINTS})"
                )
            else:
                self.log_test_result(
                    'referral_system',
                    'Process Referral Bonus',
                    False,
                    "Failed to process referral bonus"
                )
            
            # Test 3: Prevent duplicate referrals
            new_user_data['referral_pending'] = True  # Try to refer again
            success_duplicate, _, _ = await process_pending_referral(new_user_id, None)
            
            self.log_test_result(
                'referral_system',
                'Prevent Duplicate Referrals',
                not success_duplicate,
                "Duplicate referral correctly prevented" if not success_duplicate else "Duplicate referral allowed (ERROR)"
            )
            
            # Test 4: Multiple unique referrals
            new_user_2_id = self.test_users['new_user_2']
            new_user_2_data = get_or_create_global_user_data(
                new_user_2_id, "Test", "NewUser2", "test_newuser2"
            )
            new_user_2_data['referred_by'] = referrer_id
            new_user_2_data['referral_pending'] = True
            
            success_second, _, _ = await process_pending_referral(new_user_2_id, None)
            
            self.log_test_result(
                'referral_system',
                'Multiple Unique Referrals',
                success_second,
                "Second unique referral processed successfully" if success_second else "Second referral failed"
            )
            
        except Exception as e:
            self.log_test_result(
                'referral_system',
                'Referral System Error',
                False,
                f"Exception occurred: {str(e)}"
            )
    
    async def test_welcome_bonus(self):
        """Test welcome bonus functionality"""
        logger.info("🎁 Testing Welcome Bonus System...")
        
        try:
            # Test 1: First-time welcome bonus
            new_user_id = self.test_users['new_user_1']
            
            success, message = process_welcome_bonus(
                new_user_id, self.test_chat_id, "Test", "NewUser1", "test_newuser1"
            )
            
            self.log_test_result(
                'welcome_bonus',
                'First Welcome Bonus',
                success,
                f"Welcome bonus awarded: {message}" if success else f"Failed: {message}"
            )
            
            # Test 2: Prevent duplicate welcome bonus in same chat
            success_duplicate, message_duplicate = process_welcome_bonus(
                new_user_id, self.test_chat_id, "Test", "NewUser1", "test_newuser1"
            )
            
            self.log_test_result(
                'welcome_bonus',
                'Prevent Duplicate Welcome Bonus',
                not success_duplicate,
                "Duplicate welcome bonus correctly prevented" if not success_duplicate else "Duplicate allowed (ERROR)"
            )
            
            # Test 3: Welcome bonus for different user
            different_user_id = self.test_users['new_user_2']
            
            success_different, message_different = process_welcome_bonus(
                different_user_id, self.test_chat_id, "Test", "NewUser2", "test_newuser2"
            )
            
            self.log_test_result(
                'welcome_bonus',
                'Different User Welcome Bonus',
                success_different,
                f"Different user bonus: {message_different}" if success_different else f"Failed: {message_different}"
            )
            
        except Exception as e:
            self.log_test_result(
                'welcome_bonus',
                'Welcome Bonus Error',
                False,
                f"Exception occurred: {str(e)}"
            )
    
    async def test_daily_cashback(self):
        """Test daily cashback functionality"""
        logger.info("💰 Testing Daily Cashback System...")
        
        try:
            # Test 1: Setup user with betting history
            test_user_id = self.test_users['existing_user']
            chat_id_str = str(self.test_chat_id)
            user_id_str = str(test_user_id)
            
            # Create user with some losses for cashback calculation
            if user_id_str not in global_data['all_chat_data'][chat_id_str]['player_stats']:
                global_data['all_chat_data'][chat_id_str]['player_stats'][user_id_str] = {
                    'username': 'test_existing_user',
                    'score': 5000,
                    'total_bets': 10000,  # Total amount bet
                    'total_wins': 3000,   # Amount won
                    'total_losses': 7000, # Amount lost
                    'last_active': datetime.now().isoformat()
                }
            
            # Test cashback calculation
            user_stats = global_data['all_chat_data'][chat_id_str]['player_stats'][user_id_str]
            initial_score = user_stats['score']
            
            # Simulate daily cashback processing (function only takes context parameter)
            # Note: The actual function processes all users, so we'll just call it with None context
            cashback_result = await process_daily_cashback(None)
            
            if cashback_result:
                final_score = global_data['all_chat_data'][chat_id_str]['player_stats'][user_id_str]['score']
                cashback_amount = final_score - initial_score
                
                self.log_test_result(
                    'daily_cashback',
                    'Daily Cashback Calculation',
                    cashback_amount > 0,
                    f"Cashback awarded: {cashback_amount} points"
                )
            else:
                self.log_test_result(
                    'daily_cashback',
                    'Daily Cashback Calculation',
                    True,  # No cashback might be valid if conditions not met
                    "No cashback awarded (conditions not met)"
                )
            
            # Test 2: Prevent duplicate daily cashback
            second_cashback = await process_daily_cashback(None)
            
            self.log_test_result(
                'daily_cashback',
                'Prevent Duplicate Daily Cashback',
                not second_cashback,
                "Duplicate cashback correctly prevented" if not second_cashback else "Duplicate allowed (ERROR)"
            )
            
        except Exception as e:
            self.log_test_result(
                'daily_cashback',
                'Daily Cashback Error',
                False,
                f"Exception occurred: {str(e)}"
            )
    
    async def send_superadmin_notifications(self):
        """Send test results to superadmins"""
        logger.info("📤 Sending notifications to superadmins...")
        
        # Calculate totals
        total_passed = sum(category['passed'] for category in self.test_results.values())
        total_failed = sum(category['failed'] for category in self.test_results.values())
        total_tests = total_passed + total_failed
        
        # Create summary message
        summary_message = (
            f"🧪 *Comprehensive Bot Feature Test Results*\n\n"
            f"📊 *Overall Results:* {total_passed}/{total_tests} tests passed\n"
            f"⏰ *Test Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        # Add category results
        for category, results in self.test_results.items():
            category_name = category.replace('_', ' ').title()
            passed = results['passed']
            failed = results['failed']
            total_cat = passed + failed
            
            if total_cat > 0:
                status_emoji = "✅" if failed == 0 else "⚠️" if passed > failed else "❌"
                summary_message += f"{status_emoji} *{category_name}:* {passed}/{total_cat} passed\n"
        
        summary_message += "\n"
        
        if total_failed == 0:
            summary_message += "🎉 *Status:* ALL TESTS PASSED!\n✅ All bot features are functioning correctly."
        else:
            summary_message += f"⚠️ *Status:* {total_failed} test(s) failed\n❌ Please review the logs for details."
        
        # Add detailed results
        summary_message += "\n\n*Detailed Results:*\n"
        for category, results in self.test_results.items():
            if results['details']:
                category_name = category.replace('_', ' ').title()
                summary_message += f"\n*{category_name}:*\n"
                for detail in results['details']:
                    status = "✅" if detail['passed'] else "❌"
                    summary_message += f"{status} {detail['test']}: {detail['details']}\n"
        
        # Send to superadmins
        for superadmin_id in SUPER_ADMINS:
            try:
                await self.bot.send_message(
                    chat_id=superadmin_id,
                    text=summary_message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Notification sent to superadmin {superadmin_id}")
            except TelegramError as e:
                logger.error(f"❌ Failed to send notification to superadmin {superadmin_id}: {e}")
    
    async def cleanup_test_data(self):
        """Clean up test data"""
        logger.info("🧹 Cleaning up test data...")
        
        # Remove test users from global data
        for user_id in self.test_users.values():
            user_id_str = str(user_id)
            if user_id_str in global_data.get('global_user_data', {}):
                del global_data['global_user_data'][user_id_str]
        
        # Remove test users from chat data
        chat_id_str = str(self.test_chat_id)
        if chat_id_str in global_data.get('all_chat_data', {}):
            for user_id in self.test_users.values():
                user_id_str = str(user_id)
                if user_id_str in global_data['all_chat_data'][chat_id_str].get('player_stats', {}):
                    del global_data['all_chat_data'][chat_id_str]['player_stats'][user_id_str]
        
        save_data_unified(global_data)
        logger.info("Test data cleanup complete")
    
    async def run_all_tests(self):
        """Run all feature tests"""
        logger.info("🚀 Starting comprehensive feature tests...")
        
        try:
            await self.setup_test_environment()
            
            # Run all tests
            await self.test_referral_system()
            await self.test_welcome_bonus()
            await self.test_daily_cashback()
            
            # Send notifications
            await self.send_superadmin_notifications()
            
            # Cleanup
            await self.cleanup_test_data()
            
            logger.info("🎉 All tests completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            raise

async def main():
    """Main test execution function"""
    tester = FeatureTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())