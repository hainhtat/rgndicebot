#!/usr/bin/env python3
"""
Comprehensive test script to verify checkscore functionality and markdown formatting
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
from config.constants import global_data, get_chat_data_for_id
from handlers.admin_handlers import check_user_score
from data.file_manager import load_data
from utils.message_formatter import MessageTemplates

class TestResults:
    def __init__(self):
        self.captured_messages = []
        self.test_results = []
    
    def capture_message(self, message):
        self.captured_messages.append(message)
        print(f"📤 Captured message: {message[:100]}..." if len(message) > 100 else f"📤 Captured message: {message}")
    
    def add_result(self, test_name, passed, details=""):
        self.test_results.append({
            'name': test_name,
            'passed': passed,
            'details': details
        })
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")

async def test_checkscore_comprehensive():
    """
    Comprehensive test of checkscore functionality with output capture
    """
    print("🔧 Comprehensive checkscore testing...\n")
    
    results = TestResults()
    
    # Load existing data
    load_data(global_data)
    print(f"📊 Loaded global_data keys: {list(global_data.keys())}")
    
    # Test chat ID
    test_chat_id = -1001234567890
    test_user_id = 123456789
    test_admin_id = 1599213796  # Use actual super admin ID
    
    # Get or create chat data
    chat_data = get_chat_data_for_id(test_chat_id)
    print(f"📋 Chat data structure: {list(chat_data.keys())}")
    print(f"📊 Existing player stats: {list(chat_data['player_stats'].keys())}")
    
    # Add a comprehensive test user to player_stats
    chat_data['player_stats'][test_user_id] = {
        'score': 2500,
        'wins': 15,
        'losses': 8,
        'username': 'testuser',
        'referral_points': 75,
        'referred_by': 111111111
    }
    
    # Add admin to group_admins
    if 'group_admins' not in chat_data:
        chat_data['group_admins'] = []
    if test_admin_id not in chat_data['group_admins']:
        chat_data['group_admins'].append(test_admin_id)
    
    print(f"✅ Added test user {test_user_id} to chat {test_chat_id}")
    
    # Create mock objects with message capture
    class MockUser:
        def __init__(self, user_id, username=None):
            self.id = user_id
            self.username = username
            self.first_name = "Test"
            self.last_name = "User"
            self.full_name = f"{self.first_name} {self.last_name}"
    
    class MockChat:
        def __init__(self, chat_id):
            self.id = chat_id
            self.type = "group"
    
    class MockMessage:
        def __init__(self, user_id, chat_id, text, results_obj):
            self.from_user = MockUser(user_id)
            self.chat = MockChat(chat_id)
            self.text = text
            self.reply_to_message = None
            self.results = results_obj
            
        async def reply_text(self, text, parse_mode=None, **kwargs):
            self.results.capture_message(text)
            return MagicMock()
            
        async def edit_text(self, text, parse_mode=None, **kwargs):
            self.results.capture_message(text)
            return MagicMock()
    
    class MockUpdate:
        def __init__(self, user_id, chat_id, text, results_obj):
            self.message = MockMessage(user_id, chat_id, text, results_obj)
            self.effective_user = MockUser(user_id)
            self.effective_chat = MockChat(chat_id)
    
    class MockContext:
        def __init__(self):
            self.bot = AsyncMock()
            self.args = []
    
    # Test 1: Check existing user by ID
    print("\n📋 Test 1: Checking existing user by ID...")
    update = MockUpdate(test_admin_id, test_chat_id, f"/checkscore {test_user_id}", results)
    context = MockContext()
    context.args = [str(test_user_id)]
    
    # Mock the get_chat_member call
    mock_member = MagicMock()
    mock_member.user = MockUser(test_user_id, "testuser")
    context.bot.get_chat_member = AsyncMock(return_value=mock_member)
    
    try:
        await check_user_score(update, context)
        
        # Verify the response contains expected elements
        if results.captured_messages:
            message = results.captured_messages[-1]
            expected_elements = ['User Information', 'Player:', 'Wins:', 'Losses:', 'Wallet:', 'Referral Points:']
            found_elements = [elem for elem in expected_elements if elem in message]
            missing_elements = [elem for elem in expected_elements if elem not in message]
            
            if len(found_elements) == len(expected_elements):
                results.add_result("Test 1: Existing user by ID", True, f"Found all expected elements: {found_elements}")
                print(f"📊 Full message:\n{message}")
            else:
                results.add_result("Test 1: Existing user by ID", False, f"Missing elements: {missing_elements}")
        else:
            results.add_result("Test 1: Existing user by ID", False, "No message captured")
            
    except Exception as e:
        results.add_result("Test 1: Existing user by ID", False, f"Exception: {e}")
    
    # Test 2: Check non-existing user
    print("\n📋 Test 2: Checking non-existing user...")
    non_existing_user_id = 999999999
    update = MockUpdate(test_admin_id, test_chat_id, f"/checkscore {non_existing_user_id}", results)
    context = MockContext()
    context.args = [str(non_existing_user_id)]
    
    try:
        await check_user_score(update, context)
        
        # Verify the response is the correct error message
        if results.captured_messages:
            message = results.captured_messages[-1]
            if MessageTemplates.USER_NOT_IN_RECORDS in message:
                results.add_result("Test 2: Non-existing user", True, "Correct error message")
            else:
                results.add_result("Test 2: Non-existing user", False, f"Unexpected message: {message}")
        else:
            results.add_result("Test 2: Non-existing user", False, "No message captured")
            
    except Exception as e:
        results.add_result("Test 2: Non-existing user", False, f"Exception: {e}")
    
    # Test 3: Check user by username
    print("\n📋 Test 3: Checking user by username...")
    update = MockUpdate(test_admin_id, test_chat_id, "/checkscore @testuser", results)
    context = MockContext()
    context.args = ["@testuser"]
    
    # Mock the get_chat_member call for username lookup
    mock_member_username = MagicMock()
    mock_member_username.user = MockUser(test_user_id, "testuser")
    context.bot.get_chat_member = AsyncMock(return_value=mock_member_username)
    
    try:
        await check_user_score(update, context)
        
        # Verify the response contains expected elements
        if results.captured_messages:
            message = results.captured_messages[-1]
            expected_elements = ['User Information', 'Player:', 'Wins:', 'Losses:', 'Wallet:']
            found_elements = [elem for elem in expected_elements if elem in message]
            
            if len(found_elements) >= 4:  # Allow some flexibility
                results.add_result("Test 3: User by username", True, f"Found elements: {found_elements}")
            else:
                results.add_result("Test 3: User by username", False, f"Found only: {found_elements}")
        else:
            results.add_result("Test 3: User by username", False, "No message captured")
            
    except Exception as e:
        results.add_result("Test 3: User by username", False, f"Exception: {e}")
    
    # Test 4: Check non-existing username
    print("\n📋 Test 4: Checking non-existing username...")
    update = MockUpdate(test_admin_id, test_chat_id, "/checkscore @nonexistentuser", results)
    context = MockContext()
    context.args = ["@nonexistentuser"]
    
    try:
        await check_user_score(update, context)
        
        # Verify the response is the correct error message
        if results.captured_messages:
            message = results.captured_messages[-1]
            if "not found" in message.lower():
                results.add_result("Test 4: Non-existing username", True, "Correct error message")
            else:
                results.add_result("Test 4: Non-existing username", False, f"Unexpected message: {message}")
        else:
            results.add_result("Test 4: Non-existing username", False, "No message captured")
            
    except Exception as e:
        results.add_result("Test 4: Non-existing username", False, f"Exception: {e}")
    
    # Summary
    print("\n" + "="*50)
    print("🎯 COMPREHENSIVE CHECKSCORE TEST RESULTS")
    print("="*50)
    
    passed_tests = sum(1 for result in results.test_results if result['passed'])
    total_tests = len(results.test_results)
    
    for result in results.test_results:
        status = "✅" if result['passed'] else "❌"
        print(f"{status} {result['name']}")
        if result['details']:
            print(f"   {result['details']}")
    
    print(f"\n📊 Summary: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Checkscore functionality is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the results above.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(test_checkscore_comprehensive())
    sys.exit(0 if success else 1)