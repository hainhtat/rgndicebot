#!/usr/bin/env python3
"""
Minimal test to isolate the balance calculation logic
"""

def test_balance_calculation():
    print("=== Minimal Balance Calculation Test ===")
    
    # Simulate the balance calculation logic from place_bet
    initial_balance = 1000
    bet_amount = 100
    
    # This is what should happen in place_bet:
    # 1. Check if user has enough balance
    if initial_balance >= bet_amount:
        # 2. Deduct the bet amount
        new_balance = initial_balance - bet_amount
        print(f"✅ Bet placed successfully")
        print(f"Initial balance: {initial_balance}")
        print(f"Bet amount: {bet_amount}")
        print(f"New balance: {new_balance}")
        
        # 3. Create result message (simplified)
        result_message = f"✅ Bet placed: BIG {bet_amount} (Used {bet_amount} main ကျပ်)\nYour balance: {new_balance} main, 0 referral, 0 bonus ကျပ်"
        print(f"\nResult message:")
        print(result_message)
        
        # 4. Extract balance from message
        if "Your balance:" in result_message:
            balance_part = result_message.split("Your balance:")[1].strip()
            message_balance = int(balance_part.split(" main")[0])
            print(f"\nExtracted balance from message: {message_balance}")
            
            # 5. Check consistency
            if new_balance == message_balance:
                print("✅ Balance is consistent!")
                return True
            else:
                print(f"❌ Balance mismatch! Actual: {new_balance}, Message: {message_balance}")
                return False
        else:
            print("❌ No balance information found in result message")
            return False
    else:
        print(f"❌ Insufficient funds: {initial_balance} < {bet_amount}")
        return False

def test_hardcoded_765_issue():
    print("\n=== Testing Hardcoded 765 Issue ===")
    
    # This simulates what might be happening if there's a hardcoded value
    initial_balance = 1000
    bet_amount = 100
    new_balance = initial_balance - bet_amount  # Should be 900
    
    # But if there's a bug, the message might show a hardcoded value
    hardcoded_balance = 765
    
    result_message = f"✅ Bet placed: BIG {bet_amount} (Used {bet_amount} main ကျပ်)\nYour balance: {hardcoded_balance} main, 0 referral, 0 bonus ကျပ်"
    
    print(f"Actual balance after bet: {new_balance}")
    print(f"Balance shown in message: {hardcoded_balance}")
    
    if new_balance != hardcoded_balance:
        print(f"❌ This demonstrates the bug! Actual: {new_balance}, Message: {hardcoded_balance}")
        return False
    else:
        print("✅ No hardcoded value issue")
        return True

if __name__ == "__main__":
    test1_result = test_balance_calculation()
    test2_result = test_hardcoded_765_issue()
    
    print("\n=== Summary ===")
    print(f"Balance calculation test: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"Hardcoded 765 test: {'✅ PASS' if test2_result else '❌ FAIL (demonstrates the bug)'}")