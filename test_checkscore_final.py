#!/usr/bin/env python3
"""
Final test script to demonstrate checkscore functionality with real data
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

async def demonstrate_checkscore():
    """
    Demonstrate checkscore functionality with real data
    """
    print("🎯 CHECKSCORE FUNCTIONALITY DEMONSTRATION\n")
    
    # Load existing data
    load_data(global_data)
    print(f"📊 Loaded global_data with keys: {list(global_data.keys())}")
    
    # Use a real chat ID from the data
    if 'all_chat_data' in global_data and global_data['all_chat_data']:
        real_chat_id = list(global_data['all_chat_data'].keys())[0]
        chat_data = global_data['all_chat_data'][real_chat_id]
        print(f"📋 Using real chat ID: {real_chat_id}")
        print(f"📊 Player stats available: {list(chat_data['player_stats'].keys())}")
        
        if chat_data['player_stats']:
            # Get a real user ID
            real_user_id = list(chat_data['player_stats'].keys())[0]
            user_data = chat_data['player_stats'][real_user_id]
            print(f"👤 Testing with real user: {real_user_id}")
            print(f"📈 User data: {user_data}")
            
            # Create mock objects for the test
            class MockUser:
                def __init__(self, user_id, username=None):
                    self.id = int(user_id) if isinstance(user_id, str) else user_id
                    self.username = username or user_data.get('username', 'testuser')
                    self.first_name = "Real"
                    self.last_name = "User"
                    self.full_name = f"{self.first_name} {self.last_name}"
            
            class MockChat:
                def __init__(self, chat_id):
                    self.id = int(chat_id)
                    self.type = "group"
            
            class MockMessage:
                def __init__(self, user_id, chat_id, text):
                    self.from_user = MockUser(user_id)
                    self.chat = MockChat(chat_id)
                    self.text = text
                    self.reply_to_message = None
                    self.captured_message = None
                    
                async def reply_text(self, text, parse_mode=None, **kwargs):
                    self.captured_message = text
                    print("\n" + "="*60)
                    print("📤 CHECKSCORE OUTPUT:")
                    print("="*60)
                    print(text)
                    print("="*60)
                    return MagicMock()
            
            class MockUpdate:
                def __init__(self, user_id, chat_id, text):
                    self.message = MockMessage(user_id, chat_id, text)
                    self.effective_user = MockUser(user_id)
                    self.effective_chat = MockChat(chat_id)
            
            class MockContext:
                def __init__(self):
                    self.bot = AsyncMock()
                    self.args = []
            
            # Test with real data
            super_admin_id = 1599213796  # Use actual super admin ID
            update = MockUpdate(super_admin_id, real_chat_id, f"/checkscore {real_user_id}")
            context = MockContext()
            context.args = [str(real_user_id)]
            
            # Mock the get_chat_member call
            mock_member = MagicMock()
            mock_member.user = MockUser(real_user_id)
            context.bot.get_chat_member = AsyncMock(return_value=mock_member)
            
            print(f"\n🔍 Executing checkscore for user {real_user_id} in chat {real_chat_id}...")
            
            try:
                await check_user_score(update, context)
                
                # Analyze the output
                if update.message.captured_message:
                    message = update.message.captured_message
                    print("\n📊 ANALYSIS:")
                    print(f"✅ Message length: {len(message)} characters")
                    
                    # Check for key elements
                    elements = {
                        '📊 User Information': '📊' in message and 'User Information' in message,
                        '👤 Player name': '👤' in message and 'Player:' in message,
                        '💰 Wallet': '💰' in message and 'Wallet:' in message,
                        '🏆 Wins': '🏆' in message and 'Wins:' in message,
                        '💔 Losses': '💔' in message and 'Losses:' in message,
                        '📈 Win Rate': '📈' in message and 'Win Rate:' in message,
                        '🎁 Referral Points': '🎁' in message and 'Referral Points:' in message,
                        'Markdown formatting': '*' in message or '_' in message
                    }
                    
                    for element, found in elements.items():
                        status = "✅" if found else "❌"
                        print(f"{status} {element}: {'Found' if found else 'Missing'}")
                    
                    all_found = all(elements.values())
                    print(f"\n🎯 Overall result: {'✅ ALL ELEMENTS PRESENT' if all_found else '⚠️ SOME ELEMENTS MISSING'}")
                    
                else:
                    print("❌ No message was captured")
                    
            except Exception as e:
                print(f"❌ Error during test: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("❌ No player stats found in the data")
    else:
        print("❌ No chat data found")
    
    print("\n🏁 Checkscore demonstration completed!")

if __name__ == "__main__":
    asyncio.run(demonstrate_checkscore())