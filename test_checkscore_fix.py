#!/usr/bin/env python3
"""
Test script specifically for checkscore functionality
"""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import bot modules
from data.file_manager import load_data, save_data
from handlers.admin_handlers import check_user_score
from utils.message_formatter import MessageTemplates
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

async def test_checkscore():
    """Test checkscore functionality"""
    print("🔍 Testing checkscore functionality...")
    
    # Setup test data
    global_data = {}
    global_data = load_data(global_data)
    
    test_chat_id = "-1001234567890"
    test_user_id = "123456789"
    non_existing_user_id = "999999999"
    test_admin_id = "111111111"
    
    # Ensure proper data structure
    if "all_chat_data" not in global_data:
        global_data["all_chat_data"] = {}
        
    if test_chat_id not in global_data["all_chat_data"]:
        global_data["all_chat_data"][test_chat_id] = {
            "player_stats": {},
            "match_counter": 1,
            "match_history": [],
            "group_admins": [int(test_admin_id)],
            "consecutive_idle_matches": 0
        }
        
    # Add test user
    chat_data = global_data["all_chat_data"][test_chat_id]
    chat_data["player_stats"][test_user_id] = {
        "score": 5000,
        "total_wins": 15,
        "total_losses": 8,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User"
    }
    
    # Add admin
    chat_data["player_stats"][test_admin_id] = {
        "score": 10000,
        "total_wins": 25,
        "total_losses": 5,
        "username": "admin",
        "first_name": "Admin",
        "last_name": "User"
    }
    
    # Ensure global user data
    if "global_user_data" not in global_data:
        global_data["global_user_data"] = {}
        
    global_data["global_user_data"][test_user_id] = {
        "referral_points": 1500,
        "referred_by": int(test_admin_id),
        "referral_pending": False
    }
    
    save_data(global_data)
    
    # Mock objects
    mock_user = Mock(spec=User)
    mock_user.id = int(test_user_id)
    mock_user.username = "testuser"
    mock_user.first_name = "Test"
    mock_user.last_name = "User"
    
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
    mock_context.bot = Mock()
    mock_context.bot.get_chat_member = AsyncMock()
    
    # Test 1: Existing user
    print("\n📋 Test 1: Checking existing user...")
    mock_context.args = [test_user_id]
    mock_chat_member = Mock()
    mock_chat_member.user = mock_user
    mock_context.bot.get_chat_member.return_value = mock_chat_member
    
    try:
        with patch('handlers.admin_handlers.check_admin_permission', return_value=True), \
             patch('handlers.admin_handlers.get_user_display_name', return_value="Test User"):
            
            await check_user_score(mock_update, mock_context)
            
            if mock_message.reply_text.called:
                call_args = mock_message.reply_text.call_args
                message_content = call_args[0][0] if call_args[0] else ""
                
                print(f"✅ Response sent: {len(message_content)} characters")
                print(f"📄 Message preview: {message_content[:200]}...")
                
                # Check for expected elements
                expected_elements = ["User Information", "Player:", "Wallet:", "Wins:", "Losses:"]
                found_elements = [elem for elem in expected_elements if elem in message_content]
                print(f"📊 Found elements: {found_elements}")
                
                if len(found_elements) == len(expected_elements):
                    print("✅ Test 1 PASSED: All expected elements found")
                else:
                    print(f"❌ Test 1 FAILED: Missing elements: {set(expected_elements) - set(found_elements)}")
            else:
                print("❌ Test 1 FAILED: No response sent")
                
    except Exception as e:
        print(f"❌ Test 1 FAILED: Exception: {e}")
    
    # Test 2: Non-existing user
    print("\n📋 Test 2: Checking non-existing user...")
    mock_context.args = [non_existing_user_id]
    mock_message.reply_text.reset_mock()
    
    try:
        with patch('handlers.admin_handlers.check_admin_permission', return_value=True):
            
            await check_user_score(mock_update, mock_context)
            
            if mock_message.reply_text.called:
                call_args = mock_message.reply_text.call_args
                message_content = call_args[0][0] if call_args[0] else ""
                
                print(f"✅ Error response sent: {message_content}")
                
                # Should be the "user not found in records" message
                if MessageTemplates.USER_NOT_IN_RECORDS in message_content:
                    print("✅ Test 2 PASSED: Correct error message for non-existing user")
                else:
                    print(f"❌ Test 2 FAILED: Unexpected message: {message_content}")
            else:
                print("❌ Test 2 FAILED: No response sent")
                
    except Exception as e:
        print(f"❌ Test 2 FAILED: Exception: {e}")
    
    # Test 3: Username lookup
    print("\n📋 Test 3: Checking user by username...")
    mock_context.args = ["@testuser"]
    mock_message.reply_text.reset_mock()
    
    try:
        with patch('handlers.admin_handlers.check_admin_permission', return_value=True), \
             patch('handlers.admin_handlers.get_user_display_name', return_value="Test User"):
            
            await check_user_score(mock_update, mock_context)
            
            if mock_message.reply_text.called:
                call_args = mock_message.reply_text.call_args
                message_content = call_args[0][0] if call_args[0] else ""
                
                print(f"✅ Response sent: {len(message_content)} characters")
                
                # Check for expected elements
                if "User Information" in message_content and "testuser" in message_content.lower():
                    print("✅ Test 3 PASSED: Username lookup successful")
                else:
                    print(f"❌ Test 3 FAILED: Unexpected response: {message_content[:200]}...")
            else:
                print("❌ Test 3 FAILED: No response sent")
                
    except Exception as e:
        print(f"❌ Test 3 FAILED: Exception: {e}")
    
    # Test 4: Non-existing username
    print("\n📋 Test 4: Checking non-existing username...")
    mock_context.args = ["@nonexistentuser"]
    mock_message.reply_text.reset_mock()
    
    try:
        with patch('handlers.admin_handlers.check_admin_permission', return_value=True):
            
            await check_user_score(mock_update, mock_context)
            
            if mock_message.reply_text.called:
                call_args = mock_message.reply_text.call_args
                message_content = call_args[0][0] if call_args[0] else ""
                
                print(f"✅ Error response sent: {message_content}")
                
                # Should be the "user not found by username" message
                if "not found" in message_content.lower() and "@nonexistentuser" in message_content:
                    print("✅ Test 4 PASSED: Correct error message for non-existing username")
                else:
                    print(f"❌ Test 4 FAILED: Unexpected message: {message_content}")
            else:
                print("❌ Test 4 FAILED: No response sent")
                
    except Exception as e:
        print(f"❌ Test 4 FAILED: Exception: {e}")
    
    print("\n" + "="*50)
    print("🎯 CHECKSCORE TESTS COMPLETED")
    print("="*50)

if __name__ == "__main__":
    try:
        asyncio.run(test_checkscore())
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        sys.exit(1)