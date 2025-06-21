#!/usr/bin/env python3
"""
Simple test script to verify checkscore functionality
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

async def test_checkscore_functionality():
    """
    Test the checkscore functionality with proper data setup
    """
    print("🔧 Testing checkscore functionality...\n")
    
    # Load existing data
    load_data(global_data)
    print(f"📊 Loaded global_data keys: {list(global_data.keys())}")
    
    # Test chat ID
    test_chat_id = -1001234567890
    test_user_id = 123456789
    test_admin_id = 987654321
    
    # Get or create chat data
    chat_data = get_chat_data_for_id(test_chat_id)
    print(f"📋 Chat data structure: {list(chat_data.keys())}")
    print(f"📊 Player stats keys: {list(chat_data['player_stats'].keys())}")
    
    # Add a test user to player_stats
    chat_data['player_stats'][test_user_id] = {
        'score': 1500,
        'wins': 10,
        'losses': 5,
        'username': 'testuser',
        'referral_points': 50,
        'referred_by': None
    }
    
    # Add admin to group_admins
    if 'group_admins' not in chat_data:
        chat_data['group_admins'] = []
    chat_data['group_admins'].append(test_admin_id)
    
    print(f"✅ Added test user {test_user_id} to chat {test_chat_id}")
    print(f"📊 Player stats now: {list(chat_data['player_stats'].keys())}")
    
    # Create mock update and context objects
    class MockUser:
        def __init__(self, user_id, username=None):
            self.id = user_id
            self.username = username
            self.first_name = "Test"
            self.last_name = "User"
    
    class MockChat:
        def __init__(self, chat_id):
            self.id = chat_id
            self.type = "group"
    
    class MockMessage:
        def __init__(self, user_id, chat_id, text):
            self.from_user = MockUser(user_id)
            self.chat = MockChat(chat_id)
            self.text = text
            self.reply_to_message = None
            self.reply_text = AsyncMock()
            self.edit_text = AsyncMock()
    
    class MockUpdate:
        def __init__(self, user_id, chat_id, text):
            self.message = MockMessage(user_id, chat_id, text)
            self.effective_user = MockUser(user_id)
            self.effective_chat = MockChat(chat_id)
    
    class MockContext:
        def __init__(self):
            self.bot = AsyncMock()
            self.args = []
    
    # Test 1: Check existing user by ID
    print("\n📋 Test 1: Checking existing user by ID...")
    update = MockUpdate(test_admin_id, test_chat_id, f"/checkscore {test_user_id}")
    context = MockContext()
    context.args = [str(test_user_id)]
    
    # Mock the get_chat_member call
    mock_member = MagicMock()
    mock_member.user = MockUser(test_user_id, "testuser")
    context.bot.get_chat_member = AsyncMock(return_value=mock_member)
    
    try:
        await check_user_score(update, context)
        print("✅ Test 1 completed successfully")
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
    
    # Test 2: Check non-existing user
    print("\n📋 Test 2: Checking non-existing user...")
    non_existing_user_id = 999999999
    update = MockUpdate(test_admin_id, test_chat_id, f"/checkscore {non_existing_user_id}")
    context = MockContext()
    context.args = [str(non_existing_user_id)]
    
    try:
        await check_user_score(update, context)
        print("✅ Test 2 completed successfully")
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
    
    # Test 3: Check user by username
    print("\n📋 Test 3: Checking user by username...")
    update = MockUpdate(test_admin_id, test_chat_id, "/checkscore @testuser")
    context = MockContext()
    context.args = ["@testuser"]
    
    try:
        await check_user_score(update, context)
        print("✅ Test 3 completed successfully")
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
    
    print("\n🎯 All checkscore tests completed!")

if __name__ == "__main__":
    asyncio.run(test_checkscore_functionality())