import json
import sys
from datetime import datetime
from data.file_manager import load_data
from config.constants import global_data, GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER

# Load data into global_data
load_data(global_data)

# Check all chat data
for chat_id_str, chat_data in global_data.get('all_chat_data', {}).items():
    print(f"\nChat ID: {chat_id_str}")
    
    # Check if there's a current game
    game = chat_data.get('current_game')
    if game:
        print(f"  Game found: Match ID #{game.match_id}")
        print(f"  Game state: {game.state}")
        print(f"  Created at: {game.created_at}")
        print(f"  Time elapsed: {(datetime.now() - game.created_at).total_seconds()} seconds")
        
        # Check bets
        total_bets = sum(sum(bets.values()) for bets in game.bets.values())
        print(f"  Total bets: {total_bets}")
        
        # Print detailed bet information
        for bet_type, bets in game.bets.items():
            if bets:
                print(f"    {bet_type} bets:")
                for user_id, amount in bets.items():
                    print(f"      User {user_id}: {amount}")
    else:
        print("  No current game found")