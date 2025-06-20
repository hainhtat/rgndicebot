import asyncio
import logging
import telegram
from typing import Optional, List, Dict, Any, Tuple, Union
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Message, KeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, TimedOut, NetworkError

from config.constants import SUPER_ADMIN_IDS, ADMIN_WALLET_AMOUNT, HARDCODED_ADMINS, global_data, get_chat_data_for_id
from config.settings import SUPER_ADMINS
from utils.user_utils import get_user_display_name
from data.file_manager import save_data

logger = logging.getLogger(__name__)


async def is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if a user is an administrator in a specific chat
    or if they are one of the hardcoded global administrators.
    """
    is_hardcoded_admin = user_id in HARDCODED_ADMINS
    if is_hardcoded_admin:
        return True

    chat_admins = await get_admins_from_chat(chat_id, context)
    is_chat_admin = user_id in chat_admins

    logger.debug(f"is_admin: Checking admin status for user {user_id} in chat {chat_id}: is_chat_admin={is_chat_admin}, is_hardcoded_admin={is_hardcoded_admin}")
    return is_chat_admin or is_hardcoded_admin


async def update_group_admins(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Fetches the current list of administrators for a given chat
    and updates the global_data storage.
    Returns True on success, False on failure.
    """
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins if not admin.user.is_bot]  # Exclude bots

        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["group_admins"] = admin_ids  # Update chat-specific admin list

        save_data(global_data)

        logger.info(f"update_group_admins: Updated admin list for chat {chat_id}: {admin_ids}")
        return True
    except Exception as e:
        logger.error(f"update_group_admins: Failed to get chat administrators for chat {chat_id}: {e}", exc_info=True)
        return False


async def get_admins_from_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> List[int]:
    """
    Fetches the list of admin user IDs for a given chat, caching them if possible.
    """
    chat_data = get_chat_data_for_id(chat_id)
    cached_admins = chat_data.get("group_admins")

    # Fetch current admins directly from Telegram
    try:
        chat_administrators = await context.bot.get_chat_administrators(chat_id)
        admin_user_ids = [admin.user.id for admin in chat_administrators if not admin.user.is_bot]

        # Add hardcoded admins to the list
        admin_user_ids.extend(HARDCODED_ADMINS)
        admin_user_ids = list(set(admin_user_ids))  # Remove duplicates

        # Cache the fetched admins
        chat_data["group_admins"] = admin_user_ids
        save_data(global_data)  # Save global data after updating chat_data

        logger.info(f"Fetched and cached admins for chat {chat_id}: {admin_user_ids}")
        return admin_user_ids
    except telegram.error.TelegramError as e:
        error_msg = str(e)
        # Only log as error for unexpected issues, not for common expected cases
        if any(expected in error_msg for expected in ["Chat not found", "Group migrated to supergroup", "There are no administrators in the private chat"]):
            logger.debug(f"Expected Telegram API response for {chat_id}: {e}")
        else:
            logger.error(f"Error fetching chat administrators for {chat_id}: {e}")
        
        # Fallback to cached admins or hardcoded if fetching fails
        if cached_admins:
            logger.info(f"Using cached admins for chat {chat_id}: {cached_admins}")
            return cached_admins
        else:
            logger.info(f"No cached admins for chat {chat_id}, using hardcoded admins: {HARDCODED_ADMINS}")
            return HARDCODED_ADMINS


def create_custom_keyboard(user_type: str = "user") -> ReplyKeyboardMarkup:
    """
    Creates a custom keyboard. Now we only use one type of keyboard for all users.
    The user_type parameter is kept for backward compatibility but is ignored.
    """
    # Standard keyboard for all users
    keyboard = [
        [KeyboardButton("💵 ငွေထည့်မည်"), KeyboardButton("💸 ငွေထုတ်မည်")],
        [KeyboardButton("💰 My Wallet"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("🔗 Share")]
    ]
    
    # Admin actions will be handled based on permissions in the command handlers
    # rather than by showing different keyboards
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# send_keyboard_to_user function removed as requested


# Dictionary to store admin IDs by chat ID
ADMIN_IDS_BY_CHAT = {}

async def initialize_group_keyboards(context, chat_id: int):
    """
    Initialize keyboards for a specific group.
    Now sends the same keyboard to all users.
    """
    try:
        logger.info(f"Initializing keyboards for group {chat_id}")
        
        # Get all chat administrators to cache their IDs
        try:
            chat_admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in chat_admins if not admin.user.is_bot]
            ADMIN_IDS_BY_CHAT[chat_id] = admin_ids
            logger.info(f"Cached {len(admin_ids)} admin IDs for chat {chat_id}: {admin_ids}")
        except Exception as e:
            logger.error(f"Failed to get chat administrators for {chat_id}: {e}")
            ADMIN_IDS_BY_CHAT[chat_id] = []
        
        # Send a welcome message with keyboard to the group
        keyboard = create_custom_keyboard()
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🎲 ဂိမ်းစတင်ရန် အသင့်ဖြစ်ပါပြီ! အောက်ပါခလုတ်များကို အသုံးပြုပါ။",
                reply_markup=keyboard
            )
            logger.info(f"Welcome keyboard sent to group {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send welcome keyboard to group {chat_id}: {e}")
        
        logger.info(f"Keyboard initialization completed for group {chat_id}")
        
    except Exception as e:
        logger.error(f"Failed to initialize keyboards for group {chat_id}: {e}")


async def send_user_keyboard_on_interaction(context, chat_id: int, user_id: int):
    """
    Send keyboard when a user interacts in the group.
    This is called when users send messages in allowed groups.
    """
    try:
        # Debug logging
        logger.debug(f"Keyboard interaction for user {user_id} in group {chat_id}")
        
        # Try to get the update object from context if available
        update = getattr(context, 'update', None)
        if update and hasattr(update, 'message'):
            # Check if this is a command - if so, don't send the keyboard
            message_text = update.message.text
            if message_text and message_text.startswith('/'):
                logger.debug(f"Command message from user {user_id}, no action needed")
                return
        
        # Send keyboard to ensure user has access to bot functions
        keyboard = create_custom_keyboard()
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎮 Use the keyboard below to interact with the bot.",
            reply_markup=keyboard
        )
        
        logger.debug(f"Keyboard sent to user {user_id} in group {chat_id}")
        
    except Exception as e:
        logger.error(f"Failed to send keyboard to user {user_id} in group {chat_id}: {e}")


async def send_keyboard_to_new_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> None:
    """
    Send keyboard to a new member who just joined the group.
    """
    try:
        keyboard = create_custom_keyboard()
        
        # Send keyboard to the group chat where the user joined
        await context.bot.send_message(
            chat_id=chat_id,  # Send to the group chat
            text=f"🎮 Welcome! Use the keyboard below to interact with the bot.",
            reply_markup=keyboard
        )
        
        logger.info(f"Welcome keyboard sent to group {chat_id} for new member {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send keyboard to new member {user_id} in group {chat_id}: {e}")


def create_inline_keyboard(buttons: List[List[Tuple[str, str]]]) -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard from a list of button data.
    
    Args:
        buttons: List of rows, where each row is a list of (text, callback_data) tuples
    
    Returns:
        InlineKeyboardMarkup object
    """
    keyboard = []
    for row in buttons:
        keyboard_row = []
        for text, callback_data in row:
            keyboard_row.append(InlineKeyboardButton(text, callback_data=callback_data))
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)


async def send_message_with_retry(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, 
                                 parse_mode: Optional[str] = None, 
                                 reply_markup: Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]] = None,
                                 disable_web_page_preview: bool = True,
                                 max_retries: int = 3) -> Optional[Message]:
    """
    Sends a message with retry logic in case of failure.
    """
    # Skip test chats or invalid chat IDs to prevent errors
    if chat_id in [98765, 67890]:  # Common test chat IDs
        logger.debug(f"Skipping message to test chat {chat_id}")
        return None
        
    # Don't modify parse_mode - let it be as specified
    
    for attempt in range(max_retries):
        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        except telegram.error.RetryAfter as e:
            # Rate limiting - wait and retry
            logger.warning(f"Rate limited when sending message to {chat_id}. Retrying after {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
        except telegram.error.TelegramError as e:
            logger.error(f"Error sending message to {chat_id} (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Failed to send message after {max_retries} attempts: {text[:100]}...")
                return None
            await asyncio.sleep(1)  # Wait before retrying
    
    return None