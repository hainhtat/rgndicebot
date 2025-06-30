#!/usr/bin/env python3
"""
Bot Functionality Tests

This test suite covers core bot functionality:
- Configuration management
- Game logic
- Basic functionality verification
"""

import unittest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import core modules
from config.config_manager import ConfigManager
from game.game_logic import DiceGame


class TestConfigurationManagement(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        """Set up test environment"""
        self.config = ConfigManager()
    
    def test_welcome_bonus_configuration(self):
        """Test welcome bonus configuration"""
        welcome_bonus = self.config.get('user', 'new_user_bonus', 500)
        
        # Verify welcome bonus is configured
        self.assertGreater(welcome_bonus, 0)
        self.assertIsInstance(welcome_bonus, int)
        print(f"✓ Welcome bonus configured: {welcome_bonus}")
    
    def test_referral_configuration(self):
        """Test referral system configuration"""
        commission_rate = self.config.get('referral', 'commission_rate', 0.05)
        
        # Verify referral configuration
        self.assertGreater(commission_rate, 0)
        self.assertLess(commission_rate, 1.0)
        print(f"✓ Referral commission rate: {commission_rate * 100}%")
    
    def test_daily_bonus_configuration(self):
        """Test daily bonus configuration"""
        base_amount = self.config.get('daily_bonus', 'base_amount', 50)
        streak_multiplier = self.config.get('daily_bonus', 'streak_multiplier', 1.1)
        max_streak = self.config.get('daily_bonus', 'max_streak', 7)
        
        # Verify configuration values
        self.assertGreater(base_amount, 0)
        self.assertGreater(streak_multiplier, 1.0)
        self.assertGreater(max_streak, 0)
        print(f"✓ Daily bonus: base={base_amount}, multiplier={streak_multiplier}, max_streak={max_streak}")
    
    def test_betting_limits_configuration(self):
        """Test betting limits configuration"""
        min_bet = self.config.get('game', 'min_bet', 10)
        max_bet = self.config.get('game', 'max_bet', 1000)
        
        # Verify betting limits
        self.assertGreater(min_bet, 0)
        self.assertGreater(max_bet, min_bet)
        print(f"✓ Betting limits: min={min_bet}, max={max_bet}")


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
    
    def test_dice_game_creation(self):
        """Test dice game creation"""
        game = DiceGame(1, self.chat_id)
        
        # Verify game initialization
        self.assertEqual(game.match_id, 1)
        self.assertEqual(game.chat_id, self.chat_id)
        self.assertEqual(game.state, "WAITING_FOR_BETS")
        self.assertIsInstance(game.bets, dict)
        
        # Verify bet types are initialized
        self.assertIn("BIG", game.bets)
        self.assertIn("SMALL", game.bets)
        self.assertIn("LUCKY", game.bets)
        
        print(f"✓ Dice game created successfully with match_id={game.match_id}")
    
    def test_game_status(self):
        """Test game status retrieval"""
        status = self.game.get_status()
        
        # Verify status contains required fields
        required_fields = ['match_id', 'chat_id', 'state', 'bets', 'participants', 'result']
        for field in required_fields:
            self.assertIn(field, status)
        
        # Verify status values
        self.assertEqual(status['match_id'], self.match_id)
        self.assertEqual(status['chat_id'], self.chat_id)
        self.assertEqual(status['state'], "WAITING_FOR_BETS")
        
        print(f"✓ Game status retrieved successfully")
    
    def test_game_configuration(self):
        """Test game configuration values"""
        # Verify game has proper configuration
        self.assertGreater(self.game.min_bet, 0)
        self.assertGreater(self.game.max_bet, self.game.min_bet)
        self.assertGreater(self.game.big_multiplier, 1.0)
        self.assertGreater(self.game.small_multiplier, 1.0)
        self.assertGreater(self.game.lucky_multiplier, 1.0)
        
        print(f"✓ Game configuration: min_bet={self.game.min_bet}, max_bet={self.game.max_bet}")
        print(f"✓ Multipliers: big={self.game.big_multiplier}, small={self.game.small_multiplier}, lucky={self.game.lucky_multiplier}")


class TestBotIntegration(unittest.TestCase):
    """Test bot integration and core functionality"""
    
    def test_imports_successful(self):
        """Test that all core modules can be imported successfully"""
        try:
            from config.config_manager import ConfigManager
            from game.game_logic import DiceGame
            from config.constants import GAME_STATE_WAITING, BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY
            from utils.error_handler import BotError, GameStateError, InvalidBetError
            
            print("✓ All core modules imported successfully")
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import core modules: {e}")
    
    def test_constants_defined(self):
        """Test that required constants are properly defined"""
        from config.constants import (
            GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER,
            BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY,
            DEFAULT_MIN_BET, DEFAULT_MAX_BET
        )
        
        # Verify constants are strings/numbers as expected
        self.assertIsInstance(GAME_STATE_WAITING, str)
        self.assertIsInstance(BET_TYPE_BIG, str)
        self.assertIsInstance(DEFAULT_MIN_BET, int)
        self.assertIsInstance(DEFAULT_MAX_BET, int)
        
        print(f"✓ Constants defined: {GAME_STATE_WAITING}, {BET_TYPE_BIG}, {BET_TYPE_SMALL}, {BET_TYPE_LUCKY}")
    
    def test_error_handling_classes(self):
        """Test that error handling classes are properly defined"""
        from utils.error_handler import BotError, GameStateError, InvalidBetError
        
        # Test that error classes can be instantiated
        bot_error = BotError("Test error")
        game_error = GameStateError("Test game error")
        bet_error = InvalidBetError("Test bet error")
        
        self.assertIsInstance(bot_error, Exception)
        self.assertIsInstance(game_error, Exception)
        self.assertIsInstance(bet_error, Exception)
        
        print("✓ Error handling classes working properly")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎲 DICE BOT FUNCTIONALITY TESTS")
    print("="*60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestConfigurationManagement,
        TestGameLogic,
        TestBotIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print(f"✅ SUCCESS: All tests passed!")
        success_rate = 100.0
    else:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"⚠️  SUCCESS RATE: {success_rate:.1f}%")
    
    print("="*60)
    
    # Exit with appropriate code
    exit_code = 0 if result.wasSuccessful() else 1
    sys.exit(exit_code)