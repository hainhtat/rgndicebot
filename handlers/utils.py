import logging
from typing import Dict, List, Optional, Tuple, Any, Union

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import global_data, get_chat_data_for_id, ALLOWED_GROUP_IDS
from config.settings import MAIN_GAME_GROUP_LINK
from game.game_logic import DiceGame
from config.constants import GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER
from utils.telegram_utils import is_admin, send_message_with_retry
from utils.user_utils import get_user_display_name
from utils.message_formatter import MessageTemplates

logger = logging.getLogger(__name__)


async def check_allowed_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the chat is allowed to use the bot.
    Returns True if allowed, False otherwise.
    """
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    logger.info(f"Checking if chat {chat_id} (type: {chat_type}) is allowed to use the bot")
    logger.info(f"Allowed group IDs: {ALLOWED_GROUP_IDS}")
    
    # Allow private chats (direct messages to the bot)
    if chat_type == "private":
        logger.info(f"Chat {chat_id} is a private chat, allowing access")
        return True
    
    # Check if the chat is in the allowed list
    if ALLOWED_GROUP_IDS and chat_id not in ALLOWED_GROUP_IDS:
        logger.warning(f"Unauthorized access attempt from chat {chat_id}. Not in allowed list: {ALLOWED_GROUP_IDS}")
        try:
            await update.message.reply_text(
                "⚠️ This bot is only available in authorized groups.\n"
                f"Please join our official group: {MAIN_GAME_GROUP_LINK}"
            )
        except Exception as e:
            logger.error(f"Failed to send unauthorized message to chat {chat_id}: {str(e)}")
        return False
    
    logger.info(f"Chat {chat_id} is allowed to use the bot")
    return True


async def check_admin_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user has admin permission.
    Returns True if admin or superadmin, False otherwise.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is a superadmin (they can perform admin actions in any group)
    from config.constants import SUPER_ADMIN_IDS
    if user_id in SUPER_ADMIN_IDS:
        return True
    
    # Check if user is an admin in this group
    admin_status = await is_admin(chat_id, user_id, context)
    
    if not admin_status:
        await update.message.reply_text(MessageTemplates.ADMIN_ONLY_COMMAND)
        return False
    
    return True


def get_current_game(chat_id: int) -> Optional[DiceGame]:
    """
    Gets the current game for a chat if it exists and is not over.
    Returns None if no game is in progress or if the game is over.
    """
    chat_data = get_chat_data_for_id(chat_id)
    current_game = chat_data.get("current_game")
    
    # If there's no game or the game is over, clean up and return None
    if not current_game or current_game.state == GAME_STATE_OVER:
        if current_game and current_game.state == GAME_STATE_OVER:
            # Clean up finished game
            chat_data["current_game"] = None
            from data.file_manager import save_data
            save_data(global_data)
        return None
    
    return current_game


def create_new_game(chat_id: int) -> DiceGame:
    """
    Creates a new game for a chat.
    Returns the new game instance.
    """
    chat_data = get_chat_data_for_id(chat_id)
    
    # Ensure match_counter exists (backward compatibility)
    if "match_counter" not in chat_data:
        chat_data["match_counter"] = 1
    
    match_id = chat_data["match_counter"]
    
    # Create a new game
    game = DiceGame(match_id, chat_id)
    chat_data["current_game"] = game
    chat_data["match_counter"] += 1
    
    return game


async def create_game_status_message(game: DiceGame, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Creates a status message for the current game with instructions on how to play.
    """
    try:
        status = game.get_status()
        logger.info(f"Got game status for game #{status['match_id']} in chat {game.chat_id}")
        
        # Format the message with game instructions
        from utils.message_formatter import MessageTemplates
        message = MessageTemplates.GAME_STARTED.format(match_id=status['match_id']) + "\n\n"
        
        # Game status
        if status['state'] == GAME_STATE_WAITING:
            # Calculate time remaining (60 seconds from game creation)
            from datetime import datetime, timedelta
            time_elapsed = datetime.now() - game.created_at
            time_remaining = timedelta(seconds=60) - time_elapsed
            
            if time_remaining.total_seconds() > 0:
                seconds_left = int(time_remaining.total_seconds())
                message += f"⏱️ *Time remaining:* {seconds_left}s\n\n"
            else:
                message += "⏱️ *Closing soon...*\n\n"
        elif status['state'] == GAME_STATE_CLOSED:
            message += "🔒 *လောင်းကြေးပိတ်ပါပြီ*\n\n"
        elif status['state'] == GAME_STATE_OVER:
            message += f"🏁 *Game over*\nResult: {status['result']}\n\n"
        
        # Add game instructions for text betting
        message += "*လောင်းကြေးထပ်ရန်*\n"
        message += "🔴 *BIG (8-12):* B 500 or BIG 500 လို့ရိုက်ပါ\n"
        message += "⚫ *SMALL (2-6):* S 500 or SMALL 500 လို့ရိုက်ပါ\n"
        message += "🍀 *LUCKY (7):* L 500 or LUCKY 500 လို့ရိုက်ပါ\n\n"
        
        message += "💰 *လျော်မည့်ဆ:*\n"
        message += "- BIG/SMALL: 1.95x\n"
        message += "- LUCKY: 4.5x\n"
        
        logger.info(f"Created game status message: {message}")
        return message
    except Exception as e:
        logger.error(f"Error creating game status message: {str(e)}")
        return f"🎲 Game\n\nStatus: Waiting for bets\n\nError: {str(e)}"


def create_betting_keyboard():
    """
    Create the betting keyboard with buttons for different bet types and amounts.
    Note: As per requirements, buttons have been removed from the opening bet message.
    Users will place bets using text commands only.
    """
    # Return None instead of a keyboard to remove all buttons
    return None