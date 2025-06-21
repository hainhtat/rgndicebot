from datetime import datetime
from config.settings import (
    INITIAL_PLAYER_SCORE,
    ADMIN_INITIAL_POINTS,
    REFERRAL_BONUS_POINTS,
    HARDCODED_ADMINS,
    SUPER_ADMINS,
    MAIN_GAME_GROUP_LINK,
    ALLOWED_GROUP_IDS
)

# Alias for backward compatibility
SUPER_ADMIN_IDS = SUPER_ADMINS

# Game states
GAME_STATE_WAITING = "WAITING_FOR_BETS"
GAME_STATE_CLOSED = "GAME_CLOSED"
GAME_STATE_OVER = "GAME_OVER"

# Bet types
BET_TYPE_BIG = "BIG"
BET_TYPE_SMALL = "SMALL"
BET_TYPE_LUCKY = "LUCKY"

# Dice values
DICE_VALUE_MIN = 1
DICE_VALUE_MAX = 6
DICE_SUM_MIN = 2  # 1 + 1
DICE_SUM_MAX = 12  # 6 + 6
DICE_SUM_BIG_MIN = 8  # Sum >= 8 is considered BIG
DICE_SUM_SMALL_MAX = 6  # Sum <= 6 is considered SMALL
DICE_SUM_LUCKY = 7  # Sum = 7 is LUCKY

# Betting limits (can be overridden by config)
DEFAULT_MIN_BET = 100
DEFAULT_MAX_BET = 1000000

# Payout multipliers (can be overridden by config)
DEFAULT_BIG_MULTIPLIER = 2.0
DEFAULT_SMALL_MULTIPLIER = 2.0
DEFAULT_LUCKY_MULTIPLIER = 5.0

# User bonuses (can be overridden by config)
DEFAULT_NEW_USER_BONUS = 500
DEFAULT_REFERRAL_BONUS = 500

# Cashback settings (can be overridden by config)
DEFAULT_DAILY_CASHBACK_PERCENT = 5
DEFAULT_DAILY_CASHBACK_MIN_LOSS = 1000
DEFAULT_DAILY_CASHBACK_MAX = 10000

# Game timing (can be overridden by config)
DEFAULT_BET_TIME_SECONDS = 60

# Agent system constants
ADMIN_WALLET_AMOUNT = 10000000  # 10 million points for admin wallets
ADMIN_WALLET_REFILL_HOUR = 6  # 6 AM Myanmar time for daily refill
ADMIN_WALLET_REFILL_MINUTE = 0  # Exact minute for refill
DEFAULT_AUTO_ROLL_INTERVAL_SECONDS = 5
DEFAULT_MANUAL_STOP_COOLDOWN_SECONDS = 10  # Cooldown after manual game stop

# Idle game limit (can be overridden by config)
DEFAULT_IDLE_GAME_LIMIT = 3

# Data management (can be overridden by config)
DEFAULT_DATA_FILE = "data.json"
DEFAULT_SAVE_INTERVAL_MINUTES = 5

# Message retry settings (can be overridden by config)
DEFAULT_MESSAGE_RETRY_ATTEMPTS = 3
DEFAULT_MESSAGE_RETRY_DELAY_SECONDS = 1
DEFAULT_MAX_RETRY_DELAY_SECONDS = 30

# Game result emojis
RESULT_EMOJIS = {
    "big": "🔴",
    "small": "⚫",
    "lucky": "🍀"
}

# Global data structure
global_data = {
    "all_chat_data": {},  # Stores chat_id: {player_stats: {...}, match_counter: int, ...}
    "admin_data": {},     # Stores admin_id: {username: str, chat_points: {chat_id: {points: int, last_refill: datetime}}}
    "global_user_data": {}  # Stores user_id: {username: str, referral_points: int, referred_by: int, pending_referrer_id: int}
}


def get_chat_data_for_id(chat_id: int):
    """
    Retrieves or initializes the chat-specific data from global_data.
    This ensures that each chat maintains its own game state, player scores, etc.
    """
    chat_id_str = str(chat_id)  # Convert to string to match JSON serialization
    if chat_id_str not in global_data["all_chat_data"]:
        global_data["all_chat_data"][chat_id_str] = {
            "player_stats": {},
            "match_counter": 1,
            "match_history": [],
            "group_admins": [],  # Will store a list of admin user IDs for the chat
            "consecutive_idle_matches": 0,  # Counter for idle matches
        }
    return global_data["all_chat_data"][chat_id_str]


def get_admin_data(admin_id: int, chat_id: int, username: str = "Unknown Admin"):
    """
    Retrieves or initializes an admin's data, structured to handle points per chat.
    """
    admin_id_str = str(admin_id)
    chat_id_str = str(chat_id)

    # Initialize general admin profile if it doesn't exist
    if admin_id_str not in global_data["admin_data"]:
        global_data["admin_data"][admin_id_str] = {
            "username": username,
            "chat_points": {}
        }
    
    # Update username if a new one is provided
    global_data["admin_data"][admin_id_str]["username"] = username

    # Initialize per-chat data for the admin if it doesn't exist
    if chat_id_str not in global_data["admin_data"][admin_id_str]["chat_points"]:
        global_data["admin_data"][admin_id_str]["chat_points"][chat_id_str] = {
            "points": ADMIN_WALLET_AMOUNT,
            "last_refill": None
        }
    
    return global_data["admin_data"][admin_id_str]["chat_points"][chat_id_str]