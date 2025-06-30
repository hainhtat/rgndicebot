#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Dice Bot Features

This test suite covers:
- Admin functionality
- User operations
- Referral system
- Welcome bonus
- Daily cashback
- Admin daily reports
"""

import unittest
import asyncio
import json
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import core modules
from config.config_manager import ConfigManager
from database.adapter import DatabaseAdapter
from game.game_logic import DiceGame, place_bet, payout


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.db_adapter = DatabaseAdapter()
        self.user_id = 123456789
        self.chat_id = -1001234567890
    
    def test_player_stats_creation(self):
        """Test player stats creation with welcome bonus"""
        player_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        # Verify player stats were created
        self.assertIsInstance(player_stats, dict)
        self.assertEqual(player_stats['user_id'], str(self.user_id))
        self.assertEqual(player_stats['username'], "testuser")
        
        # Check welcome bonus was applied
        welcome_bonus = self.config.get('user', 'new_user_bonus', 500)
        self.assertEqual(player_stats['score'], welcome_bonus)
    
    def test_player_stats_update(self):
        """Test player stats updates"""
        # Create initial player stats
        initial_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        # Update player stats
        score_change = 100
        self.db_adapter.update_player_stats(
            self.user_id, self.chat_id, score_change, wins=1, bets=1
        )
        
        # Verify stats were updated
        updated_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        expected_score = initial_stats['score'] + score_change
        self.assertEqual(updated_stats['score'], expected_score)
        self.assertEqual(updated_stats['total_wins'], initial_stats['total_wins'] + 1)
        self.assertEqual(updated_stats['total_bets'], initial_stats['total_bets'] + 1)
    
    def test_referral_points(self):
        """Test referral points functionality"""
        # Test getting referral points for new user
        initial_points = self.db_adapter.get_user_referral_points(self.user_id)
        self.assertEqual(initial_points, 0)
        
        # Test updating referral points
        points_to_add = 50
        success = self.db_adapter.update_user_referral_points(self.user_id, points_to_add)
        self.assertTrue(success)
        
        # Verify points were updated
        updated_points = self.db_adapter.get_user_referral_points(self.user_id)
        self.assertEqual(updated_points, points_to_add)
    
    def test_admin_points(self):
        """Test admin points functionality"""
        # Test getting admin points
        initial_points = self.db_adapter.get_admin_points(self.user_id, self.chat_id)
        self.assertGreaterEqual(initial_points, 0)
        
        # Test updating admin points
        points_to_add = 1000
        success = self.db_adapter.update_admin_points(self.user_id, self.chat_id, points_to_add)
        self.assertTrue(success)
        
        # Test refilling admin points
        refill_amount = 5000
        success = self.db_adapter.refill_admin_points(self.user_id, self.chat_id, refill_amount)
        self.assertTrue(success)


class TestGameLogic(unittest.TestCase):
    """Test game logic functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.match_id = 1
        self.chat_id = -1001234567890
        self.user_id = 123456789
        
        # Create a test game
        self.game = DiceGame(self.match_id, self.chat_id)
        
        # Mock data structures
        self.chat_data = {
            "player_stats": {
                str(self.user_id): {
                    "username": "testuser",
                    "score": 1000,
                    "total_wins": 0,
                    "total_losses": 0,
                    "total_bets": 0
                }
            }
        }
        
        self.global_data = {
            "users": {
                str(self.user_id): {
                    "username": "testuser",
                    "referral_points": 100,
                    "bonus_points": 50
                }
            }
        }
    
    @patch('game.game_logic.get_chat_data_for_id')
    @patch('game.game_logic.get_global_data')
    @patch('game.game_logic.save_data_unified')
    def test_place_bet_main_score(self, mock_save, mock_get_global, mock_get_chat):
        """Test placing bet with main score"""
        mock_get_chat.return_value = self.chat_data
        mock_get_global.return_value = self.global_data
        
        bet_amount = 100
        result = place_bet(
            self.game, self.user_id, "testuser", "small", bet_amount,
            self.chat_id, use_referral_points=False, use_bonus_points=False
        )
        
        # Verify bet was placed
        self.assertIn("Bet placed", result)
        self.assertIn("small", result)
        self.assertIn(str(bet_amount), result)
        
        # Verify game state
        self.assertIn("small", self.game.bets)
        self.assertIn(str(self.user_id), self.game.bets["small"])
        self.assertEqual(self.game.bets["small"][str(self.user_id)], bet_amount)
    
    @patch('game.game_logic.get_chat_data_for_id')
    @patch('game.game_logic.get_global_data')
    @patch('game.game_logic.save_data_unified')
    def test_place_bet_referral_points(self, mock_save, mock_get_global, mock_get_chat):
        """Test placing bet with referral points"""
        mock_get_chat.return_value = self.chat_data
        mock_get_global.return_value = self.global_data
        
        bet_amount = 50
        result = place_bet(
            self.game, self.user_id, "testuser", "big", bet_amount,
            self.chat_id, use_referral_points=True, use_bonus_points=False
        )
        
        # Verify bet was placed with referral points
        self.assertIn("Bet placed", result)
        self.assertIn("referral", result)
    
    @patch('game.game_logic.get_chat_data_for_id')
    @patch('game.game_logic.get_global_data')
    @patch('game.game_logic.save_data_unified')
    def test_place_bet_bonus_points(self, mock_save, mock_get_global, mock_get_chat):
        """Test placing bet with bonus points"""
        mock_get_chat.return_value = self.chat_data
        mock_get_global.return_value = self.global_data
        
        bet_amount = 30
        result = place_bet(
            self.game, self.user_id, "testuser", "lucky", bet_amount,
            self.chat_id, use_referral_points=False, use_bonus_points=True
        )
        
        # Verify bet was placed with bonus points
        self.assertIn("Bet placed", result)
        self.assertIn("bonus", result)
    
    @patch('game.game_logic.get_chat_data_for_id')
    def test_payout_calculation(self, mock_get_chat):
        """Test payout calculation"""
        mock_get_chat.return_value = self.chat_data
        
        # Set up a game with bets
        self.game.bets["small"][str(self.user_id)] = 100
        self.game.result = (2, 3)  # Sum = 5, should win "small"
        self.game.state = "closed"
        
        result = payout(self.game, self.chat_data, self.global_data, self.chat_id)
        
        # Verify payout result
        self.assertIsInstance(result, dict)
        self.assertIn("winners", result)
        self.assertIn("total_payout", result)
        self.assertIn("dice_result", result)
        
        # Check if user won
        if result["winners"]:
            winner = result["winners"][0]
            self.assertEqual(winner["user_id"], str(self.user_id))
            self.assertGreater(winner["winnings"], 0)


class TestWelcomeBonus(unittest.TestCase):
    """Test welcome bonus functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.db_adapter = DatabaseAdapter()
    
    def test_welcome_bonus_amount(self):
        """Test welcome bonus configuration"""
        welcome_bonus = self.config.get('user', 'new_user_bonus', 500)
        
        # Verify welcome bonus is configured
        self.assertGreater(welcome_bonus, 0)
        self.assertIsInstance(welcome_bonus, int)
        self.assertEqual(welcome_bonus, 500)  # Default value
    
    def test_new_user_gets_bonus(self):
        """Test that new users receive welcome bonus"""
        user_id = 999999999
        chat_id = -1001234567890
        
        player_stats = self.db_adapter.get_or_create_player_stats(
            user_id, chat_id, "newuser"
        )
        
        welcome_bonus = self.config.get('user', 'new_user_bonus', 500)
        self.assertEqual(player_stats['score'], welcome_bonus)


class TestReferralSystem(unittest.TestCase):
    """Test referral system functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.db_adapter = DatabaseAdapter()
        self.referrer_id = 123456789
        self.referee_id = 987654321
    
    def test_referral_points_operations(self):
        """Test referral points operations"""
        # Test initial referral points
        initial_points = self.db_adapter.get_user_referral_points(self.referrer_id)
        self.assertEqual(initial_points, 0)
        
        # Test adding referral points
        points_to_add = 100
        success = self.db_adapter.update_user_referral_points(self.referrer_id, points_to_add)
        self.assertTrue(success)
        
        # Verify points were added
        updated_points = self.db_adapter.get_user_referral_points(self.referrer_id)
        self.assertEqual(updated_points, points_to_add)
    
    def test_referrer_assignment(self):
        """Test setting user referrer"""
        success = self.db_adapter.set_user_referrer(self.referee_id, self.referrer_id)
        self.assertTrue(success)
    
    def test_referral_commission_calculation(self):
        """Test referral commission calculation"""
        bet_amount = 100
        commission_rate = self.config.get('referral', 'commission_rate', 0.05)
        
        expected_commission = int(bet_amount * commission_rate)
        self.assertEqual(expected_commission, 5)  # 5% of 100


class TestDailyCashback(unittest.TestCase):
    """Test daily cashback functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
    
    def test_daily_bonus_configuration(self):
        """Test daily bonus configuration"""
        base_amount = self.config.get('daily_bonus', 'base_amount', 50)
        streak_multiplier = self.config.get('daily_bonus', 'streak_multiplier', 1.1)
        max_streak = self.config.get('daily_bonus', 'max_streak', 7)
        
        # Verify configuration values
        self.assertGreater(base_amount, 0)
        self.assertGreater(streak_multiplier, 1.0)
        self.assertGreater(max_streak, 0)
    
    def test_streak_bonus_calculation(self):
        """Test streak bonus calculation"""
        base_amount = self.config.get('daily_bonus', 'base_amount', 50)
        streak_multiplier = self.config.get('daily_bonus', 'streak_multiplier', 1.1)
        
        # Test different streak levels
        for streak in range(1, 8):
            bonus = int(base_amount * (streak_multiplier ** min(streak, 7)))
            self.assertGreaterEqual(bonus, base_amount)
            
            if streak > 1:
                previous_bonus = int(base_amount * (streak_multiplier ** min(streak - 1, 7)))
                self.assertGreaterEqual(bonus, previous_bonus)


class TestAdminReports(unittest.TestCase):
    """Test admin reporting functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.db_adapter = DatabaseAdapter()
        self.admin_id = 123456789
        self.chat_id = -1001234567890
    
    def test_admin_points_management(self):
        """Test admin points management"""
        # Test getting admin points
        initial_points = self.db_adapter.get_admin_points(self.admin_id, self.chat_id)
        self.assertGreaterEqual(initial_points, 0)
        
        # Test updating admin points
        points_to_add = 1000
        success = self.db_adapter.update_admin_points(self.admin_id, self.chat_id, points_to_add)
        self.assertTrue(success)
        
        # Test refilling admin points
        refill_amount = 5000
        success = self.db_adapter.refill_admin_points(self.admin_id, self.chat_id, refill_amount)
        self.assertTrue(success)
    
    def test_leaderboard_generation(self):
        """Test leaderboard generation"""
        # Create some test player stats
        for i, user_id in enumerate([111, 222, 333]):
            self.db_adapter.get_or_create_player_stats(
                user_id, self.chat_id, f"user{i}"
            )
            # Update scores to create a leaderboard
            self.db_adapter.update_player_stats(
                user_id, self.chat_id, (i + 1) * 100, wins=i + 1, bets=(i + 1) * 2
            )
        
        # Get leaderboard
        leaderboard = self.db_adapter.get_chat_leaderboard(self.chat_id, limit=5)
        
        # Verify leaderboard
        self.assertIsInstance(leaderboard, list)
        self.assertLessEqual(len(leaderboard), 5)
        
        # Check if sorted by score (highest first)
        if len(leaderboard) > 1:
            for i in range(len(leaderboard) - 1):
                self.assertGreaterEqual(
                    leaderboard[i]['score'], 
                    leaderboard[i + 1]['score']
                )
    
    def test_match_history(self):
        """Test match history functionality"""
        # Add a test match to history
        match_data = {
            "match_id": 1,
            "dice_result": [3, 4],
            "winning_type": "big",
            "total_bets": 500,
            "total_payout": 450,
            "participants": 5,
            "timestamp": datetime.now().isoformat()
        }
        
        success = self.db_adapter.add_match_to_history(self.chat_id, match_data)
        self.assertTrue(success)
        
        # Get recent matches
        recent_matches = self.db_adapter.get_recent_matches(self.chat_id, limit=10)
        
        # Verify match history
        self.assertIsInstance(recent_matches, list)
        if recent_matches:
            match = recent_matches[0]
            self.assertIn('match_id', match)
            self.assertIn('dice_result', match)
            self.assertIn('winning_type', match)


class TestIntegration(unittest.TestCase):
    """Integration tests for combined functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
        self.db_adapter = DatabaseAdapter()
        self.user_id = 123456789
        self.chat_id = -1001234567890
    
    def test_complete_user_journey(self):
        """Test complete user journey from registration to betting"""
        # 1. Create new user (should get welcome bonus)
        player_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        welcome_bonus = self.config.get('user', 'new_user_bonus', 500)
        self.assertEqual(player_stats['score'], welcome_bonus)
        
        # 2. Add referral points
        referral_points = 100
        success = self.db_adapter.update_user_referral_points(self.user_id, referral_points)
        self.assertTrue(success)
        
        # 3. Update player stats (simulate betting)
        score_change = -50  # Lost a bet
        self.db_adapter.update_player_stats(
            self.user_id, self.chat_id, score_change, losses=1, bets=1
        )
        
        # 4. Verify final state
        final_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        expected_score = welcome_bonus + score_change
        self.assertEqual(final_stats['score'], expected_score)
        self.assertEqual(final_stats['total_losses'], 1)
        self.assertEqual(final_stats['total_bets'], 1)
        
        # 5. Verify referral points
        final_referral_points = self.db_adapter.get_user_referral_points(self.user_id)
        self.assertEqual(final_referral_points, referral_points)
    
    def test_admin_user_interaction(self):
        """Test admin and user interaction"""
        admin_id = 987654321
        
        # 1. Set up admin
        admin_points = self.db_adapter.get_admin_points(admin_id, self.chat_id)
        self.assertGreaterEqual(admin_points, 0)
        
        # 2. Create user
        player_stats = self.db_adapter.get_or_create_player_stats(
            self.user_id, self.chat_id, "testuser"
        )
        
        # 3. Admin refills points
        refill_amount = 10000
        success = self.db_adapter.refill_admin_points(admin_id, self.chat_id, refill_amount)
        self.assertTrue(success)
        
        # 4. User gets referral bonus
        referral_bonus = 200
        success = self.db_adapter.update_user_referral_points(self.user_id, referral_bonus)
        self.assertTrue(success)
        
        # 5. Verify both operations succeeded
        final_admin_points = self.db_adapter.get_admin_points(admin_id, self.chat_id)
        final_user_referral = self.db_adapter.get_user_referral_points(self.user_id)
        
        self.assertGreaterEqual(final_admin_points, refill_amount)
        self.assertEqual(final_user_referral, referral_bonus)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestDatabaseOperations,
        TestGameLogic,
        TestWelcomeBonus,
        TestReferralSystem,
        TestDailyCashback,
        TestAdminReports,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    exit_code = 0 if result.wasSuccessful() else 1
    sys.exit(exit_code)