#!/usr/bin/env python3
"""
Script to clear Telegram webhook and resolve bot conflicts.
"""

import requests
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import BOT_TOKEN

def clear_webhook():
    """Clear the webhook for the bot."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        return False
    
    print("🤖 Clearing Telegram Webhook")
    print("=" * 40)
    
    # Delete webhook
    delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    try:
        print("🔄 Sending deleteWebhook request...")
        response = requests.post(delete_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Webhook deleted successfully")
                print(f"   Description: {result.get('description', 'N/A')}")
            else:
                print(f"❌ Failed to delete webhook: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    # Set empty webhook (alternative method)
    set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    try:
        print("🔄 Setting empty webhook...")
        response = requests.post(set_url, data={'url': ''}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Empty webhook set successfully")
                print(f"   Description: {result.get('description', 'N/A')}")
            else:
                print(f"⚠️  Warning setting empty webhook: {result.get('description', 'Unknown error')}")
        else:
            print(f"⚠️  HTTP Warning {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Network warning: {e}")
    
    return True

def get_webhook_info():
    """Get current webhook information."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        return False
    
    print("🔍 Getting Webhook Information")
    print("=" * 40)
    
    info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    try:
        print("🔄 Getting webhook info...")
        response = requests.get(info_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                webhook_info = result.get('result', {})
                print("📊 Webhook Information:")
                print(f"   URL: {webhook_info.get('url', 'Not set')}")
                print(f"   Has custom certificate: {webhook_info.get('has_custom_certificate', False)}")
                print(f"   Pending update count: {webhook_info.get('pending_update_count', 0)}")
                print(f"   Last error date: {webhook_info.get('last_error_date', 'None')}")
                print(f"   Last error message: {webhook_info.get('last_error_message', 'None')}")
                print(f"   Max connections: {webhook_info.get('max_connections', 'Default')}")
                
                if webhook_info.get('url'):
                    print("⚠️  Webhook is currently set - this may cause conflicts with polling")
                    return True
                else:
                    print("✅ No webhook set - polling should work fine")
                    return False
            else:
                print(f"❌ Failed to get webhook info: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

def get_bot_info():
    """Get bot information to verify token."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        return False
    
    print("🤖 Getting Bot Information")
    print("=" * 40)
    
    me_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        print("🔄 Getting bot info...")
        response = requests.get(me_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                bot_info = result.get('result', {})
                print("🤖 Bot Information:")
                print(f"   ID: {bot_info.get('id')}")
                print(f"   Username: @{bot_info.get('username')}")
                print(f"   First Name: {bot_info.get('first_name')}")
                print(f"   Can join groups: {bot_info.get('can_join_groups', False)}")
                print(f"   Can read all group messages: {bot_info.get('can_read_all_group_messages', False)}")
                print(f"   Supports inline queries: {bot_info.get('supports_inline_queries', False)}")
                print("✅ Bot token is valid")
                return True
            else:
                print(f"❌ Failed to get bot info: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

def main():
    print("🎲 RGN Dice Bot - Webhook Manager")
    print("=" * 50)
    
    try:
        # Check bot token validity
        if not get_bot_info():
            print("\n❌ Bot token is invalid or there's a network issue")
            return
        
        print()
        
        # Check current webhook status
        webhook_set = get_webhook_info()
        
        print()
        
        if webhook_set:
            print("🔧 Webhook is set - clearing it to resolve conflicts...")
            if clear_webhook():
                print("\n✅ Webhook cleared successfully")
                print("\n💡 Next steps:")
                print("   1. Wait 2-3 minutes")
                print("   2. Restart your bot")
                print("   3. The bot should now use polling without conflicts")
            else:
                print("\n❌ Failed to clear webhook")
        else:
            print("✅ No webhook conflicts detected")
            print("\n💡 If you're still getting conflicts:")
            print("   1. Stop all bot instances (Render + local)")
            print("   2. Wait 2-3 minutes")
            print("   3. Start only one bot instance")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "info":
            get_bot_info()
            print()
            get_webhook_info()
        elif command == "clear":
            clear_webhook()
        else:
            print("Usage: python clear_webhook.py [info|clear]")
    else:
        main()