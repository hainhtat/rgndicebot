import json
import sys
from datetime import datetime

from config.constants import global_data, GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER
from game.game_logic import DiceGame
from handlers.utils import get_current_game, create_new_game, load_data_unified, save_data_unified
from config.settings import USE_DATABASE
from database.adapter import db_adapter

# Load data into global_data
load_data_unified()

# Chat ID for testing
chat_id = -1002780424700
chat_id_str = str(chat_id)

# Get the current game
chat_data = global_data['all_chat_data'].get(chat_id_str, {})
game = get_current_game(chat_id)

print(f"Current game state: {game.state if game else 'No game'}")

# If game is in GAME_OVER state, check if we should create a new game
if not game or game.state == GAME_STATE_OVER:
    # Check for consecutive idle matches before creating new game
    consecutive_idle = chat_data.get("consecutive_idle_matches", 0)
    idle_game_limit = 3  # Same as in bet_handlers.py
    
    if consecutive_idle >= idle_game_limit:
        print(f"Cannot create new game: {consecutive_idle} consecutive idle matches (limit: {idle_game_limit})")
        print("Game is stopped due to inactivity. Use /roll to start a new game.")
    else:
        print("Creating a new game...")
        game = create_new_game(chat_id)
        print(f"New game created: Match ID #{game.match_id}, State: {game.state}")

# Save data
save_data_unified(global_data)
print("Data saved.")