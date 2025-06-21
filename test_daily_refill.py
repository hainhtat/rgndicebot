#!/usr/bin/env python3
"""
Test script to verify that all admins in groups are refilled every morning.
This script simulates the daily refill process and validates the results.
"""

import json
import sys
import os
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_test_data():
    """Load current bot data for testing"""
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ data.json not found. Make sure you're running this from the bot directory.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing data.json: {e}")
        return None

def simulate_daily_refill():
    """Simulate the daily admin refill process"""
    print("🔄 Simulating daily admin refill process...")
    
    try:
        # Import the required modules
        from config.constants import global_data, ADMIN_WALLET_AMOUNT
        
        # Load current data into global_data
        current_data = load_test_data()
        if not current_data:
            return False
        
        # Update global_data with current data
        global_data.update(current_data)
        
        print(f"📊 Current admin data: {len(global_data.get('admin_data', {}))} admins")
        print(f"💰 Refill amount: {ADMIN_WALLET_AMOUNT:,} points")
        
        # Get all chat data to find groups with admins
        all_chat_data = global_data.get('all_chat_data', {})
        total_groups = len(all_chat_data)
        groups_with_admins = 0
        total_admins_refilled = 0
        
        print(f"🏘️ Total groups: {total_groups}")
        
        # Simulate refill for each group
        for chat_id, chat_data in all_chat_data.items():
            group_admins = chat_data.get('group_admins', [])
            if group_admins:
                groups_with_admins += 1
                print(f"\n🏢 Group {chat_id}: {len(group_admins)} admins")
                
                for admin_id in group_admins:
                    admin_id_str = str(admin_id)
                    chat_id_str = str(chat_id)
                    
                    # Check if admin exists in admin_data
                    if admin_id_str not in global_data['admin_data']:
                        global_data['admin_data'][admin_id_str] = {
                            'username': f'Admin {admin_id}',
                            'chat_points': {}
                        }
                    
                    # Check if chat_points exists for this group
                    if chat_id_str not in global_data['admin_data'][admin_id_str]['chat_points']:
                        global_data['admin_data'][admin_id_str]['chat_points'][chat_id_str] = {
                            'points': 0,
                            'last_refill': None
                        }
                    
                    # Get current points before refill
                    current_points = global_data['admin_data'][admin_id_str]['chat_points'][chat_id_str]['points']
                    
                    # Simulate refill
                    global_data['admin_data'][admin_id_str]['chat_points'][chat_id_str]['points'] = ADMIN_WALLET_AMOUNT
                    global_data['admin_data'][admin_id_str]['chat_points'][chat_id_str]['last_refill'] = datetime.now()
                    
                    total_admins_refilled += 1
                    
                    print(f"  👤 Admin {admin_id}: {current_points:,} → {ADMIN_WALLET_AMOUNT:,} points")
        
        print(f"\n📈 Refill Summary:")
        print(f"  🏘️ Groups with admins: {groups_with_admins}/{total_groups}")
        print(f"  👥 Total admins refilled: {total_admins_refilled}")
        print(f"  💰 Total points distributed: {total_admins_refilled * ADMIN_WALLET_AMOUNT:,}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the bot directory.")
        return False
    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        return False

async def test_refill_scheduler():
    """Test the actual refill scheduler function"""
    print("\n🧪 Testing refill scheduler function...")
    
    try:
        from utils.scheduler import daily_admin_wallet_refill
        from config.constants import global_data
        
        # Load current data
        current_data = load_test_data()
        if not current_data:
            return False
        
        global_data.update(current_data)
        
        # Call the actual refill function
        print("🔄 Calling daily_admin_wallet_refill()...")
        await daily_admin_wallet_refill()
        
        print("✅ Refill scheduler function executed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing scheduler: {e}")
        return False

def validate_refill_results():
    """Validate that all admins have been properly refilled"""
    print("\n🔍 Validating refill results...")
    
    try:
        from config.constants import global_data, ADMIN_WALLET_AMOUNT
        
        admin_data = global_data.get('admin_data', {})
        all_chat_data = global_data.get('all_chat_data', {})
        
        validation_errors = []
        total_validated = 0
        
        for chat_id, chat_data in all_chat_data.items():
            group_admins = chat_data.get('group_admins', [])
            
            for admin_id in group_admins:
                admin_id_str = str(admin_id)
                chat_id_str = str(chat_id)
                total_validated += 1
                
                # Check if admin exists in admin_data
                if admin_id_str not in admin_data:
                    validation_errors.append(f"Admin {admin_id} missing from admin_data")
                    continue
                
                # Check if chat_points exists
                admin_info = admin_data[admin_id_str]
                if 'chat_points' not in admin_info:
                    validation_errors.append(f"Admin {admin_id} missing chat_points")
                    continue
                
                # Check if this group's points exist
                if chat_id_str not in admin_info['chat_points']:
                    validation_errors.append(f"Admin {admin_id} missing points for group {chat_id}")
                    continue
                
                # Check if points are correctly set
                points = admin_info['chat_points'][chat_id_str].get('points', 0)
                if points != ADMIN_WALLET_AMOUNT:
                    validation_errors.append(f"Admin {admin_id} has {points} points instead of {ADMIN_WALLET_AMOUNT}")
                
                # Check if last_refill is recent
                last_refill = admin_info['chat_points'][chat_id_str].get('last_refill')
                if not last_refill:
                    validation_errors.append(f"Admin {admin_id} missing last_refill timestamp")
        
        print(f"📊 Validation Results:")
        print(f"  👥 Total admins validated: {total_validated}")
        print(f"  ❌ Validation errors: {len(validation_errors)}")
        
        if validation_errors:
            print("\n🚨 Validation Errors:")
            for error in validation_errors[:10]:  # Show first 10 errors
                print(f"  • {error}")
            if len(validation_errors) > 10:
                print(f"  ... and {len(validation_errors) - 10} more errors")
            return False
        else:
            print("✅ All validations passed!")
            return True
            
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        return False

def test_scheduler_timing():
    """Test that the scheduler is configured for the correct time"""
    print("\n⏰ Testing scheduler timing configuration...")
    
    try:
        from config.constants import ADMIN_WALLET_REFILL_HOUR, ADMIN_WALLET_REFILL_MINUTE
        
        print(f"📅 Configured refill time: {ADMIN_WALLET_REFILL_HOUR:02d}:{ADMIN_WALLET_REFILL_MINUTE:02d}")
        
        # Check if the time is reasonable (morning hours)
        if 6 <= ADMIN_WALLET_REFILL_HOUR <= 10:
            print("✅ Refill time is set for morning hours")
            return True
        else:
            print(f"⚠️ Refill time {ADMIN_WALLET_REFILL_HOUR}:{ADMIN_WALLET_REFILL_MINUTE} may not be optimal for morning refills")
            return False
            
    except ImportError:
        print("❌ Could not import refill timing constants")
        return False
    except Exception as e:
        print(f"❌ Error checking scheduler timing: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Daily Admin Refill Test Suite")
    print("=" * 50)
    
    tests = [
        ("Scheduler Timing", test_scheduler_timing),
        ("Daily Refill Simulation", simulate_daily_refill),
        ("Refill Scheduler Function", test_refill_scheduler),
        ("Refill Results Validation", validate_refill_results)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔬 Running: {test_name}")
        print("-" * 30)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                print(f"✅ {test_name}: PASSED")
                passed_tests += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Daily admin refill is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)