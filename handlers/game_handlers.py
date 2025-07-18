import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from config.settings import USE_DATABASE
from database.adapter import db_adapter

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.constants import global_data, get_chat_data_for_id

from game.game_logic import DiceGame
from handlers.utils import (
    check_allowed_chat, 
    get_current_game, 
    create_new_game,
    create_game_status_message,
    create_betting_keyboard,
    save_data_unified
)
from utils.message_formatter import format_leaderboard, format_game_history, MessageTemplates

logger = logging.getLogger(__name__)


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start a new dice game in the chat.
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    current_game = get_current_game(chat_id)
    
    if current_game:
        from utils.message_formatter import MessageTemplates
        await update.message.reply_text(MessageTemplates.GAME_ALREADY_IN_PROGRESS, parse_mode="HTML")
        return
    
    # Check if there's a manual stop cooldown in effect
    from datetime import datetime
    manual_stop_time = chat_data.get("manual_stop_cooldown")
    if manual_stop_time:
        # Get the cooldown period from config
        from config.config_manager import get_config
        config = get_config()
        cooldown_period = config.get("game", "manual_stop_cooldown_seconds", 10)
        
        # Calculate how long ago the game was manually stopped
        now = datetime.now()
        cooldown_elapsed = (now - manual_stop_time).total_seconds()
        
        if cooldown_elapsed < cooldown_period:
            # Still in cooldown period
            remaining = int(cooldown_period - cooldown_elapsed)
            await update.message.reply_text(
                f"⏱ Please wait {remaining} seconds before starting a new game after stopping one."
            )
            return
        else:
            # Cooldown period has passed, clear the flag
            chat_data.pop("manual_stop_cooldown", None)
    
    # Create a new game
    create_new_game(chat_id)
    
    # Save data after creating the game
    from main import save_data_unified
    save_data_unified(global_data)
    
    # Get the current game
    current_game = get_current_game(chat_id)
    
    # Create the game status message with enhanced formatting
    status_message = await create_game_status_message(current_game, context)
    
    # Create the betting keyboard (now returns None as per requirements)
    reply_markup = create_betting_keyboard()
    
    # Send the game status message
    await update.message.reply_text(
        status_message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def roll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start a new dice game in the chat.
    Usage: /roll
    The game will automatically roll dice after 1 minute of betting time,
    then start a new game, and continue until stopped or no bets for 3 consecutive matches.
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    from utils.telegram_utils import is_admin
    
    # Check if user is an admin
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text(MessageTemplates.ONLY_ADMINS_CAN_USE, parse_mode="HTML")
        return
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    
    # Check if there's a manual stop cooldown in effect
    from datetime import datetime
    manual_stop_time = chat_data.get("manual_stop_cooldown")
    if manual_stop_time:
        # Get the cooldown period from config
        from config.config_manager import get_config
        config = get_config()
        cooldown_period = config.get("game", "manual_stop_cooldown_seconds", 10)
        
        # Calculate how long ago the game was manually stopped
        now = datetime.now()
        cooldown_elapsed = (now - manual_stop_time).total_seconds()
        
        if cooldown_elapsed < cooldown_period:
            # Still in cooldown period
            remaining = int(cooldown_period - cooldown_elapsed)
            await update.message.reply_text(
                f"⏱ Please wait {remaining} seconds before starting a new game after stopping one."
            )
            return
        else:
            # Cooldown period has passed, clear the flag
            chat_data.pop("manual_stop_cooldown", None)
    
    # Check if games are in inactive state and activate them
    game_state = chat_data.get("game_state", "active")
    if game_state == "inactive":
        chat_data["game_state"] = "active"
        await update.message.reply_text(
            "✅ <b>Games activated!</b>\n\nStarting a new dice game...",
            parse_mode="HTML"
        )
    
    # Get chat data
    current_game = get_current_game(chat_id)
    
    if current_game:
        await update.message.reply_text(
            "❌ A game is already in progress. Please finish the current game first."
        )
        return
    
    # Start a new game
    await update.message.reply_text(MessageTemplates.STARTING_NEW_GAME, parse_mode="HTML")
    
    # Reset consecutive idle matches when manually starting a new game
    chat_data["consecutive_idle_matches"] = 0
    
    # Create a new game
    current_game = create_new_game(chat_id)
    
    # Save data after creating the game
    save_data_unified(global_data)
    
    # Check if current_game is not None before proceeding
    if current_game is None:
        await update.message.reply_text(
            "❌ Error: Failed to create a new game. Please try again."
        )
        return
        
    # Create the game status message
    status_message = await create_game_status_message(current_game, context)
    
    # Create the betting keyboard
    reply_markup = create_betting_keyboard()
    
    # Send the game status message
    await update.message.reply_text(
        status_message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    # Keyboard sending removed as requested
    
    # The auto_roll_dice function will handle the rest of the game flow:
    # 1. Wait for 1 minute for bets
    # 2. Close betting
    # 3. Roll dice after 5 seconds
    # 4. Create a new game
    # 5. Repeat until stopped or no bets for 3 consecutive matches


async def new_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback for the new game button.
    Creates a new game and updates the message with the game status.
    """
    query = update.callback_query
    chat_id = update.effective_chat.id
    
    logger.info(f"New game callback triggered in chat {chat_id}")
    
    # Check if the chat is allowed to use the bot
    if not await check_allowed_chat(update, context):
        logger.warning(f"Chat {chat_id} is not allowed to use the bot")
        try:
            await query.answer(MessageTemplates.CHAT_NOT_AUTHORIZED)
        except Exception as e:
            logger.error(f"Failed to answer query: {str(e)}")
        return
    
    try:
        # Get the chat data
        chat_data = get_chat_data_for_id(chat_id)
        logger.info(f"Retrieved chat data for chat {chat_id}")
        
        # Check if there's already a game in progress
        current_game = get_current_game(chat_id)
        if current_game:
            logger.warning(f"Game creation failed: A game is already in progress in chat {chat_id}")
            try:
                await query.answer(MessageTemplates.GAME_ALREADY_IN_PROGRESS_CALLBACK)
            except Exception as e:
                logger.error(f"Failed to answer query: {str(e)}")
            return
        
        # Check if there's a manual stop cooldown in effect
        from datetime import datetime
        manual_stop_time = chat_data.get("manual_stop_cooldown")
        if manual_stop_time:
            # Get the cooldown period from config
            from config.config_manager import get_config
            config = get_config()
            cooldown_period = config.get("game", "manual_stop_cooldown_seconds", 10)
            
            # Calculate how long ago the game was manually stopped
            now = datetime.now()
            cooldown_elapsed = (now - manual_stop_time).total_seconds()
            
            if cooldown_elapsed < cooldown_period:
                # Still in cooldown period
                remaining = int(cooldown_period - cooldown_elapsed)
                try:
                    await query.edit_message_text(
                        f"⏱ Please wait {remaining} seconds before starting a new game after stopping one."
                    )
                    return
                except Exception as e:
                    logger.error(f"Failed to edit message for cooldown: {str(e)}")
                    return
            else:
                # Cooldown period has passed, clear the flag
                chat_data.pop("manual_stop_cooldown", None)
        
        # Create a new game
        logger.info(f"Creating new game for chat {chat_id}")
        game = create_new_game(chat_id)
        logger.info(f"New game created with ID {game.match_id}")
        
        # Save the data
        save_data_unified(global_data)
        logger.info(f"Data saved after creating new game for chat {chat_id}")
        
        # Get the current game
        current_game = get_current_game(chat_id)
        if not current_game:
            logger.error(f"Failed to retrieve current game for chat {chat_id} after creation")
            try:
                await query.answer(MessageTemplates.FAILED_CREATE_GAME)
            except Exception as e:
                logger.error(f"Failed to answer query: {str(e)}")
            return
        
        logger.info(f"Retrieved current game with ID {current_game.match_id} for chat {chat_id}")
        
        # Create the status message and keyboard
        try:
            status_message = await create_game_status_message(current_game, context)
            logger.info(f"Created status message for game {current_game.match_id}")
        except Exception as e:
            logger.error(f"Error creating status message: {str(e)}")
            try:
                await query.answer(MessageTemplates.FAILED_CREATE_STATUS_MESSAGE)
            except Exception as e2:
                logger.error(f"Failed to answer query: {str(e2)}")
            return
        
        keyboard = create_betting_keyboard()
        logger.info(f"Created betting keyboard for game {current_game.match_id}")
        
        # Edit the message with the new status and keyboard
        try:
            logger.info(f"Attempting to edit message with new game status for chat {chat_id}")
            await query.edit_message_text(
                text=status_message,
                reply_markup=keyboard,
                parse_mode=None  # Use no parse mode to avoid formatting issues
            )
            logger.info(f"Successfully edited message with new game status for chat {chat_id}")
            try:
                await query.answer(MessageTemplates.NEW_GAME_CREATED)
            except Exception as e:
                logger.error(f"Failed to answer query after successful edit: {str(e)}")
        except Exception as e:
            logger.error(f"Error editing message with new game status: {str(e)}")
            try:
                await query.answer(MessageTemplates.FAILED_UPDATE_GAME_STATUS)
            except Exception as e2:
                logger.error(f"Failed to answer query after edit error: {str(e2)}")
    except Exception as e:
        logger.error(f"Unexpected error in new_game_callback: {str(e)}")
        try:
            await query.answer(MessageTemplates.UNEXPECTED_ERROR)
        except Exception as e2:
            logger.error(f"Failed to answer query after unexpected error: {str(e2)}")


async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the current game status.
    Usage: /status
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    current_game = get_current_game(chat_id)
    
    if not current_game:
        # No game in progress, show a button to start a new game
        keyboard = [
            [InlineKeyboardButton("🎮 New Game", callback_data="new_game")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ No game is currently in progress.\n"
            "Click the button below to start a new game.",
            reply_markup=reply_markup
        )
        return
    
    # Create the game status message
    status_message = await create_game_status_message(current_game, context)
    
    # Create the betting keyboard
    reply_markup = create_betting_keyboard()
    
    # Send the game status message
    await update.message.reply_text(
        status_message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the leaderboard for the current chat.
    Usage: /leaderboard
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    
    # Format the leaderboard
    leaderboard_message = await format_leaderboard(chat_data, context, "🏆 Leaderboard", global_data)
    
    # Send the leaderboard message
    await update.message.reply_text(
        leaderboard_message,
        parse_mode="HTML"
    )


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the game history for the current chat.
    Usage: /history
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    
    # Format the game history
    history_message = format_game_history(chat_data["match_history"])
    
    # Send the history message
    await update.message.reply_text(
        history_message,
        parse_mode="HTML"
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show help information about how to use the bot.
    Usage: /help
    """
    help_message = MessageTemplates.HELP_MESSAGE
    
    try:
        await update.message.reply_text(
            help_message,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error sending help message: {e}")
        # Try without HTML parsing
        await update.message.reply_text(
            help_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''),
            parse_mode=None
        )


async def bot_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show information about the bot.
    Usage: /about
    """
    about_message = (
        "🎲 <b>RGN Dice Bot</b> 🎲\n\n"
        "A fun dice betting game for Telegram groups!\n\n"
        "<b>Features:</b>\n"
        "• Real-time dice rolling\n"
        "• Betting system with ကျပ်\n"
        "• Leaderboards and statistics\n"
        "• Referral system\n\n"
        "<b>Version:</b> 3.3\n"
        "<b>Created by:</b> RGN Team\n"
    )
    
    await update.message.reply_text(
        about_message,
        parse_mode="HTML"
    )