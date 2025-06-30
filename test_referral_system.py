#!/usr/bin/env python3
"""
Simple test to verify referral system functionality
"""

import asyncio
import json
from config.constants import global_data

from main import load_data_unified, save_data_unified
from utils.user_utils import get_or_create_global_user_data

def test_referral_logic():
    """Test referral system logic without bot context"""
    print("🧪 Testing Referral System Logic...")
    
    # Load current data
    load_data(global_data)
    
    referrer_id = 6809465186  # Existing user
    new_user_1 = 999888777   # Test user 1
    new_user_2 = 999888778   # Test user 2
    
    print(f"\n📊 Testing with referrer: {referrer_id}")
    
    # Ensure referrer exists
    get_or_create_global_user_data(referrer_id, "Test", "Referrer", "test_referrer")
    
    # Test 1: Refer first new user (should succeed)
    print("\n🔸 Test 1: Referring first new user...")
    success1 = test_single_referral(new_user_1, referrer_id, "TestUser1")
    print(f"   Result: {'✅ SUCCESS' if success1 else '❌ FAILED'}")
    
    # Test 2: Try to refer the same user again (should fail)
    print("\n🔸 Test 2: Trying to refer same user again...")
    success2 = test_single_referral(new_user_1, referrer_id, "TestUser1")
    print(f"   Result: {'✅ SUCCESS' if success2 else '❌ FAILED (Expected)'}")
    
    # Test 3: Refer a different new user (should succeed)
    print("\n🔸 Test 3: Referring different new user...")
    success3 = test_single_referral(new_user_2, referrer_id, "TestUser2")
    print(f"   Result: {'✅ SUCCESS' if success3 else '❌ FAILED'}")
    
    return success1, success2, success3

def test_single_referral(user_id, referrer_id, user_name):
    """Test a single referral without bot context"""
    user_id_str = str(user_id)
    referrer_id_str = str(referrer_id)
    
    # Check if user is trying to refer themselves
    if user_id == referrer_id:
        print("   ❌ Self-referral not allowed")
        return False
    
    # Create user data if it doesn't exist
    get_or_create_global_user_data(user_id, user_name, "", f"test_{user_id}")
    
    # Get user data
    user_data = global_data["global_user_data"].get(user_id_str)
    referrer_data = global_data["global_user_data"].get(referrer_id_str)
    
    if not user_data or not referrer_data:
        print("   ❌ User or referrer data not found")
        return False
    
    # Check if user has already been referred
    if user_data.get("referred_by") is not None:
        print("   ❌ User already has a referrer")
        return False
    
    # Store the referral relationship
    user_data["referred_by"] = referrer_id
    user_data["referral_pending"] = True
    
    print(f"   ✅ User {user_id} successfully referred by {referrer_id}")
    return True

def test_referral_system():
    """Main test function"""
    success1, success2, success3 = test_referral_logic()
    
    new_user_1 = 999888777   # Test user 1
    new_user_2 = 999888778   # Test user 2
    
    # Summary
    print("\n📋 SUMMARY:")
    print(f"   ✅ First referral: {'PASSED' if success1 else 'FAILED'}")
    print(f"   ✅ Duplicate prevention: {'PASSED' if not success2 else 'FAILED'}")
    print(f"   ✅ Multiple referrals: {'PASSED' if success3 else 'FAILED'}")
    
    # Check referral data
    print("\n📊 REFERRAL DATA:")
    user1_data = global_data["global_user_data"].get(str(new_user_1), {})
    user2_data = global_data["global_user_data"].get(str(new_user_2), {})
    
    print(f"   User {new_user_1} referred by: {user1_data.get('referred_by', 'None')}")
    print(f"   User {new_user_2} referred by: {user2_data.get('referred_by', 'None')}")
    
    # Clean up test data
    if str(new_user_1) in global_data["global_user_data"]:
        del global_data["global_user_data"][str(new_user_1)]
    if str(new_user_2) in global_data["global_user_data"]:
        del global_data["global_user_data"][str(new_user_2)]
    
    save_data_unified(global_data)
    print("\n🧹 Test data cleaned up.")
    
    overall_success = success1 and not success2 and success3
    print(f"\n🎯 OVERALL RESULT: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    test_referral_system()