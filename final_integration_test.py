#!/usr/bin/env python3
"""
Final comprehensive test for PostgreSQL database integration fixes.
Tests the complete flow of place_bet and payout functions with database operations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import USE_DATABASE
from database.connection import init_database, get_db_session
from database.adapter import DatabaseAdapter
from game.game_logic import place_bet, payout
from game.game_logic import DiceGame
from main import load_data_unified, save_data_unified
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_betting_flow():
    """Test the complete betting and payout flow with database integration."""
    print("🎯 Testing Complete Betting Flow with Database Integration")
    print(f"📊 USE_DATABASE: {USE_DATABASE}")
    
    # Test parameters
    chat_id = -1001234567890
    user_id = 987654321
    username = "TestPlayer"
    bet_amount = 100
    
    try:
        # Initialize database
        if USE_DATABASE:
            print("\n1️⃣ Initializing database...")
            init_database()
            print("✅ Database initialized")
        
        # Initialize data structures
        print("\n2️⃣ Loading game data...")
        global_data = load_data_unified()
        
        # Ensure chat data exists
        chat_id_str = str(chat_id)
        if chat_id_str not in global_data:
            global_data[chat_id_str] = {
                "player_stats": {},
                "match_counter": 0,
                "idle_match_counter": 0,
                "match_history": []
            }
        
        chat_data = global_data[chat_id_str]
        
        # Initialize database adapter
        db_adapter = DatabaseAdapter()
        
        # Set up initial player with some funds
        print("\n3️⃣ Setting up test player...")
        if USE_DATABASE:
            # Create/get player in database
            player_stats = db_adapter.get_or_create_player_stats(user_id, chat_id, username)
            # Give player some initial funds
            db_adapter.update_player_stats(user_id, chat_id, 1000, False, 0)  # Add 1000 to score
            player_stats = db_adapter.get_or_create_player_stats(user_id, chat_id, username)
            print(f"✅ Player created in database: {player_stats}")
        else:
            # Create player locally
            user_id_str = str(user_id)
            chat_data["player_stats"][user_id_str] = {
                "user_id": user_id,
                "username": username,
                "score": 1000,
                "total_wins": 0,
                "total_losses": 0,
                "total_bets": 0
            }
            print(f"✅ Player created locally: {chat_data['player_stats'][user_id_str]}")
        
        # Create a test game
        print("\n4️⃣ Creating test game...")
        match_id = chat_data["match_counter"] + 1
        game = DiceGame(match_id, chat_id)
        
        # Test place_bet function
        print("\n5️⃣ Testing place_bet function...")
        result = place_bet(game, user_id, username, "big", bet_amount, chat_data, global_data, chat_id)
        
        if "Bet placed" in result:
            print(f"✅ Bet placed successfully: {result}")
            
            # Check player stats after bet
            if USE_DATABASE:
                updated_stats = db_adapter.get_or_create_player_stats(user_id, chat_id, username)
                print(f"📊 Player stats after bet (DB): {updated_stats}")
            else:
                user_id_str = str(user_id)
                print(f"📊 Player stats after bet (Local): {chat_data['player_stats'][user_id_str]}")
        else:
            print(f"❌ Bet placement failed: {result}")
            return False
        
        # Simulate game completion
        print("\n6️⃣ Simulating game completion...")
        from config.constants import GAME_STATE_CLOSED
        game.state = GAME_STATE_CLOSED
        game.result = (3, 4)  # Dice results as tuple
        game.dice1 = 3
        game.dice2 = 4
        
        # Test payout function
        print("\n7️⃣ Testing payout function...")
        payout_result = payout(game, chat_data, global_data, chat_id)
        
        if payout_result:
            print("✅ Payout processed successfully")
            
            # Check final player stats
            if USE_DATABASE:
                final_stats = db_adapter.get_or_create_player_stats(user_id, chat_id, username)
                print(f"📊 Final player stats (DB): {final_stats}")
            else:
                user_id_str = str(user_id)
                print(f"📊 Final player stats (Local): {chat_data['player_stats'][user_id_str]}")
        else:
            print("❌ Payout processing failed")
            return False
        
        # Test database consistency
        if USE_DATABASE:
            print("\n8️⃣ Testing database consistency...")
            with get_db_session() as session:
                from sqlalchemy import text
                
                # Check if player exists in database
                result = session.execute(
                    text("SELECT * FROM player_stats WHERE user_id = :user_id AND chat_id = :chat_id"),
                    {"user_id": user_id, "chat_id": chat_id}
                ).fetchone()
                
                if result:
                    print(f"✅ Player found in database: score={result.score}, total_bets={result.total_bets}")
                else:
                    print("❌ Player not found in database")
                    return False
        
        print("\n🎉 All integration tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_betting_flow()
    if success:
        print("\n✅ DATABASE INTEGRATION FIXES VERIFIED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n❌ DATABASE INTEGRATION TESTS FAILED!")
        sys.exit(1)