import os
import random
from datetime import datetime

# --- UPDATED: Centralized data structure for all chats and global user data ---
# This dictionary will be populated from the file_manager.
# Do NOT initialize it with default values here, as it will overwrite loaded data.
global_data = {
    "all_chat_data": {}, # Stores chat_id: {player_stats: {...}, match_counter: int, ...}
    # UPDATED: admin_data structure to support per-chat points
    "admin_data": {},    # Stores admin_id: {username: str, chat_points: {chat_id: {points: int, last_refill: datetime}}}
    "global_user_data": {} # NEW: Stores user_id: {username: str, referral_points: int, referred_by: int, pending_referrer_id: int}
}

# --- REMOVED: Database imports as we are no longer using a database ---
# from database import save_admin_data, save_chat_data 

def get_chat_data_for_id(chat_id: int):
    """
    Retrieves or initializes the chat-specific data from global_data.
    This ensures that each chat maintains its own game state, player scores, etc.
    If chat data is not found in global_data (meaning it wasn't loaded from file or is new),
    it initializes a basic structure.
    """
    if chat_id not in global_data["all_chat_data"]:
        global_data["all_chat_data"][chat_id] = {
            # Removed referral-related fields from here, as they are now in global_user_data
            "player_stats": {}, # Stores user_id: {username: str, score: int, wins: int, losses: int, last_active: datetime}
            "match_counter": 1, # Unique ID for each match within a chat
            "match_history": [], # Stores past match results
            "group_admins": [], # Cached list of admin user_ids for this specific chat
            "consecutive_idle_matches": 0 # New: Tracks idle matches for auto-stopping
        }
    return global_data["all_chat_data"][chat_id]

# UPDATED: get_admin_data now takes chat_id
def get_admin_data(admin_id: int, chat_id: int, username: str = "Unknown Admin"):
    """
    Retrieves or initializes admin-specific data from global_data for a specific chat.
    Ensures that admin data is present and updates the username if a valid one is provided.
    Initializes points for the specific chat if they don't exist.
    """
    # Initialize global admin profile if it doesn't exist
    if admin_id not in global_data["admin_data"]:
        global_data["admin_data"][admin_id] = {
            "username": username, # Store initial username
            "chat_points": {} # Initialize chat_points dictionary
        }
    else:
        # Update general admin username if a valid one is provided and different
        existing_username = global_data["admin_data"][admin_id].get("username")
        if username and username != "Unknown Admin" and existing_username != username:
            global_data["admin_data"][admin_id]["username"] = username
    
    # Initialize points for the specific chat if they don't exist
    if chat_id not in global_data["admin_data"][admin_id]["chat_points"]:
        global_data["admin_data"][admin_id]["chat_points"][chat_id] = {
            "points": ADMIN_INITIAL_POINTS,
            "last_refill": None
        }
            
    return global_data["admin_data"][admin_id]["chat_points"][chat_id]


# Hardcoded global administrators (Telegram User IDs)
# These users will always have admin privileges regardless of specific group admin status.
# Replace with actual user IDs for your global admins.
HARDCODED_ADMINS = [
    # 1599213796,
    5965715103, # Replace with a real admin's User ID (e.g., your ID)
    # Add more admin IDs here if needed
]

# Allowed Group IDs
# The bot will only function in these specific groups.
# Replace with the actual Telegram Group IDs where you want the bot to run.
# You can get a group's ID by forwarding a message from the group to @userinfobot
ALLOWED_GROUP_IDS = [
    # -1002295769196,
    # -1002780424700,
    -1002718732381,
    -1002689980361
]


# Initial score for new players
INITIAL_PLAYER_SCORE = 0 # Changed to 0 as per request

# Emojis for results (optional, but adds flair!)
RESULT_EMOJIS = {
    "big": "⬆️",
    "small": "⬇️",
    "lucky": "🍀"
}

# Admin refill constants
ADMIN_INITIAL_POINTS = 10000000 # Admins start with 10,000,000 points, refilled daily

# Referral system constants
REFERRAL_BONUS_POINTS = 500 # Points awarded to referrer when new user joins via their link

# --- UPDATED: Hardcoded main game group link ---
# IMPORTANT: Replace this with an actual permanent invite link you generate manually from your Telegram group.
# This link will be given to users to join the group.
MAIN_GAME_GROUP_LINK = "https://t.me/rgndiceofficial" 
# --- END UPDATED ---
