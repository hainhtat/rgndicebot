import asyncio
import logging
import telegram
from typing import Optional, List, Dict, Any, Tuple, Union
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, TimedOut, NetworkError
from config.settings import USE_DATABASE
from database.adapter import db_adapter

from config.constants import SUPER_ADMIN_IDS, ADMIN_WALLET_AMOUNT, HARDCODED_ADMINS, global_data, get_chat_data_for_id
from config.settings import SUPER_ADMINS
from utils.user_utils import get_user_display_name
from utils.logging_utils import get_logger

logger = get_logger(__name__)



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

        save_data_unified(global_data)

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
        save_data_unified(global_data)  # Save global data after updating chat_data

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




def save_data_unified(global_data: Dict = None) -> None:
    """Unified save function that works with both database and file storage"""
    # Import the proper save function from main
    from main import save_data_unified as main_save_data_unified
    main_save_data_unified(global_data)
        
def load_data_unified() -> Dict:
    """Unified load function that works with both database and file storage"""
    # Import the proper load function from main
    from main import load_data_unified as main_load_data_unified
    return main_load_data_unified()

def create_custom_keyboard():
    """
    Create a custom keyboard for all users (both admins and regular users).
    
    Returns:
        ReplyKeyboardMarkup: The keyboard markup
    """
    # Standard user keyboard for everyone
    keyboard = [
        [KeyboardButton("💰 My Wallet"), KeyboardButton("🙋‍♂️ ကစားနည်း")],
        [KeyboardButton("💵 ငွေထည့်မည်"), KeyboardButton("💸 ငွေထုတ်မည်")],
        [KeyboardButton("🔗 Share")]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Removed create_admin_inline_keyboard function - using unified user keyboard for all users


# Removed send_keyboard_to_user function - keyboards are now sent to group chat only


# Dictionary to store admin IDs by chat ID
ADMIN_IDS_BY_CHAT = {}

async def initialize_group_keyboards(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """
    Initialize keyboards for a group by caching admin information.
    Individual keyboards will be sent privately when users interact.
    """
    try:
        logger.info(f"Initializing keyboard system for group {chat_id}")
        
        # Get admin list for this chat and cache it
        try:
            chat_admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in chat_admins if not admin.user.is_bot]
            
            # Add hardcoded admins
            from config.constants import HARDCODED_ADMINS
            admin_ids.extend(HARDCODED_ADMINS)
            admin_ids = list(set(admin_ids))  # Remove duplicates
            
            ADMIN_IDS_BY_CHAT[chat_id] = admin_ids
            logger.info(f"Cached {len(admin_ids)} admin IDs for chat {chat_id}: {admin_ids}")
            
            # Send simple greeting message to group
            await context.bot.send_message(
                chat_id=chat_id,
                text="🎲 Hello! I'm your Dice Game Bot. Ready to play and win big! 🎉"
            )
            
        except Exception as e:
            logger.error(f"Failed to get chat administrators for {chat_id}: {e}")
            ADMIN_IDS_BY_CHAT[chat_id] = []
            
            # Send greeting message even if admin fetch fails
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🎲 Hello! I'm your Dice Game Bot. Ready to play and win big! 🎉"
                )
            except Exception as msg_error:
                logger.error(f"Failed to send greeting message to {chat_id}: {msg_error}")
                # Don't raise error if message sending fails - just log it
        
        logger.info(f"Greeting sent and admin cache initialized for chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Failed to initialize greeting system for group {chat_id}: {e}")


async def send_appropriate_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send keyboard to user after they interact.
    All users (both admins and regular users) get the same keyboard.
    Sends keyboard only within the group chat, targeted to the specific user.
    """
    try:
        if not update.effective_chat or not update.effective_user:
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Only send keyboards in group chats
        if update.effective_chat.type not in ['group', 'supergroup']:
            return
            
        # Send the same keyboard to all users
        keyboard = create_custom_keyboard()
        
        # Send keyboard to the group chat as a reply to the user's message
        await update.message.reply_text(
            f"🎮 Keyboard for @{update.effective_user.username or update.effective_user.first_name}",
            reply_markup=keyboard
        )
        
        logger.debug(f"Keyboard sent to group {chat_id} for user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send keyboard: {e}")


# Removed send_user_keyboard_on_interaction function - keyboards are now only sent within group chats


# Removed send_keyboard_to_new_member function - keyboards are now only sent within group chats when users interact


async def send_keyboard_to_all_group_members(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_text: str = "🎮 Game controls are now available for everyone!") -> None:
    """
    Send keyboard to all group members by posting a message with keyboard in the group chat.
    This makes the keyboard available to all members in the group.
    """
    try:
        # Only send keyboards in group chats
        chat = await context.bot.get_chat(chat_id)
        if chat.type not in ['group', 'supergroup']:
            logger.debug(f"Skipping keyboard send for non-group chat {chat_id}")
            return
            
        # Create the keyboard
        keyboard = create_custom_keyboard()
        
        # Send keyboard message to the group
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"Keyboard sent to all members in group {chat_id}")
        
    except Exception as e:
        logger.error(f"Failed to send keyboard to all group members in {chat_id}: {e}")


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