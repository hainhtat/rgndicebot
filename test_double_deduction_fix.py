#!/usr/bin/env python3
"""
Test script to verify the double deduction fix in place_bet function
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test both database and non-database modes
from game.game_logic import DiceGame, place_bet
from config.constants import BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY, GAME_STATE_WAITING
from config import settings
from main import load_data_unified, save_data_unified
from utils.user_utils import get_or_create_global_user_data

def test_double_deduction_fix():
    """Test that wallet is not deducted twice in place_bet function"""
    print("🧪 Testing Double Deduction Fix...")
    
    # Test parameters
    test_user_id = 999999999
    test_chat_id = -999999999
    test_username = "DoubleDeductionTestUser"
    initial_balance = 1000
    bet_amount = 100
    
    print(f"📊 USE_DATABASE: {settings.USE_DATABASE}")
    
    # Test with database disabled first
    print("\n=== Testing with Database DISABLED ===")
    original_use_db = settings.USE_DATABASE
    settings.USE_DATABASE = False
    
    try:
        # Create test data
        global_data = load_data_unified()
        
        # Initialize chat data
        if 'all_chat_data' not in global_data:
            global_data['all_chat_data'] = {}
        if str(test_chat_id) not in global_data['all_chat_data']:
            global_data['all_chat_data'][str(test_chat_id)] = {
                'player_stats': {},
                'current_game': None
            }
        
        chat_data = global_data['all_chat_data'][str(test_chat_id)]
        
        # Create player with initial balance
        chat_data['player_stats'][str(test_user_id)] = {
            'username': test_username,
            'score': initial_balance,
            'total_bets': 0,
            'total_wins': 0,
            'total_losses': 0
        }
        
        # Create global user data
        global_user_data = get_or_create_global_user_data(test_user_id, username=test_username)
        global_user_data['referral_points'] = 0
        global_user_data['bonus_points'] = 0
        
        # Create a new game
        game = DiceGame(match_id="test_double_deduction", chat_id=test_chat_id)
        game.state = GAME_STATE_WAITING
        
        print(f"Initial balance: {chat_data['player_stats'][str(test_user_id)]['score']}")
        
        # Place a bet
        try:
            result_message = place_bet(
                game=game,
                user_id=test_user_id,
                username=test_username,
                bet_type=BET_TYPE_BIG,
                amount=bet_amount,
                chat_data=chat_data,
                global_data=global_data,
                chat_id=test_chat_id
            )
            
            final_balance = chat_data['player_stats'][str(test_user_id)]['score']
            expected_balance = initial_balance - bet_amount
            
            print(f"Final balance: {final_balance}")
            print(f"Expected balance: {expected_balance}")
            print(f"Result message: {result_message}")
            
            if final_balance == expected_balance:
                print("✅ Non-database mode test PASSED")
            else:
                print("❌ Non-database mode test FAILED")
                print(f"Balance difference: {final_balance - expected_balance}")
                
        except Exception as e:
            print(f"❌ Error in non-database test: {e}")
            
    finally:
        # Restore original database setting
        settings.USE_DATABASE = original_use_db
    
    # Test with database enabled if available
    if original_use_db:
        print("\n=== Testing with Database ENABLED ===")
        settings.USE_DATABASE = True
        
        try:
            from database.adapter import DatabaseAdapter
            db_adapter = DatabaseAdapter()
            
            # Create fresh test data
            test_user_id_2 = 888888888
            test_chat_id_2 = -888888888
            
            # Get or create player stats in database
            player_stats = db_adapter.get_or_create_player_stats(
                test_user_id_2, test_chat_id_2, "DBTestUser"
            )
            
            # Set initial balance
            db_adapter.update_player_stats(
                test_user_id_2, test_chat_id_2, 
                initial_balance - player_stats['score'], False, 0
            )
            
            # Get updated stats
            updated_stats = db_adapter.get_or_create_player_stats(
                test_user_id_2, test_chat_id_2, "DBTestUser"
            )
            
            print(f"Initial DB balance: {updated_stats['score']}")
            
            # Create game and chat data
            global_data = load_data_unified()
            if 'all_chat_data' not in global_data:
                global_data['all_chat_data'] = {}
            if str(test_chat_id_2) not in global_data['all_chat_data']:
                global_data['all_chat_data'][str(test_chat_id_2)] = {
                    'player_stats': {},
                    'current_game': None
                }
            
            chat_data = global_data['all_chat_data'][str(test_chat_id_2)]
            
            # Create global user data
            global_user_data = get_or_create_global_user_data(test_user_id_2, username="DBTestUser")
            global_user_data['referral_points'] = 0
            global_user_data['bonus_points'] = 0
            
            # Create a new game
            game = DiceGame(match_id="test_db_double_deduction", chat_id=test_chat_id_2)
            game.state = GAME_STATE_WAITING
            
            # Place a bet
            try:
                result_message = place_bet(
                    game=game,
                    user_id=test_user_id_2,
                    username="DBTestUser",
                    bet_type=BET_TYPE_BIG,
                    amount=bet_amount,
                    chat_data=chat_data,
                    global_data=global_data,
                    chat_id=test_chat_id_2
                )
                
                # Get final balance from database
                final_stats = db_adapter.get_or_create_player_stats(
                    test_user_id_2, test_chat_id_2, "DBTestUser"
                )
                
                final_balance = final_stats['score']
                expected_balance = initial_balance - bet_amount
                
                print(f"Final DB balance: {final_balance}")
                print(f"Expected balance: {expected_balance}")
                print(f"Result message: {result_message}")
                
                if final_balance == expected_balance:
                    print("✅ Database mode test PASSED")
                else:
                    print("❌ Database mode test FAILED")
                    print(f"Balance difference: {final_balance - expected_balance}")
                    
            except Exception as e:
                print(f"❌ Error in database test: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"❌ Database test setup error: {e}")
            print("Skipping database test")
    
    print("\n🎯 Double deduction fix test completed!")

if __name__ == "__main__":
    test_double_deduction_fix()