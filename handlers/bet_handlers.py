import re
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext

# Import configuration and logging utilities
from config.config_manager import get_config
from utils.logging_utils import get_logger
from utils.error_handler import error_handler, BotError, GameStateError, InvalidBetError
from utils.telegram_utils import get_admins_from_chat, is_admin

# Import constants
from config.constants import (
    global_data, get_chat_data_for_id,
    GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER,
    BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY
)

# Import from utils
from utils.user_utils import get_user_display_name
from utils.telegram_utils import send_message_with_retry
from utils.message_formatter import (
    format_bet_confirmation, format_insufficient_funds, format_bet_error,
    format_game_result, format_game_summary, format_dice_result,
    format_participants_list, format_betting_closed_message, format_dice_animation_failed,
    format_game_status, MessageTemplates, get_parse_mode_for_message
)

# Import from game logic
from game.game_logic import DiceGame, place_bet as process_bet, roll_dice as game_roll_dice, close_betting, payout

# Import data management
from data.file_manager import save_data

# Import from handlers utils
from handlers.utils import check_allowed_chat, get_current_game, create_new_game

# Get logger for this module
logger = get_logger(__name__)

# Get configuration
config = get_config()

@error_handler
async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle both callback queries for betting and text-based betting."""
    # Check if this is a callback query or a text message
    is_callback = update.callback_query is not None
    
    # Get chat and user information
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    
    # Check if this chat is allowed to use the bot
    if not await check_allowed_chat(update, context):
        return
    
    # Check if user is an admin - admins cannot participate in games
    if await is_admin(chat_id, user_id, context):
        error_message = "❌ Admins cannot participate in games."
        if is_callback:
            await update.callback_query.answer(error_message)
        else:
            await update.message.reply_text(error_message)
        return
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    
    # Get the current game or create a new one if needed
    game = get_current_game(chat_id)
    if not game or game.state == GAME_STATE_OVER:
        game = create_new_game(chat_id)
    
    # Parse the bet information
    bet_type = None
    amount = None
    
    if is_callback:
        # This is a callback query for betting
        callback_data = update.callback_query.data
        
        # Check if this is an info button
        if callback_data.startswith("info_"):
            # Handle info button click
            info_type = callback_data.split("_")[1]
            await update.callback_query.answer(f"Info about {info_type} betting")
            return
        
        # Parse bet type and amount from callback data
        match = re.match(r"bet_(big|small|lucky)_(\d+)", callback_data)
        if match:
            bet_type = match.group(1).upper()
            amount = int(match.group(2))
        else:
            await update.callback_query.answer("Invalid bet format")
            return
    else:
        # This is a text message for betting
        message_text = update.message.text.strip().lower()
        
        # Parse bet type and amount from text
        # Format can be: "b 500", "big 100", "s 200", "small 300", "l 700", "lucky 400"
        # Or without space: "b500", "s200", "l700"
        
        # First try the format with space
        match = re.match(r"^(b|big|s|small|l|lucky)\s+(\d+)$", message_text)
        if not match:
            # Try the format without space
            match = re.match(r"^(b|s|l)(\d+)$", message_text)
        
        if match:
            bet_code = match.group(1).lower()
            if bet_code in ["b", "big"]:
                bet_type = BET_TYPE_BIG
            elif bet_code in ["s", "small"]:
                bet_type = BET_TYPE_SMALL
            elif bet_code in ["l", "lucky"]:
                bet_type = BET_TYPE_LUCKY
            
            # Get the amount from the second group
            amount = int(match.group(2))
        else:
            # Invalid format
            return
    
    # Get referral points from global data for both scenarios
    global_user_data = global_data.get("global_user_data", {}).get(str(user_id), {})
    referral_points = global_user_data.get("referral_points", 0)
    
    # Process the bet
    try:
        result_message = process_bet(game, user_id, username, bet_type, amount, chat_data, global_data)
        
        # Send confirmation message
        confirmation_message = format_bet_confirmation(
            bet_type=bet_type,
            amount=amount,
            result_message=result_message,
            username=username,
            referral_points=referral_points,
            user_id=str(user_id),
            game=game,
            global_data=global_data
        )
        
        # Always use HTML parse mode since format_bet_confirmation now returns HTML
        if is_callback:
            await update.callback_query.answer("လောင်းကြေးထပ်လိုက်ပါပြီ!")
            await update.callback_query.edit_message_text(
                text=confirmation_message,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text=confirmation_message,
                parse_mode="HTML"
            )
        
        logger.info(f"Bet placed: user={user_id}, type={bet_type}, amount={amount}, chat={chat_id}")
        
    except (GameStateError, InvalidBetError) as e:
        error_message = str(e)
        
        if is_callback:
            await update.callback_query.answer(error_message)
        else:
            await update.message.reply_text(
                text=format_bet_error(error_message),
                parse_mode="Markdown"
            )
        
        logger.warning(f"Bet error: user={user_id}, type={bet_type}, amount={amount}, error={error_message}")

@error_handler
async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle manual dice rolling by admins."""
    # Check if this is a callback query
    if not update.callback_query:
        return
    
    # Get chat and user information
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if this chat is allowed to use the bot
    if not await check_allowed_chat(update, context):
        return
    
    # Get chat data
    chat_data = get_chat_data_for_id(chat_id)
    
    # Get the current game
    game = get_current_game(chat_id)
    if not game:
        await update.callback_query.answer("No active game found")
        return
    
    # Check if the game is in the correct state
    if game.state != GAME_STATE_CLOSED:
        # Close betting first
        close_betting(game)
    
    # Process payouts
    try:
        # Send dice animation and capture actual values
        dice_msg1 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
        dice_msg2 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
        
        # Get the actual dice values from Telegram's animation
        dice1 = dice_msg1.dice.value
        dice2 = dice_msg2.dice.value
        dice_sum = dice1 + dice2
        
        # Update the game result with actual dice values
        game.result = (dice1, dice2)
        
        result = payout(game, chat_data, global_data)
        
        # Send result message
        await update.callback_query.edit_message_text(
            text=format_dice_result(dice1, dice2, dice_sum),
            parse_mode="Markdown"
        )
        
        # Send game summary
        await send_message_with_retry(
            context,
            chat_id,
            format_game_summary(result, global_data),
            parse_mode="Markdown"
        )
        
        # Create a new game
        new_game = create_new_game(chat_id)
        
        # Send new game status message with proper time remaining
        await send_message_with_retry(
            context,
            chat_id,
            format_game_status(new_game.get_status(), 60),
            parse_mode="Markdown"
        )
        
        logger.info(f"Dice rolled manually: chat={chat_id}, user={user_id}, result={dice1},{dice2}")
        
    except Exception as e:
        logger.error(f"Error in manual dice roll for chat {chat_id}: {e}")
        try:
            # Fallback: use manual dice roll if animation fails
            dice1, dice2 = game_roll_dice(game)
            result = payout(game, chat_data, global_data)
            
            # Send fallback result message
            await update.callback_query.edit_message_text(
                text=f"⚠️ *Dice animation failed, using manual roll*\n\n{format_dice_result(dice1, dice2, dice1 + dice2)}",
                parse_mode="Markdown"
            )
            
            # Send game summary
            await send_message_with_retry(
                context,
                chat_id,
                format_game_summary(result, global_data),
                parse_mode="Markdown"
            )
            
            # Create a new game
            new_game = create_new_game(chat_id)
            
            # Send new game status message
            await send_message_with_retry(
                context,
                chat_id,
                format_game_status(new_game.get_status(), 60),
                parse_mode="Markdown"
            )
            
        except Exception as fallback_error:
            await update.callback_query.answer(f"Critical error: {str(fallback_error)}")
            logger.error(f"Critical error in manual roll fallback: {fallback_error}", exc_info=True)

@error_handler
async def auto_roll_dice(update, context) -> None:
    """Automatically manage the dice game flow:
    1. Wait for 1 minute for bets
    2. Close betting with a message listing participants
    3. Wait 5 seconds
    4. Roll dice and announce results
    5. Create a new game
    6. Repeat until stopped or no bets for 3 consecutive matches
    """
    # Context is passed from the job queue
    # Get the configuration values
    bet_time = config.get("game", "bet_time_seconds", 60)  # 1 minute for betting
    roll_delay = config.get("game", "roll_delay_seconds", 5)  # Delay after closing bets before rolling
    idle_game_limit = config.get("game", "idle_game_limit", 3)  # Stop after 3 consecutive games with no bets
    manual_stop_cooldown = config.get("game", "manual_stop_cooldown_seconds", 10)
    
    # Log the current settings
    logger.info(f"Game flow settings: bet_time={bet_time}s, roll_delay={roll_delay}s, idle_limit={idle_game_limit}, manual_stop_cooldown={manual_stop_cooldown}s")
    
    # Get current time
    now = datetime.now()
    
    # Debug: Log all chats
    logger.info(f"Processing {len(global_data['all_chat_data'])} chats: {list(global_data['all_chat_data'].keys())}")
    
    # Iterate through all chats with active games
    for chat_id_str, chat_data in global_data["all_chat_data"].items():
        try:
            chat_id = int(chat_id_str)
            
            # Skip test chats or invalid chat IDs
            if chat_id == 98765 or chat_id == 67890:  # Common test chat IDs
                logger.debug(f"Skipping test chat {chat_id}")
                continue
            
            # Check if this chat has a manual stop cooldown in effect
            manual_stop_time = chat_data.get("manual_stop_cooldown")
            if manual_stop_time:
                # Calculate how long ago the game was manually stopped
                cooldown_elapsed = (now - manual_stop_time).total_seconds()
                
                # Use the configured cooldown period after manual stop
                cooldown_period = manual_stop_cooldown  # seconds
                
                if cooldown_elapsed < cooldown_period:
                    # Skip this chat during cooldown period
                    logger.info(f"Skipping chat {chat_id} due to manual stop cooldown ({cooldown_elapsed:.1f}s elapsed, {cooldown_period-cooldown_elapsed:.1f}s remaining)")
                    continue
                else:
                    # Cooldown period has passed, clear the flag
                    chat_data.pop("manual_stop_cooldown", None)
                    logger.info(f"Manual stop cooldown expired for chat {chat_id}")
            
            # Get the current game
            game = get_current_game(chat_id)
            logger.info(f"Chat {chat_id}: get_current_game returned: {game}")
            if not game:
                # If there's no current game and we're not in a cooldown period,
                # we can create a new game if needed
                # This is handled elsewhere (e.g., by user commands or other functions)
                logger.info(f"Chat {chat_id}: No current game found, continuing to next chat")
                continue
            
            # Check if the game has been waiting for bets for too long
            if game.state == GAME_STATE_WAITING:
                time_elapsed = (now - game.created_at).total_seconds()
                logger.info(f"Chat {chat_id}: Game state={game.state}, created_at={game.created_at}, now={now}, elapsed={time_elapsed:.1f}s, bet_time={bet_time}s")
                
                if time_elapsed >= bet_time:
                    # Close betting
                    close_betting(game)
                    logger.info(f"Auto-closed betting for game in chat {chat_id} after {time_elapsed:.1f} seconds")
                    
                    # Check if there are any bets immediately after closing
                    total_bets = sum(sum(bets.values()) for bets in game.bets.values())
                    consecutive_idle = chat_data.get("consecutive_idle_matches", 0)
                    
                    # If no bets and we've reached the idle limit, stop the game immediately
                    if total_bets == 0 and consecutive_idle >= idle_game_limit:
                        logger.info(f"Stopping game in chat {chat_id} after {consecutive_idle} consecutive idle games")
                        
                        # Remove the current game to stop the auto-roll cycle
                        if chat_id_str in global_data["all_chat_data"]:
                            global_data["all_chat_data"][chat_id_str].pop("current_game", None)
                            save_data(global_data)
                        
                        # Send stop message with admin list
                        if context and hasattr(context, 'bot'):
                            # Get admin list for this chat
                            admin_list = await get_admins_from_chat(chat_id, context)
                            admin_usernames = []
                            for admin_id in admin_list:
                                try:
                                    chat_member = await context.bot.get_chat_member(chat_id, admin_id)
                                    username = chat_member.user.username
                                    if username:
                                        admin_usernames.append(f"@{username}")
                                except Exception:
                                    pass
                            
                            # If no admin usernames found, use fallback
                            if not admin_usernames:
                                admin_usernames = ["@admin"]
                            
                            # Escape admin usernames for Markdown
                            escaped_admin_usernames = [username.replace("_", "\\_") for username in admin_usernames]
                            admin_list_text = "\n".join(escaped_admin_usernames)
                            stop_message = MessageTemplates.GAME_STOPPED_INACTIVITY.format(
                                admin_list=admin_list_text
                            )
                            
                            logger.info(f"Sending stop message to chat {chat_id}: {stop_message[:100]}...")
                            result = await send_message_with_retry(
                                context,
                                chat_id,
                                stop_message,
                                parse_mode="Markdown"
                            )
                            if result is not None:
                                logger.info(f"Stop message sent successfully to chat {chat_id}")
                            else:
                                logger.error(f"Failed to send stop message to chat {chat_id}")
                        
                        continue
                    
                    # Create participants message using template
                    participants_msg = format_participants_list(game, chat_data, global_data)
                    
                    # Send message that betting is closed with participants list
                    if context and hasattr(context, 'bot'):
                        await send_message_with_retry(
                            context,
                            chat_id,
                            format_betting_closed_message(participants_msg, roll_delay),
                            parse_mode="Markdown"
                        )
            
            # Check if the game has been closed
            if game.state == GAME_STATE_CLOSED:
                time_elapsed = (now - game.closed_at).total_seconds() if hasattr(game, 'closed_at') else 0
                
                if time_elapsed >= roll_delay:  # Wait 5 seconds after closing bets before rolling
                    # Check if there are any bets
                    total_bets = sum(sum(bets.values()) for bets in game.bets.values())
                    
                    # Check if we should skip this game due to consecutive idle games
                    consecutive_idle = chat_data.get("consecutive_idle_matches", 0)
                    
                    if total_bets == 0 and consecutive_idle >= idle_game_limit:
                        # Stop the game entirely after consecutive idle games
                        logger.info(f"Stopping game in chat {chat_id} after {consecutive_idle} consecutive idle games")
                        
                        # Remove the current game to stop the auto-roll cycle
                        if chat_id_str in global_data["all_chat_data"]:
                            global_data["all_chat_data"][chat_id_str].pop("current_game", None)
                            save_data(global_data)
                        
                        # Send stop message
                        if context and hasattr(context, 'bot'):
                            await send_message_with_retry(
                                context,
                                chat_id,
                                "🛑 *Game stopped due to inactivity*\n\nNo bets were placed for 3 consecutive matches.\nUse /roll to start a new game.",
                                parse_mode="Markdown"
                            )
                        
                        continue
                    
                    # Send dice animation and capture actual values
                    if context and hasattr(context, 'bot'):
                        try:
                            # Send two dice and capture their values
                            dice_msg1 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
                            dice_msg2 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
                            
                            # Get the actual dice values from Telegram's animation
                            dice1 = dice_msg1.dice.value
                            dice2 = dice_msg2.dice.value
                            
                            # Update the game result with actual dice values
                            game.result = (dice1, dice2)
                            
                            # Process payouts with actual dice values
                            result = payout(game, chat_data, global_data)
                            
                            # Send game summary (contains dice result and payout info)
                            await send_message_with_retry(
                                context,
                                chat_id,
                                format_game_summary(result, global_data),
                                parse_mode="Markdown"
                            )
                            
                            logger.info(f"Game result sent successfully for match {game.match_id} in chat {chat_id}")
                            
                        except Exception as e:
                            logger.error(f"Error in dice roll and result for chat {chat_id}: {e}")
                            # Fallback: use manual dice roll if animation fails
                            dice1, dice2 = game_roll_dice(game)
                            result = payout(game, chat_data, global_data)
                            
                            # Send fallback result message
                            await send_message_with_retry(
                                context,
                                chat_id,
                                format_dice_animation_failed(format_game_summary(result, global_data)),
                                parse_mode="Markdown"
                            )
                    
                    # Check if we should create a new game or stop due to consecutive idle games
                    consecutive_idle_after_payout = chat_data.get("consecutive_idle_matches", 0)
                    if total_bets == 0 and consecutive_idle_after_payout >= idle_game_limit:
                        # Don't create a new game, stop the cycle
                        logger.info(f"Not creating new game in chat {chat_id} after {consecutive_idle_after_payout} consecutive idle games")
                        
                        # Remove the current game to stop the auto-roll cycle
                        if chat_id_str in global_data["all_chat_data"]:
                            global_data["all_chat_data"][chat_id_str].pop("current_game", None)
                            save_data(global_data)
                        
                        # Send stop message BEFORE any new game would be created
                        if context and hasattr(context, 'bot'):
                            # Get admin list for this chat
                            admin_list = await get_admins_from_chat(chat_id, context)
                            admin_usernames = []
                            for admin_id in admin_list:
                                try:
                                    chat_member = await context.bot.get_chat_member(chat_id, admin_id)
                                    username = chat_member.user.username
                                    if username:
                                        admin_usernames.append(f"@{username}")
                                except Exception:
                                    pass
                            
                            # If no admin usernames found, use fallback
                            if not admin_usernames:
                                admin_usernames = ["@admin"]
                            
                            # Escape admin usernames for Markdown
                            escaped_admin_usernames = [username.replace("_", "\\_") for username in admin_usernames]
                            admin_list_text = "\n".join(escaped_admin_usernames)
                            stop_message = MessageTemplates.GAME_STOPPED_INACTIVITY.format(
                                admin_list=admin_list_text
                            )
                            
                            logger.info(f"Sending stop message to chat {chat_id}: {stop_message[:100]}...")
                            result = await send_message_with_retry(
                                context,
                                chat_id,
                                stop_message,
                                parse_mode="Markdown"
                            )
                            if result is not None:
                                logger.info(f"Stop message sent successfully to chat {chat_id}")
                            else:
                                logger.error(f"Failed to send stop message to chat {chat_id}")
                    else:
                        # Create a new game (we've already checked for manual stop cooldown at the beginning of the function)
                        new_game = create_new_game(chat_id)
                        
                        # Send new game status message with proper time remaining
                        if context and hasattr(context, 'bot'):
                            await send_message_with_retry(
                                context,
                                chat_id,
                                format_game_status(new_game.get_status(), 60),
                                parse_mode="Markdown"
                            )
                    
                    # Log successful game processing
                    logger.info(f"Game processing completed for chat {chat_id}")
        
        except Exception as e:
            logger.error(f"Error in auto_roll_dice for chat {chat_id_str}: {str(e)}", exc_info=True)