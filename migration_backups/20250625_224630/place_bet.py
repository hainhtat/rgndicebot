import json
import sys
from datetime import datetime
from data.file_manager import load_data, save_data
from config.constants import global_data, GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER
from game.game_logic import DiceGame
from handlers.utils import get_current_game, create_new_game

# Load data into global_data
load_data(global_data)

# Chat ID for testing
chat_id = -1002780424700
chat_id_str = str(chat_id)

# Get the current game
chat_data = global_data['all_chat_data'].get(chat_id_str, {})
game = get_current_game(chat_id)

print(f"Current game state: {game.state if game else 'No game'}")

# If game is in GAME_OVER state, create a new game
if not game or game.state == GAME_STATE_OVER:
    print("Creating a new game...")
    game = create_new_game(chat_id)
    print(f"New game created: Match ID #{game.match_id}, State: {game.state}")

# Save data
save_data(global_data)
print("Data saved.")