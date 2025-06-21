import logging
from datetime import datetime
from typing import Dict, Optional, Any, Tuple

import telegram
from telegram.ext import ContextTypes

from config.constants import global_data
from config.settings import REFERRAL_BONUS_POINTS
from config.messages import (
    ERROR_SELF_REFERRAL, ERROR_USER_DATA_CREATION, ERROR_REFERRER_NOT_FOUND,
    ERROR_ALREADY_REFERRED, ERROR_CHAT_DATA_NOT_FOUND, ERROR_PLAYER_NOT_FOUND,
    SUCCESS_REFERRAL_WELCOME, SUCCESS_REFERRAL_BONUS, SUCCESS_POINTS_ADDED,
    SUCCESS_POINTS_DEDUCTED, SUCCESS_WELCOME_BONUS, INFO_WELCOME_BONUS_ALREADY_RECEIVED,
    FALLBACK_USER_NAME, FALLBACK_USERNAME_DISPLAY, FALLBACK_FULL_NAME_USERNAME
)
from data.file_manager import save_data

logger = logging.getLogger(__name__)


def get_or_create_global_user_data(user_id: int, first_name: Optional[str] = None, 
                                  last_name: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves or initializes a user's global data (e.g., referral points, display names).
    Ensures that user data is present and updates names if more complete ones are provided.
    """
    user_id_str = str(user_id)
    
    if user_id_str not in global_data["global_user_data"]:
        # Initialize with the best available name
        full_name_init = f"{first_name or ''} {last_name or ''}".strip()
        if not full_name_init:  # If no first/last name, try username
            full_name_init = username if username else f"User {user_id}"

        global_data["global_user_data"][user_id_str] = {
            "full_name": full_name_init,
            "username": username,
            "referral_points": 0,
            "referred_by": None,
            "welcome_bonus_received": False
        }
    else:
        # Update existing user's data with more complete info if available
        user_data = global_data["global_user_data"][user_id_str]

        # Construct new full_name from provided parts
        new_full_name = f"{first_name or ''} {last_name or ''}".strip()

        # Only update full_name if the new one is not empty and different from current,
        # or if the current one is a generic placeholder.
        if new_full_name and (user_data.get("full_name") == f"User {user_id}" or user_data.get("full_name") != new_full_name):
            user_data["full_name"] = new_full_name

        # Only update username if the new one is not empty and different from current,
        # or if the current one is None.
        if username and (user_data.get("username") is None or user_data.get("username") != username):
            user_data["username"] = username

    return global_data["global_user_data"][user_id_str]


async def get_user_display_name(context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                               chat_id: Optional[int] = None) -> str:
    """
    Attempts to get the display name for a user ID, formatted as "Name (username)".
    Prioritizes cached data, then fetches from Telegram API to update cache.
    """
    user_info = global_data["global_user_data"].get(str(user_id))
    cached_full_name = user_info.get("full_name") if user_info else None
    cached_username = user_info.get("username") if user_info else None

    # Try to fetch fresh data from Telegram API
    fetched_user = None
    try:
        # Prioritize getting from chat_member for more reliable first/last name
        if chat_id:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            fetched_user = chat_member.user
        else:  # Fallback to get_chat if chat_id not available (e.g., from direct message to bot)
            fetched_user = await context.bot.get_chat(user_id)
    except Exception as e:
        logger.debug(f"Failed to fetch user details for {user_id} from Telegram API: {e}")

    if fetched_user:
        current_full_name = fetched_user.full_name
        current_username = fetched_user.username

        # Update global_user_data with the latest fetched info
        get_or_create_global_user_data(user_id, fetched_user.first_name, fetched_user.last_name, username=fetched_user.username)

        # Decide display format
        if current_full_name and current_username and current_username.strip():
            from utils.formatting import escape_markdown_username
            return f"{escape_markdown_username(current_full_name)} (@{escape_markdown_username(current_username)})"
        elif current_full_name:
            from utils.formatting import escape_markdown_username
            return escape_markdown_username(current_full_name)
        elif current_username and current_username.strip():
            from utils.formatting import escape_markdown_username
            return f"@{escape_markdown_username(current_username)}"
        else:
            return FALLBACK_USER_NAME.format(user_id=user_id)  # Fallback if fetched user has no name/username
    elif cached_full_name or cached_username:
        # Fallback to cached data if API fetch failed but we have data
        if cached_full_name and cached_username and cached_username.strip():
            from utils.formatting import escape_markdown_username
            return f"{escape_markdown_username(cached_full_name)} (@{escape_markdown_username(cached_username)})"
        elif cached_full_name:
            from utils.formatting import escape_markdown_username
            return escape_markdown_username(cached_full_name)
        elif cached_username and cached_username.strip():
            from utils.formatting import escape_markdown_username
            return f"@{escape_markdown_username(cached_username)}"
    else:
        return FALLBACK_USER_NAME.format(user_id=user_id)  # Final fallback if no data at all


async def process_referral(user_id: int, referrer_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Processes a simple referral between two users.
    Only stores the referral relationship but doesn't award points yet.
    Points are awarded when the user joins the main group.
    Returns a tuple of (success, message, referrer_data).
    """
    user_id_str = str(user_id)
    referrer_id_str = str(referrer_id)
    
    # Check if user is trying to refer themselves
    if user_id == referrer_id:
        return False, ERROR_SELF_REFERRAL, None
    
    # Make sure both users have data entries
    # Try to get user info from context if possible
    try:
        user_info = await context.bot.get_chat(user_id)
        get_or_create_global_user_data(user_id, user_info.first_name, user_info.last_name, user_info.username)
    except Exception as e:
        logger.error(f"Failed to get user info for {user_id}: {e}")
        # Still create an entry if it doesn't exist
        if user_id_str not in global_data["global_user_data"]:
            get_or_create_global_user_data(user_id)
    
    try:
        referrer_info = await context.bot.get_chat(referrer_id)
        get_or_create_global_user_data(referrer_id, referrer_info.first_name, referrer_info.last_name, referrer_info.username)
    except Exception as e:
        logger.error(f"Failed to get referrer info for {referrer_id}: {e}")
        # Still create an entry if it doesn't exist
        if referrer_id_str not in global_data["global_user_data"]:
            get_or_create_global_user_data(referrer_id)
    
    # Get user data after ensuring they exist
    user_data = global_data["global_user_data"].get(user_id_str)
    referrer_data = global_data["global_user_data"].get(referrer_id_str)
    
    # Check if user data exists after our attempts to create it
    if not user_data:
        return False, ERROR_USER_DATA_CREATION, None
    
    if not referrer_data:
        return False, ERROR_REFERRER_NOT_FOUND, None
    
    # Check if user has already been referred
    if user_data.get("referred_by") is not None:
        return False, ERROR_ALREADY_REFERRED, None
    
    # Store the referral relationship but don't award points yet
    # Points will be awarded when the user joins the main group
    user_data["referred_by"] = referrer_id
    user_data["referral_pending"] = True  # Mark that this referral is pending (points not awarded yet)
    
    # Save the updated data
    save_data(global_data)
    
    # Get referrer name
    referrer_name = referrer_data.get('full_name', FALLBACK_USER_NAME.format(user_id=referrer_id))
    
    # Create a nicer formatted success message
    success_message = SUCCESS_REFERRAL_WELCOME.format(referrer_name=referrer_name)
    
    return True, success_message, referrer_data


async def process_pending_referral(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, int, str]:
    """
    Processes a pending referral when a user joins the main group.
    Awards points to the referrer and sends them a notification.
    Returns a tuple of (success, referrer_id, message).
    """
    user_id_str = str(user_id)
    
    # Get user data
    user_data = global_data["global_user_data"].get(user_id_str)
    
    # Check if user data exists and has a referrer (but not already processed)
    if not user_data or user_data.get("referred_by") is None:
        return False, 0, ""
    
    # Check if this referral has already been processed
    if not user_data.get("referral_pending", False):
        return False, 0, ""
    
    # Get referrer data
    referrer_id = user_data.get("referred_by")
    referrer_id_str = str(referrer_id)
    referrer_data = global_data["global_user_data"].get(referrer_id_str)
    
    if not referrer_data:
        return False, 0, ""
    
    # Award points to the referrer
    referrer_data["referral_points"] = referrer_data.get("referral_points", 0) + REFERRAL_BONUS_POINTS
    
    # Mark referral as processed
    user_data["referral_pending"] = False
    
    # Save the updated data
    save_data(global_data)
    
    # Get user and referrer names
    try:
        user_info = await context.bot.get_chat(user_id)
        user_name = user_info.full_name
    except Exception:
        user_name = user_data.get('full_name', FALLBACK_USER_NAME.format(user_id=user_id))
    
    referrer_name = referrer_data.get('full_name', FALLBACK_USER_NAME.format(user_id=referrer_id))
    total_referral_points = referrer_data.get("referral_points", 0)
    
    # Create a notification message for the referrer
    notification_message = SUCCESS_REFERRAL_BONUS.format(
        user_name=user_name,
        bonus_points=REFERRAL_BONUS_POINTS,
        total_points=total_referral_points
    )
    
    return True, referrer_id, notification_message


def adjust_user_score(user_id: int, chat_id: int, amount: int, is_admin: bool = False) -> Tuple[bool, str]:
    """
    Adjusts a user's score by the specified amount.
    Returns a tuple of (success, message).
    """
    user_id_str = str(user_id)
    
    # Get chat data
    chat_data = global_data["all_chat_data"].get(chat_id)
    if not chat_data:
        return False, ERROR_CHAT_DATA_NOT_FOUND
    
    # Get player stats
    player_stats = chat_data["player_stats"].get(user_id_str)
    if not player_stats:
        return False, ERROR_PLAYER_NOT_FOUND
    
    # Adjust score
    old_score = player_stats["score"]
    player_stats["score"] += amount
    
    # Ensure score doesn't go below 0 for non-admin adjustments
    if not is_admin and player_stats["score"] < 0:
        player_stats["score"] = 0
    
    # Save the updated data
    save_data(global_data)
    
    # Return success message
    username = player_stats.get('username', FALLBACK_USER_NAME.format(user_id=user_id))
    if amount > 0:
        return True, SUCCESS_POINTS_ADDED.format(amount=amount, username=username, score=player_stats['score'])
    else:
        return True, SUCCESS_POINTS_DEDUCTED.format(amount=abs(amount), username=username, score=player_stats['score'])


def process_welcome_bonus(user_id: int, chat_id: int, first_name: Optional[str] = None, 
                         last_name: Optional[str] = None, username: Optional[str] = None) -> Tuple[bool, str]:
    """
    Process welcome bonus for a new group member.
    Returns (success, message) tuple.
    Prevents duplicate welcome bonuses.
    """
    from config.settings import WELCOME_BONUS_POINTS
    
    # Get or create global user data
    user_data = get_or_create_global_user_data(user_id, first_name, last_name, username)
    
    # Check if user has already received welcome bonus
    if user_data.get("welcome_bonus_received", False):
        logger.info(f"User {user_id} has already received welcome bonus, skipping")
        return False, INFO_WELCOME_BONUS_ALREADY_RECEIVED
    
    # Get or create player stats for this chat
    chat_id_str = str(chat_id)
    if chat_id_str not in global_data["all_chat_data"]:
        global_data["all_chat_data"][chat_id_str] = {
            "player_stats": {},
            "match_counter": 1,
            "match_history": [],
            "group_admins": [],
            "consecutive_idle_matches": 0
        }
    
    user_id_str = str(user_id)
    if user_id_str not in global_data["all_chat_data"][chat_id_str]["player_stats"]:
        global_data["all_chat_data"][chat_id_str]["player_stats"][user_id_str] = {
            "username": username or first_name or FALLBACK_USER_NAME.format(user_id=user_id),
            "score": 0,
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "last_active": datetime.now().isoformat()
        }
    
    # Add welcome bonus to player's score
    player_stats = global_data["all_chat_data"][chat_id_str]["player_stats"][user_id_str]
    player_stats["score"] += WELCOME_BONUS_POINTS
    player_stats["last_active"] = datetime.now().isoformat()
    
    # Mark welcome bonus as received
    user_data["welcome_bonus_received"] = True
    
    # Save the updated data
    save_data(global_data)
    
    logger.info(f"Welcome bonus of {WELCOME_BONUS_POINTS} points awarded to user {user_id} in chat {chat_id}")
    
    return True, SUCCESS_WELCOME_BONUS.format(bonus_points=WELCOME_BONUS_POINTS)