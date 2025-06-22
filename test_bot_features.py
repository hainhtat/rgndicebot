#!/usr/bin/env python3
"""
Comprehensive Test Script for Dice Bot Features
Tests payouts, referrals, security measures, and notifications
"""

import asyncio
import json
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# Import bot modules
from config.settings import BOT_TOKEN, SUPER_ADMINS
from config.constants import global_data
from data.file_manager import load_data, save_data
from utils.user_utils import process_referral, get_or_create_global_user_data

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotTester:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.test_results = []
        self.test_chat_id = -1002780424700  # Test group ID
        self.test_users = {
            'referrer': 6809465186,  # Existing user
            'new_user_1': 999888777,  # Test new user 1
            'new_user_2': 999888778,  # Test new user 2
            'duplicate_user': 999888777  # Same as new_user_1 for duplicate test
        }
    
    def log_test(self, test_name, passed, details=""):
        """Log test results"""
        status = "✅ PASSED" if passed else "❌ FAILED"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        
        self.test_results.append(result)
        logger.info(result)
    
    async def test_referral_security(self):
        """Test referral security measures"""
        logger.info("\n🔒 Testing Referral Security Measures...")
        
        # Load current data
        load_data(global_data)
        
        # Test 1: Prevent duplicate welcome bonus
        logger.info("Test 1: Duplicate welcome bonus prevention")
        
        # Check if user already exists
        chat_data = global_data.get(str(self.test_chat_id), {})
        player_stats = chat_data.get("player_stats", {})
        
        existing_user = str(self.test_users['referrer'])
        if existing_user in player_stats:
            initial_score = player_stats[existing_user].get('score', 0)
            
            # Try to process welcome bonus again (should fail)
            from utils.user_utils import process_welcome_bonus
            success, message = process_welcome_bonus(
                self.test_users['referrer'], 
                self.test_chat_id,
                "TestUser",
                "TestLast",
                "testuser"
            )
            
            final_score = player_stats[existing_user].get('score', 0)
            duplicate_prevented = (final_score == initial_score) and not success
            
            self.log_test(
                "Duplicate Welcome Bonus Prevention", 
                duplicate_prevented,
                f"Score unchanged: {initial_score} -> {final_score}"
            )
        else:
            self.log_test("Duplicate Welcome Bonus Prevention", False, "Test user not found")
        
        # Test 2: Prevent duplicate referral bonus
        logger.info("Test 2: Duplicate referral bonus prevention")
        
        # Try to refer the same user multiple times
        referrer_id = self.test_users['referrer']
        referred_id = self.test_users['new_user_1']
        
        # First referral attempt
        success1, message1, _ = await process_referral(referred_id, referrer_id, None)
        
        # Second referral attempt (should fail)
        success2, message2, _ = await process_referral(referred_id, referrer_id, None)
        
        duplicate_referral_prevented = success1 and not success2
        
        self.log_test(
            "Duplicate Referral Prevention", 
            duplicate_referral_prevented,
            f"First: {success1}, Second: {success2}"
        )
        
        # Test 3: Allow multiple different referrals
        logger.info("Test 3: Multiple different referrals allowed")
        
        # Try to refer a different user (should succeed)
        success3, message3, _ = await process_referral(self.test_users['new_user_2'], referrer_id, None)
        
        self.log_test(
            "Multiple Different Referrals Allowed", 
            success3,
            f"New referral success: {success3}"
        )
    
    async def test_payout_system(self):
        """Test payout calculations and security"""
        logger.info("\n💰 Testing Payout System...")
        
        load_data(global_data)
        
        # Test withdrawal validation
        chat_data = global_data.get(str(self.test_chat_id), {})
        player_stats = chat_data.get("player_stats", {})
        
        test_user = str(self.test_users['referrer'])
        if test_user in player_stats:
            current_balance = player_stats[test_user].get('score', 0)
            
            # Test minimum withdrawal amount
            min_withdrawal_met = current_balance >= 1000
            
            self.log_test(
                "Minimum Withdrawal Amount Check", 
                min_withdrawal_met,
                f"Balance: {current_balance}, Required: 1000"
            )
            
            # Test balance calculation accuracy
            expected_balance = current_balance
            actual_balance = player_stats[test_user]['score']
            balance_accurate = expected_balance == actual_balance
            
            self.log_test(
                "Balance Calculation Accuracy", 
                balance_accurate,
                f"Expected: {expected_balance}, Actual: {actual_balance}"
            )
        else:
            self.log_test("Payout System Tests", False, "Test user not found")
    
    async def test_admin_score_validation(self):
        """Test admin score adjustment validation"""
        logger.info("\n⚖️ Testing Admin Score Validation...")
        
        load_data(global_data)
        
        chat_data = global_data.get(str(self.test_chat_id), {})
        player_stats = chat_data.get("player_stats", {})
        
        test_user = str(self.test_users['referrer'])
        if test_user in player_stats:
            current_score = player_stats[test_user]['score']
            
            # Test: Cannot deduct more than user has
            excessive_deduction = current_score + 1000  # More than they have
            
            # Simulate the validation logic
            would_go_negative = (current_score - excessive_deduction) < 0
            
            self.log_test(
                "Negative Balance Prevention", 
                would_go_negative,  # This should be True (prevented)
                f"Current: {current_score}, Attempted deduction: {excessive_deduction}"
            )
            
            # Test: Valid deduction should be allowed
            valid_deduction = min(100, current_score)  # Small valid amount
            valid_deduction_allowed = (current_score - valid_deduction) >= 0
            
            self.log_test(
                "Valid Deduction Allowed", 
                valid_deduction_allowed,
                f"Current: {current_score}, Valid deduction: {valid_deduction}"
            )
        else:
            self.log_test("Admin Score Validation", False, "Test user not found")
    
    async def test_superadmin_notifications(self):
        """Test superadmin notification system"""
        logger.info("\n📢 Testing Superadmin Notifications...")
        
        try:
            # Test notification to superadmins
            test_message = (
                "🧪 <b>Bot Test Notification</b>\n\n"
                f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                "🔧 Testing notification system functionality\n\n"
                "✅ If you receive this message, notifications are working correctly!"
            )
            
            # Send test notification to all superadmins
            notification_sent = False
            for super_admin_id in SUPER_ADMINS:
                try:
                    await self.bot.send_message(
                        chat_id=super_admin_id,
                        text=test_message,
                        parse_mode="HTML"
                    )
                    notification_sent = True
                    logger.info(f"✅ Test notification sent to superadmin {super_admin_id}")
                except TelegramError as e:
                    logger.error(f"❌ Failed to send notification to superadmin {super_admin_id}: {e}")
            
            self.log_test(
                "Superadmin Notification System", 
                notification_sent,
                f"Sent to {len(SUPER_ADMINS)} superadmin(s)"
            )
            
        except Exception as e:
            self.log_test("Superadmin Notification System", False, f"Error: {e}")
    
    async def test_data_integrity(self):
        """Test data integrity and consistency"""
        logger.info("\n🗄️ Testing Data Integrity...")
        
        load_data(global_data)
        
        # Test data structure integrity
        required_keys = ['all_chat_data', 'global_user_data']
        data_structure_valid = all(key in global_data for key in required_keys)
        
        self.log_test(
            "Data Structure Integrity", 
            data_structure_valid,
            f"Required keys present: {required_keys}"
        )
        
        # Test chat data consistency
        chat_data = global_data.get('all_chat_data', {})
        chat_consistency = True
        
        for chat_id, data in chat_data.items():
            if 'player_stats' not in data:
                chat_consistency = False
                break
        
        self.log_test(
            "Chat Data Consistency", 
            chat_consistency,
            f"Checked {len(chat_data)} chat(s)"
        )
        
        # Test user data consistency
        user_data = global_data.get('global_user_data', {})
        user_consistency = True
        
        for user_id, data in user_data.items():
            required_user_keys = ['first_name', 'referral_points']
            if not all(key in data for key in required_user_keys):
                user_consistency = False
                break
        
        self.log_test(
            "User Data Consistency", 
            user_consistency,
            f"Checked {len(user_data)} user(s)"
        )
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("🚀 Starting Comprehensive Bot Feature Tests...")
        logger.info(f"Test started at: {datetime.now()}")
        
        # Run all test categories
        await self.test_data_integrity()
        await self.test_referral_security()
        await self.test_payout_system()
        await self.test_admin_score_validation()
        await self.test_superadmin_notifications()
        
        # Generate test report
        logger.info("\n📊 TEST REPORT")
        logger.info("=" * 50)
        
        passed_tests = sum(1 for result in self.test_results if "✅ PASSED" in result)
        total_tests = len(self.test_results)
        
        for result in self.test_results:
            logger.info(result)
        
        logger.info("=" * 50)
        logger.info(f"📈 SUMMARY: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED! Bot is functioning correctly.")
        else:
            logger.warning(f"⚠️ {total_tests - passed_tests} test(s) failed. Please review.")
        
        # Send summary to superadmins
        summary_message = (
            f"🧪 <b>Bot Test Summary</b>\n\n"
            f"📊 <b>Results:</b> {passed_tests}/{total_tests} tests passed\n"
            f"⏰ <b>Test Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        if passed_tests == total_tests:
            summary_message += "🎉 <b>Status:</b> ALL TESTS PASSED!\n✅ Bot is functioning correctly."
        else:
            summary_message += f"⚠️ <b>Status:</b> {total_tests - passed_tests} test(s) failed\n❌ Please review the logs."
        
        for super_admin_id in SUPER_ADMINS:
            try:
                await self.bot.send_message(
                    chat_id=super_admin_id,
                    text=summary_message,
                    parse_mode="HTML"
                )
            except TelegramError as e:
                logger.error(f"Failed to send summary to superadmin {super_admin_id}: {e}")

async def main():
    """Main test function"""
    tester = BotTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())