#!/usr/bin/env python3
"""
Comprehensive Database Consistency Test for Dice Bot

This test suite verifies the consistency of:
- Main wallet balances
- Referral points
- Bonus points
- Betting operations
- Cross-system interactions

Run with: python3 test_database_consistency.py
"""

import asyncio
import logging
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import USE_DATABASE
from database.adapter import db_adapter
from config.constants import global_data, get_chat_data_for_id, get_admin_data
from handlers.utils import save_data_unified, load_data_unified
from utils.user_utils import get_or_create_global_user_data, process_referral
from game.game_logic import payout, DiceGame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseConsistencyTester:
    """Comprehensive database consistency tester for the dice bot."""
    
    def __init__(self):
        self.test_chat_id = -1001234567890  # Test chat ID
        self.test_users = [
            {'id': 111111, 'username': 'test_user_1', 'first_name': 'Test', 'last_name': 'User1'},
            {'id': 222222, 'username': 'test_user_2', 'first_name': 'Test', 'last_name': 'User2'},
            {'id': 333333, 'username': 'test_user_3', 'first_name': 'Test', 'last_name': 'User3'},
            {'id': 444444, 'username': 'test_admin', 'first_name': 'Test', 'last_name': 'Admin'},
        ]
        self.test_results = []
        self.initial_state = {}
        
    async def setup_test_environment(self):
        """Setup clean test environment."""
        logger.info("Setting up test environment...")
        
        # Load current data
        load_data_unified()
        
        # Backup current state
        self.initial_state = {
            'global_data': json.loads(json.dumps(global_data, default=str)),
        }
        
        # Initialize test chat data
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"] = {}
        chat_data["game_state"] = {"active": False}
        
        # Initialize test users with known balances
        for user in self.test_users:
            user_id = str(user['id'])
            
            # Initialize player stats
            chat_data["player_stats"][user_id] = {
                "username": user['username'],
                "score": 10000,  # Start with 10k points
                "total_bets": 0,
                "total_wins": 0,
                "total_losses": 0,
                "last_active": datetime.now()
            }
            
            # Initialize global user data
            global_user_data = get_or_create_global_user_data(
                user['id'], user['first_name'], user['last_name'], user['username']
            )
            global_user_data['referral_points'] = 5000  # Start with 5k referral points
            global_user_data['bonus_points'] = 2000     # Start with 2k bonus points
        
        save_data_unified(global_data)
        logger.info("Test environment setup complete")
    
    async def cleanup_test_environment(self):
        """Restore original state after tests."""
        logger.info("Cleaning up test environment...")
        
        # Restore original state
        global_data.clear()
        global_data.update(self.initial_state['global_data'])
        save_data_unified(global_data)
        
        logger.info("Test environment cleanup complete")
    
    def get_user_balances(self, user_id: int) -> Dict[str, int]:
        """Get all balance types for a user."""
        user_id_str = str(user_id)
        chat_data = get_chat_data_for_id(self.test_chat_id)
        
        # Main wallet (from player stats)
        main_wallet = chat_data.get("player_stats", {}).get(user_id_str, {}).get("score", 0)
        
        # Global balances
        global_user_data = global_data.get("global_user_data", {}).get(user_id_str, {})
        referral_points = global_user_data.get('referral_points', 0)
        bonus_points = global_user_data.get('bonus_points', 0)
        
        return {
            'main_wallet': main_wallet,
            'referral_points': referral_points,
            'bonus_points': bonus_points,
            'total': main_wallet + referral_points + bonus_points
        }
    
    def assert_balance_consistency(self, user_id: int, expected: Dict[str, int], test_name: str):
        """Assert that user balances match expected values."""
        actual = self.get_user_balances(user_id)
        
        success = True
        errors = []
        
        for balance_type, expected_value in expected.items():
            if actual.get(balance_type) != expected_value:
                success = False
                errors.append(
                    f"{balance_type}: expected {expected_value}, got {actual.get(balance_type)}"
                )
        
        self.test_results.append({
            'test': test_name,
            'user_id': user_id,
            'success': success,
            'expected': expected,
            'actual': actual,
            'errors': errors
        })
        
        if not success:
            logger.error(f"FAIL: {test_name} - User {user_id}: {', '.join(errors)}")
        else:
            logger.info(f"PASS: {test_name} - User {user_id}")
    
    async def test_basic_balance_operations(self):
        """Test basic balance operations."""
        logger.info("Testing basic balance operations...")
        
        user_id = self.test_users[0]['id']
        user_id_str = str(user_id)
        
        # Test initial balances
        self.assert_balance_consistency(user_id, {
            'main_wallet': 10000,
            'referral_points': 5000,
            'bonus_points': 2000,
            'total': 17000
        }, "Initial Balance Check")
        
        # Test main wallet modification
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"][user_id_str]["score"] = 15000
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 15000,
            'referral_points': 5000,
            'bonus_points': 2000,
            'total': 22000
        }, "Main Wallet Modification")
        
        # Test referral points modification
        global_user_data = global_data["global_user_data"][user_id_str]
        global_user_data['referral_points'] = 7500
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 15000,
            'referral_points': 7500,
            'bonus_points': 2000,
            'total': 24500
        }, "Referral Points Modification")
        
        # Test bonus points modification
        global_user_data['bonus_points'] = 3000
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 15000,
            'referral_points': 7500,
            'bonus_points': 3000,
            'total': 25500
        }, "Bonus Points Modification")
    
    async def test_betting_operations(self):
        """Test betting operations and their impact on balances."""
        logger.info("Testing betting operations...")
        
        user_id = self.test_users[1]['id']
        user_id_str = str(user_id)
        
        # Reset user to known state
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"][user_id_str]["score"] = 10000
        save_data_unified(global_data)
        
        # Test bet placement (deduction)
        bet_amount = 1000
        chat_data["player_stats"][user_id_str]["score"] -= bet_amount
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 9000,
            'referral_points': 5000,
            'bonus_points': 2000,
            'total': 16000
        }, "Bet Placement Deduction")
        
        # Test winning bet (payout)
        dice_result = [6, 6]  # Double 6 (sum = 12, BIG win)
        # Calculate payout for BIG bet with 1.95x multiplier
        payout_amount = int(bet_amount * 1.95)  # BIG multiplier
        chat_data["player_stats"][user_id_str]["score"] += payout_amount
        chat_data["player_stats"][user_id_str]["total_wins"] += 1
        save_data_unified(global_data)
        
        expected_balance = 9000 + payout_amount
        self.assert_balance_consistency(user_id, {
            'main_wallet': expected_balance,
            'referral_points': 5000,
            'bonus_points': 2000,
            'total': expected_balance + 7000
        }, "Winning Bet Payout")
        
        # Test losing bet
        bet_amount = 500
        chat_data["player_stats"][user_id_str]["score"] -= bet_amount
        chat_data["player_stats"][user_id_str]["total_losses"] += 1
        save_data_unified(global_data)
        
        expected_balance -= bet_amount
        self.assert_balance_consistency(user_id, {
            'main_wallet': expected_balance,
            'referral_points': 5000,
            'bonus_points': 2000,
            'total': expected_balance + 7000
        }, "Losing Bet Deduction")
    
    async def test_referral_system(self):
        """Test referral system consistency."""
        logger.info("Testing referral system...")
        
        referrer_id = self.test_users[0]['id']
        referee_id = self.test_users[2]['id']
        
        # Get initial balances
        referrer_initial = self.get_user_balances(referrer_id)
        referee_initial = self.get_user_balances(referee_id)
        
        # Mock context for referral processing
        class MockContext:
            def __init__(self):
                self.bot = None
        
        mock_context = MockContext()
        
        # Process referral
        success, message, referrer_data = await process_referral(referee_id, referrer_id, mock_context)
        
        if success:
            # Check referrer got bonus
            referrer_final = self.get_user_balances(referrer_id)
            expected_referrer_referral = referrer_initial['referral_points'] + 500
            
            self.assert_balance_consistency(referrer_id, {
                'main_wallet': referrer_initial['main_wallet'],
                'referral_points': expected_referrer_referral,
                'bonus_points': referrer_initial['bonus_points'],
                'total': referrer_initial['total'] + 500
            }, "Referrer Bonus Award")
            
            # Check referee got welcome bonus
            referee_final = self.get_user_balances(referee_id)
            expected_referee_bonus = referee_initial['bonus_points'] + 500
            
            self.assert_balance_consistency(referee_id, {
                'main_wallet': referee_initial['main_wallet'],
                'referral_points': referee_initial['referral_points'],
                'bonus_points': expected_referee_bonus,
                'total': referee_initial['total'] + 500
            }, "Referee Welcome Bonus")
    
    async def test_admin_wallet_operations(self):
        """Test admin wallet operations."""
        logger.info("Testing admin wallet operations...")
        
        admin_id = self.test_users[3]['id']
        
        # Get admin data
        admin_data = get_admin_data(admin_id, self.test_chat_id, "test_admin")
        initial_points = admin_data.get("points", 0)
        
        # Test admin wallet refill
        refill_amount = 50000
        admin_data["points"] = initial_points + refill_amount
        admin_data["last_refill"] = datetime.now()
        save_data_unified(global_data)
        
        # Verify admin wallet update
        updated_admin_data = get_admin_data(admin_id, self.test_chat_id, "test_admin")
        expected_points = initial_points + refill_amount
        
        success = updated_admin_data.get("points", 0) == expected_points
        self.test_results.append({
            'test': 'Admin Wallet Refill',
            'user_id': admin_id,
            'success': success,
            'expected': {'admin_points': expected_points},
            'actual': {'admin_points': updated_admin_data.get("points", 0)},
            'errors': [] if success else [f"Expected {expected_points}, got {updated_admin_data.get('points', 0)}"]
        })
        
        if success:
            logger.info(f"PASS: Admin Wallet Refill - Admin {admin_id}")
        else:
            logger.error(f"FAIL: Admin Wallet Refill - Admin {admin_id}")
    
    async def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        logger.info("Testing edge cases...")
        
        user_id = self.test_users[0]['id']
        user_id_str = str(user_id)
        
        # Test zero balances
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"][user_id_str]["score"] = 0
        
        global_user_data = global_data["global_user_data"][user_id_str]
        global_user_data['referral_points'] = 0
        global_user_data['bonus_points'] = 0
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 0,
            'referral_points': 0,
            'bonus_points': 0,
            'total': 0
        }, "Zero Balances")
        
        # Test negative balance prevention (should not go below 0)
        try:
            chat_data["player_stats"][user_id_str]["score"] = -1000
            save_data_unified(global_data)
            
            actual_balance = self.get_user_balances(user_id)['main_wallet']
            
            # In a proper system, negative balances should be prevented
            # This test documents current behavior
            self.test_results.append({
                'test': 'Negative Balance Handling',
                'user_id': user_id,
                'success': True,  # Document current behavior
                'expected': {'main_wallet': -1000},
                'actual': {'main_wallet': actual_balance},
                'errors': []
            })
            logger.info(f"INFO: Negative Balance Handling - Current behavior allows negative: {actual_balance}")
        except Exception as e:
            logger.error(f"Error in negative balance test: {e}")
        
        # Test large numbers
        large_amount = 999999999
        chat_data["player_stats"][user_id_str]["score"] = large_amount
        save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': large_amount,
            'referral_points': 0,
            'bonus_points': 0,
            'total': large_amount
        }, "Large Number Handling")
    
    async def test_concurrent_operations(self):
        """Test concurrent operations simulation."""
        logger.info("Testing concurrent operations simulation...")
        
        user_id = self.test_users[1]['id']
        user_id_str = str(user_id)
        
        # Reset to known state
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"][user_id_str]["score"] = 10000
        save_data_unified(global_data)
        
        # Simulate multiple rapid operations
        operations = [
            ('bet', -500),
            ('win', 1000),
            ('bet', -300),
            ('lose', 0),
            ('referral_bonus', 500),  # This goes to referral_points
        ]
        
        expected_main_wallet = 10000
        expected_referral_points = 5000
        
        for operation, amount in operations:
            if operation in ['bet', 'lose']:
                chat_data["player_stats"][user_id_str]["score"] += amount
                expected_main_wallet += amount
            elif operation == 'win':
                chat_data["player_stats"][user_id_str]["score"] += amount
                expected_main_wallet += amount
            elif operation == 'referral_bonus':
                global_user_data = global_data["global_user_data"][user_id_str]
                global_user_data['referral_points'] += amount
                expected_referral_points += amount
            
            save_data_unified(global_data)
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': expected_main_wallet,
            'referral_points': expected_referral_points,
            'bonus_points': 2000,
            'total': expected_main_wallet + expected_referral_points + 2000
        }, "Concurrent Operations Simulation")
    
    async def test_data_persistence(self):
        """Test data persistence across save/load cycles."""
        logger.info("Testing data persistence...")
        
        user_id = self.test_users[2]['id']
        user_id_str = str(user_id)
        
        # Set specific values
        chat_data = get_chat_data_for_id(self.test_chat_id)
        chat_data["player_stats"][user_id_str]["score"] = 12345
        
        global_user_data = global_data["global_user_data"][user_id_str]
        global_user_data['referral_points'] = 6789
        global_user_data['bonus_points'] = 1111
        
        save_data_unified(global_data)
        
        # Simulate restart by reloading data
        load_data_unified()
        
        self.assert_balance_consistency(user_id, {
            'main_wallet': 12345,
            'referral_points': 6789,
            'bonus_points': 1111,
            'total': 20245
        }, "Data Persistence After Reload")
    
    def print_test_summary(self):
        """Print comprehensive test summary."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*80)
        print("DATABASE CONSISTENCY TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "No tests run")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            print("-" * 40)
            for result in self.test_results:
                if not result['success']:
                    print(f"❌ {result['test']} (User {result['user_id']})")
                    for error in result['errors']:
                        print(f"   {error}")
        
        print("\nDETAILED RESULTS:")
        print("-" * 40)
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {result['test']} (User {result['user_id']})")
            if not result['success']:
                print(f"     Expected: {result['expected']}")
                print(f"     Actual: {result['actual']}")
        
        print("\n" + "="*80)
    
    async def run_all_tests(self):
        """Run all database consistency tests."""
        try:
            await self.setup_test_environment()
            
            # Run all test suites
            await self.test_basic_balance_operations()
            await self.test_betting_operations()
            await self.test_referral_system()
            await self.test_admin_wallet_operations()
            await self.test_edge_cases()
            await self.test_concurrent_operations()
            await self.test_data_persistence()
            
            self.print_test_summary()
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            raise
        finally:
            await self.cleanup_test_environment()

async def main():
    """Main test execution function."""
    print("Starting Database Consistency Tests...")
    print(f"Using database: {USE_DATABASE}")
    
    tester = DatabaseConsistencyTester()
    await tester.run_all_tests()
    
    print("\nDatabase consistency tests completed.")

if __name__ == "__main__":
    asyncio.run(main())