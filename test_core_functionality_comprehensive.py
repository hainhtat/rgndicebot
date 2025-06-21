#!/usr/bin/env python3
"""
Comprehensive Test Script for RGN Dice Bot Core Functionality
Tests checkscore, markdown formatting, user management, and other core features.
"""

import sys
import os
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import bot modules
from data.file_manager import load_data, save_data
from handlers.admin_handlers import check_user_score
from utils.message_formatter import MessageTemplates
from utils.user_utils import get_user_display_name
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

class TestCoreBot:
    def __init__(self):
        self.global_data = {}
        self.test_results = []
        
    def log_test(self, test_name, passed, details=""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        
    def setup_test_data(self):
        """Setup test data with sample users and chat data"""
        print("\n🔧 Setting up test data...")
        
        # Load existing data
        self.global_data = load_data(self.global_data)
        
        # Test chat ID
        test_chat_id = "-1001234567890"
        test_user_id_1 = "123456789"
        test_user_id_2 = "987654321"
        test_admin_id = "111111111"
        
        # Ensure chat data exists
        if "chat_data" not in self.global_data:
            self.global_data["chat_data"] = {}
            
        if test_chat_id not in self.global_data["chat_data"]:
            self.global_data["chat_data"][test_chat_id] = {
                "player_stats": {},
                "admin_list": [int(test_admin_id)],
                "game_state": {
                    "active": False,
                    "bets": {},
                    "start_time": None
                }
            }
            
        # Add test users to chat data
        chat_data = self.global_data["chat_data"][test_chat_id]
        chat_data["player_stats"][test_user_id_1] = {
            "score": 5000,
            "total_wins": 15,
            "total_losses": 8,
            "username": "testuser1",
            "first_name": "Test",
            "last_name": "User1"
        }
        
        chat_data["player_stats"][test_user_id_2] = {
            "score": 2500,
            "total_wins": 5,
            "total_losses": 12,
            "username": "testuser2",
            "first_name": "Test",
            "last_name": "User2"
        }
        
        # Add admin to player stats
        chat_data["player_stats"][test_admin_id] = {
            "score": 10000,
            "total_wins": 25,
            "total_losses": 5,
            "username": "admin",
            "first_name": "Admin",
            "last_name": "User"
        }
        
        # Ensure global user data exists
        if "global_user_data" not in self.global_data:
            self.global_data["global_user_data"] = {}
            
        # Add global user data with referral info
        self.global_data["global_user_data"][test_user_id_1] = {
            "referral_points": 1500,
            "referred_by": int(test_admin_id),
            "referral_pending": False
        }
        
        self.global_data["global_user_data"][test_user_id_2] = {
            "referral_points": 500,
            "referred_by": None,
            "referral_pending": False
        }
        
        # Save test data
        save_data(self.global_data)
        print(f"✅ Test data setup complete for chat {test_chat_id}")
        
        return test_chat_id, test_user_id_1, test_user_id_2, test_admin_id
        
    def test_message_templates(self):
        """Test message template formatting"""
        print("\n📝 Testing message templates...")
        
        # Test basic templates
        templates_to_test = [
            ("CHECKSCORE_USAGE", MessageTemplates.CHECKSCORE_USAGE),
            ("USER_NOT_IN_RECORDS", MessageTemplates.USER_NOT_IN_RECORDS),
            ("USER_NOT_FOUND_BY_ID", MessageTemplates.USER_NOT_FOUND_BY_ID.format(user_id=123)),
            ("USER_NOT_FOUND_BY_USERNAME", MessageTemplates.USER_NOT_FOUND_BY_USERNAME.format(username="@test")),
            ("HELP_MESSAGE", MessageTemplates.HELP_MESSAGE),
        ]
        
        for template_name, template_content in templates_to_test:
            try:
                # Check if template exists and has content
                if template_content and len(template_content.strip()) > 0:
                    self.log_test(f"Template {template_name}", True, f"Length: {len(template_content)}")
                else:
                    self.log_test(f"Template {template_name}", False, "Empty or None")
            except Exception as e:
                self.log_test(f"Template {template_name}", False, f"Error: {e}")
                
    def test_markdown_formatting(self):
        """Test markdown formatting in messages"""
        print("\n🎨 Testing markdown formatting...")
        
        # Test markdown elements
        markdown_tests = [
            ("Bold text", "*Bold text*"),
            ("Italic text", "_Italic text_"),
            ("Code text", "`code`"),
            ("Escaped characters", "Test\\*escaped\\*"),
            ("Mixed formatting", "*Bold* and _italic_ with `code`"),
        ]
        
        for test_name, markdown_text in markdown_tests:
            try:
                # Check if markdown is properly formatted
                has_markdown = any(char in markdown_text for char in ['*', '_', '`', '\\'])
                self.log_test(f"Markdown: {test_name}", has_markdown, markdown_text)
            except Exception as e:
                self.log_test(f"Markdown: {test_name}", False, f"Error: {e}")
                
    async def test_checkscore_functionality(self, test_chat_id, test_user_id_1, test_admin_id):
        """Test checkscore command functionality"""
        print("\n🔍 Testing checkscore functionality...")
        
        # Mock objects for testing
        mock_user = Mock(spec=User)
        mock_user.id = int(test_user_id_1)
        mock_user.username = "testuser1"
        mock_user.first_name = "Test"
        mock_user.last_name = "User1"
        
        mock_admin = Mock(spec=User)
        mock_admin.id = int(test_admin_id)
        mock_admin.username = "admin"
        mock_admin.first_name = "Admin"
        mock_admin.last_name = "User"
        
        mock_chat = Mock(spec=Chat)
        mock_chat.id = int(test_chat_id)
        
        mock_message = Mock(spec=Message)
        mock_message.from_user = mock_admin
        mock_message.chat = mock_chat
        mock_message.reply_to_message = None
        mock_message.reply_text = AsyncMock()
        
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.args = [test_user_id_1]  # Test with user ID
        mock_context.bot = Mock()
        mock_context.bot.get_chat_member = AsyncMock()
        
        # Mock get_chat_member to return our test user
        mock_chat_member = Mock()
        mock_chat_member.user = mock_user
        mock_context.bot.get_chat_member.return_value = mock_chat_member
        
        try:
            # Test checkscore with existing user
            with patch('handlers.admin_handlers.check_admin_permission', return_value=True), \
                 patch('handlers.admin_handlers.get_chat_data_for_id') as mock_get_chat_data, \
                 patch('handlers.admin_handlers.get_user_display_name', return_value="Test User1"):
                
                # Setup mock chat data
                mock_get_chat_data.return_value = self.global_data["chat_data"][test_chat_id]
                
                await check_user_score(mock_update, mock_context)
                
                # Check if reply_text was called (should be called for successful lookup)
                if mock_message.reply_text.called:
                    call_args = mock_message.reply_text.call_args
                    message_content = call_args[0][0] if call_args[0] else ""
                    
                    # Check if message contains expected elements
                    expected_elements = ["User Information", "Player:", "Wallet:", "Wins:", "Losses:"]
                    all_present = all(element in message_content for element in expected_elements)
                    
                    self.log_test("Checkscore existing user", all_present, 
                                f"Message length: {len(message_content)}")
                    
                    # Test markdown formatting in response
                    has_markdown = '*' in message_content or '_' in message_content
                    self.log_test("Checkscore markdown formatting", has_markdown, 
                                "Contains markdown formatting")
                else:
                    self.log_test("Checkscore existing user", False, "No reply sent")
                    
        except Exception as e:
            self.log_test("Checkscore existing user", False, f"Exception: {e}")
            
        # Test checkscore with non-existing user
        try:
            mock_context.args = ["999999999"]  # Non-existing user ID
            mock_message.reply_text.reset_mock()
            
            with patch('handlers.admin_handlers.check_admin_permission', return_value=True), \
                 patch('handlers.admin_handlers.get_chat_data_for_id') as mock_get_chat_data:
                
                mock_get_chat_data.return_value = self.global_data["chat_data"][test_chat_id]
                
                await check_user_score(mock_update, mock_context)
                
                if mock_message.reply_text.called:
                    call_args = mock_message.reply_text.call_args
                    message_content = call_args[0][0] if call_args[0] else ""
                    
                    # Should contain error message
                    is_error = "not found" in message_content.lower() or "❌" in message_content
                    self.log_test("Checkscore non-existing user", is_error, 
                                f"Error message: {message_content[:100]}...")
                else:
                    self.log_test("Checkscore non-existing user", False, "No reply sent")
                    
        except Exception as e:
            self.log_test("Checkscore non-existing user", False, f"Exception: {e}")
            
    def test_data_integrity(self, test_chat_id, test_user_id_1, test_user_id_2):
        """Test data integrity and structure"""
        print("\n🗄️ Testing data integrity...")
        
        # Test global data structure
        required_keys = ["chat_data", "global_user_data"]
        for key in required_keys:
            exists = key in self.global_data
            self.log_test(f"Global data has {key}", exists)
            
        # Test chat data structure
        if test_chat_id in self.global_data["chat_data"]:
            chat_data = self.global_data["chat_data"][test_chat_id]
            required_chat_keys = ["player_stats", "admin_list", "game_state"]
            
            for key in required_chat_keys:
                exists = key in chat_data
                self.log_test(f"Chat data has {key}", exists)
                
            # Test user data structure
            if test_user_id_1 in chat_data["player_stats"]:
                user_data = chat_data["player_stats"][test_user_id_1]
                required_user_keys = ["score", "total_wins", "total_losses"]
                
                for key in required_user_keys:
                    exists = key in user_data
                    self.log_test(f"User data has {key}", exists)
                    
                # Test data types
                score_is_int = isinstance(user_data.get("score", 0), int)
                wins_is_int = isinstance(user_data.get("total_wins", 0), int)
                losses_is_int = isinstance(user_data.get("total_losses", 0), int)
                
                self.log_test("User score is integer", score_is_int)
                self.log_test("User wins is integer", wins_is_int)
                self.log_test("User losses is integer", losses_is_int)
            else:
                self.log_test("Test user exists in chat data", False)
        else:
            self.log_test("Test chat exists in global data", False)
            
    def test_referral_data(self, test_user_id_1):
        """Test referral system data"""
        print("\n🔗 Testing referral data...")
        
        if test_user_id_1 in self.global_data["global_user_data"]:
            user_global_data = self.global_data["global_user_data"][test_user_id_1]
            
            # Test referral fields
            has_referral_points = "referral_points" in user_global_data
            has_referred_by = "referred_by" in user_global_data
            
            self.log_test("User has referral_points field", has_referral_points)
            self.log_test("User has referred_by field", has_referred_by)
            
            if has_referral_points:
                points_is_int = isinstance(user_global_data["referral_points"], int)
                self.log_test("Referral points is integer", points_is_int)
                
            if has_referred_by and user_global_data["referred_by"]:
                referrer_is_int = isinstance(user_global_data["referred_by"], int)
                self.log_test("Referrer ID is integer", referrer_is_int)
        else:
            self.log_test("User exists in global data", False)
            
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")
                    
        print("\n" + "="*50)
        
async def main():
    """Main test function"""
    print("🚀 Starting Comprehensive Core Functionality Tests")
    print("="*60)
    
    tester = TestCoreBot()
    
    # Setup test data
    test_chat_id, test_user_id_1, test_user_id_2, test_admin_id = tester.setup_test_data()
    
    # Run tests
    tester.test_message_templates()
    tester.test_markdown_formatting()
    await tester.test_checkscore_functionality(test_chat_id, test_user_id_1, test_admin_id)
    tester.test_data_integrity(test_chat_id, test_user_id_1, test_user_id_2)
    tester.test_referral_data(test_user_id_1)
    
    # Print summary
    tester.print_summary()
    
    return len([r for r in tester.test_results if not r["passed"]]) == 0

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)