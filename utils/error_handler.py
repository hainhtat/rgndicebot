import logging
import traceback
from functools import wraps
from typing import Callable, Any, Dict, Optional, Type, Union, List

import telegram
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TimedOut, NetworkError, ChatMigrated, TelegramError

from utils.message_formatter import MessageTemplates

logger = logging.getLogger(__name__)

# Define error types and their user-friendly messages
ERROR_MESSAGES = {
    Forbidden: "Bot token is invalid or I was blocked by the user.",
    BadRequest: "Invalid request parameters.",
    TimedOut: "Request timed out. Please try again later.",
    NetworkError: "Network error occurred. Please try again later.",
    ChatMigrated: "The chat has been migrated to a supergroup.",
    TelegramError: "An error occurred with Telegram. Please try again later.",
    ValueError: "Invalid value provided.",
    KeyError: "Required data not found.",
    TypeError: "Invalid data type.",
    Exception: "An unexpected error occurred. Please try again later."
}


class BotError(Exception):
    """Base class for bot-specific errors"""
    def __init__(self, message: str, user_message: Optional[str] = None):
        self.message = message  # Technical message for logs
        self.user_message = user_message or message  # User-friendly message
        super().__init__(self.message)


class InvalidBetError(BotError):
    """Error for invalid bets"""
    pass


class InsufficientFundsError(BotError):
    """Error for insufficient funds"""
    pass


class GameStateError(BotError):
    """Error for invalid game state transitions"""
    pass


class PermissionError(BotError):
    """Error for permission issues"""
    pass


class DataError(BotError):
    """Error for data-related issues"""
    pass


async def handle_error(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot
    
    This function handles all errors that occur during command execution.
    It logs the error and sends an appropriate message to the user.
    """
    # Get the exception info
    error = context.error
    
    # Log the error with traceback
    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = ''.join(tb_list)
    
    # Log with appropriate level based on error type
    if isinstance(error, (telegram.error.BadRequest, ValueError, KeyError, TypeError)):
        logger.warning(f"Update {context.update} caused error: {error}\n{tb_string}")
    else:
        logger.error(f"Update {context.update} caused error: {error}\n{tb_string}")
    
    # Get user-friendly error message
    user_message = "❌ An error occurred."
    
    # Check for custom bot errors first
    if isinstance(error, BotError):
        user_message = f"❌ {error.user_message}"
    else:
        # Find the most specific error type that matches
        for error_type, message in ERROR_MESSAGES.items():
            if isinstance(error, error_type):
                user_message = f"❌ {message}"
                break
    
    # Send error message to user if possible
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=user_message
            )
        except telegram.error.TelegramError as send_error:
            logger.error(f"Failed to send error message: {send_error}")


def error_handler(func: Callable) -> Callable:
    """Decorator for handling errors in handler functions
    
    This decorator catches exceptions, logs them, and returns an appropriate
    error message to the user.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            # Log the error
            tb_list = traceback.format_exception(None, e, e.__traceback__)
            tb_string = ''.join(tb_list)
            
            if isinstance(e, BotError):
                logger.warning(f"Handler error in {func.__name__}: {e.message}\n{tb_string}")
                user_message = f"❌ {e.user_message}"
            else:
                logger.error(f"Unhandled error in {func.__name__}: {e}\n{tb_string}")
                
                # Find appropriate error message
                user_message = "❌ An error occurred."
                for error_type, message in ERROR_MESSAGES.items():
                    if isinstance(e, error_type):
                        user_message = f"❌ {message}"
                        break
            
            # Send error message to user
            if update.effective_chat:
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=user_message
                    )
                except telegram.error.TelegramError as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
            
            # Re-raise for global handler
            raise
    
    return wrapper


def validate_game_state(required_states: List[str]):
    """Decorator to validate game state before executing a handler
    
    Args:
        required_states: List of valid game states for this handler
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
            from handlers.utils import get_current_game
            
            chat_id = update.effective_chat.id
            current_game = get_current_game(chat_id)
            
            if not current_game:
                await update.effective_message.reply_text(MessageTemplates.NO_ACTIVE_GAME)
                return None
            
            if current_game.state not in required_states:
                await update.effective_message.reply_text(
                    f"❌ Cannot perform this action in the current game state: {current_game.state}"
                )
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    
    return decorator


def validate_admin(func: Callable) -> Callable:
    """Decorator to validate that the user is an admin before executing a handler"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        from handlers.utils import check_admin_permission
        
        if not await check_admin_permission(update, context):
            return None
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def validate_allowed_chat(func: Callable) -> Callable:
    """Decorator to validate that the chat is allowed to use the bot"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        from handlers.utils import check_allowed_chat
        
        if not await check_allowed_chat(update, context):
            return None
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper