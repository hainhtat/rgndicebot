import logging
import re
import os
import pytz
import asyncio
from datetime import time, datetime, timedelta

import telegram
from telegram import Update, Bot, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, ApplicationBuilder

# Import configuration and logging utilities
from config.config_manager import get_config
from utils.logging_utils import setup_logging, get_logger

# Import from reorganized modules
from config.constants import global_data, ALLOWED_GROUP_IDS
from config.settings import BOT_TOKEN, TIMEZONE, SUPER_ADMINS
from data.file_manager import load_data, save_data

# Import error handler
from utils.error_handler import error_handler, handle_error
from utils.scheduler import start_scheduler, stop_scheduler

# Import handlers from old module for backward compatibility
import handlers

# Import new handlers
from handlers.admin_handlers import adjust_score, check_user_score, refresh_admins, stop_game, admin_wallets, manual_refill, handle_admin_score_adjustment
from handlers.refill_handlers import refill_command, handle_refill_group_selection, handle_refill_action, handle_refill_back_to_groups, handle_refill_amount_command, handle_back_to_groups
from handlers.admin_panel_handlers import admin_panel_handler, handle_admin_panel_callback
from handlers.bet_handlers import place_bet, roll_dice
from handlers import auto_roll_dice_wrapper
from handlers.game_handlers import start_game, new_game_callback, game_status, show_leaderboard, show_history, show_help, bot_info, roll_command
from handlers.user_handlers import start_command, check_wallet, refer_user, get_referral_link, deposit_handler, withdrawal_handler, handle_new_chat_member, handle_share_referral_callback
from handlers.superadmin_handlers import my_groups_command, handle_mygroups_callback
from utils.daily_bonus import process_daily_cashback

# Initialize configuration
config = get_config()

# Configure logging
log_config = config.get_section("logging")
setup_logging(
    log_level=log_config.get("level", "INFO"),
    log_file=log_config.get("file"),
    json_format=log_config.get("json_format", False)
)

# Get logger for this module
logger = get_logger(__name__)

# auto_roll_dice_wrapper is imported from handlers package

# Import the dynamic keyboard function
from utils.telegram_utils import create_custom_keyboard, is_admin, initialize_group_keyboards, send_user_keyboard_on_interaction, send_keyboard_to_new_member



# Function to initialize keyboards for all users in allowed groups
async def initialize_keyboards(application):
    """
    Send keyboards to all users in allowed groups when bot starts
    """
    logger.info("Initializing keyboards for all users in allowed groups...")
    
    for chat_id in ALLOWED_GROUP_IDS:
        try:
            # Get all members of the group
            chat_members = await application.bot.get_chat_administrators(chat_id)
            
            # Send keyboards to administrators
            for member in chat_members:
                if not member.user.is_bot:
                    # Keyboard sending removed as requested
                    pass
                    
            logger.info(f"Initialized keyboards for administrators in group {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize keyboards for group {chat_id}: {e}")

# Handler for unhandled text messages
async def unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Logs unhandled text messages and provides appropriate responses.
    """
    if update.effective_chat.type == "private":
        # Just log the message without sending any response
        logger.info(f"Unhandled private message from {update.effective_user.id}: {update.message.text}")
    else:
        # For group chats, send user keyboard to regular users on first interaction
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if this is an allowed group
        if chat_id in ALLOWED_GROUP_IDS:
            # Just log the interaction without sending any keyboard
            # The keyboard functionality is already available through other handlers
            pass
        
        logger.info(f"Unhandled group message from {update.effective_user.id} in chat {update.effective_chat.id}: {update.message.text}")


async def initialize_bot_keyboards(application: Application) -> None:
    """
    Initialize keyboards for all allowed groups when the bot starts.
    This ensures admins get their keyboards immediately upon bot startup.
    """
    try:
        # Create a mock context with the bot instance
        class MockContext:
            def __init__(self, bot):
                self.bot = bot
        
        context = MockContext(application.bot)
        
        for chat_id in ALLOWED_GROUP_IDS:
            try:
                await initialize_group_keyboards(context, chat_id)
                logger.info(f"Initialized keyboards for group {chat_id}")
            except Exception as e:
                logger.error(f"Failed to initialize keyboards for group {chat_id}: {e}")
        
        logger.info("Bot keyboard initialization completed for all groups")
    except Exception as e:
        logger.error(f"Error during bot keyboard initialization: {e}")


# Function to add scheduled jobs
async def add_scheduled_jobs(application: Application) -> None:
    """
    Add scheduled jobs to the application's job queue.
    This function is called after the Application is fully initialized.
    """
    # Schedule jobs here if needed
    logger.info("Scheduled jobs initialized.")

    # Define async wrapper for save_data
    async def save_data_async(context):
        save_data(global_data)
        
    # Get configuration values for scheduling
    save_interval = config.get("data", "save_interval_minutes", 5)
    # We use a small interval for the auto_roll_dice scheduler to check game states frequently
    # The actual timing for betting and rolling is controlled within the auto_roll_dice function
    check_interval = 5  # Check game states every 5 seconds
    
    # Log the scheduling settings
    logger.info(f"Scheduling settings: save_interval={save_interval}m, check_interval={check_interval}s")
    
    # Schedule periodic data saving
    application.job_queue.run_repeating(
        save_data_async,
        interval=timedelta(minutes=save_interval),
        first=datetime.now(pytz.utc) + timedelta(seconds=10),
        name="periodic_data_save"
    )
    logger.info(f"Scheduled periodic data saving job (every {save_interval} minutes).")
    
    # Schedule automatic dice rolling
    application.job_queue.run_repeating(
        auto_roll_dice_wrapper,
        interval=timedelta(seconds=check_interval),
        first=datetime.now(pytz.utc) + timedelta(seconds=15),
        name="auto_roll_dice"
    )
    logger.info(f"Scheduled automatic dice rolling job (checking game states every {check_interval} seconds).")
    
    # Schedule daily cashback processing (once per day at 00:05 AM)
    daily_time = time(hour=0, minute=5, tzinfo=pytz.timezone(TIMEZONE))
    application.job_queue.run_daily(
        process_daily_cashback,
        time=daily_time,
        name="daily_cashback"
    )
    logger.info(f"Scheduled daily cashback processing job (every day at {daily_time.strftime('%H:%M')} {TIMEZONE}).")


def main() -> None:
    """
    Main function to set up and run the Telegram bot.
    """
    logger.info("Starting bot setup...")

    # Load data from the JSON file at startup
    load_data(global_data)
    logger.info("Global data loaded from file.")

    # Create the application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Set up error handler
    application.add_error_handler(handle_error)
    logger.info("Error handler registered.")

    # Add handlers
    
    # Command Handlers
    
    # Essential Command Handlers
    # Keep only essential commands
    application.add_handler(CommandHandler("start", start_command))
    
    # Admin commands (keep for direct access)
    application.add_handler(CommandHandler("adjustscore", adjust_score))
    application.add_handler(CommandHandler("checkscore", check_user_score))
    application.add_handler(CommandHandler("mygroups", my_groups_command))
    application.add_handler(CommandHandler("refreshadmins", refresh_admins))
    application.add_handler(CommandHandler("adminwallets", admin_wallets))
    application.add_handler(CommandHandler("refill", refill_command))
    application.add_handler(CommandHandler("refill_amount", handle_refill_amount_command))
    application.add_handler(CommandHandler("manualrefill", manual_refill))  # Keep old refill as manual refill
    
    # Refill callback handlers
    application.add_handler(CallbackQueryHandler(handle_refill_group_selection, pattern='^refill_group_'))
    application.add_handler(CallbackQueryHandler(handle_refill_action, pattern='^refill_(all|admin|custom)_'))
    application.add_handler(CallbackQueryHandler(handle_back_to_groups, pattern='^refill_back_to_groups$'))
    
    # Admin panel callback handlers
    application.add_handler(CallbackQueryHandler(handle_admin_panel_callback, pattern='^admin_panel_'))
    
    # Superadmin callback handlers
    application.add_handler(CallbackQueryHandler(handle_mygroups_callback, pattern='^mygroups_'))
    application.add_handler(CallbackQueryHandler(handle_mygroups_callback, pattern='^admin_wallets_'))
    
    # Callback query handlers
    
    # Callback query handlers - New modules
    application.add_handler(CallbackQueryHandler(new_game_callback, pattern='^new_game$'))
    application.add_handler(CallbackQueryHandler(place_bet, pattern='^bet_'))
    application.add_handler(CallbackQueryHandler(roll_dice, pattern='^roll_dice$'))
    
    # Share referral callback handler
    application.add_handler(CallbackQueryHandler(handle_share_referral_callback, pattern='^share_referral_'))

    # Message Handlers for text-based betting (e.g., 'b 500', 'big 100')
    # Improved bet pattern to handle more formats like "b1000", "small 5000", "L200"
    bet_pattern = re.compile(r"^(big|b|small|s|lucky|l)\s*(\d+)$|^(b|s|l)(\d+)$", re.IGNORECASE)
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(bet_pattern), place_bet))

    # Message Handlers for the Custom Reply Keyboard Buttons
    # User buttons
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 My Wallet$"), check_wallet))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏆 Leaderboard$"), show_leaderboard))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💵 ငွေထည့်မည်$"), deposit_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💸 ငွေထုတ်မည်$"), withdrawal_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔗 Share$"), get_referral_link))
    
    # Keep admin command handlers for slash commands
    # These commands will be accessible via slash commands only, not keyboard buttons
    application.add_handler(CommandHandler("roll", roll_command))
    application.add_handler(CommandHandler("stopgame", stop_game))
    application.add_handler(CommandHandler("history", show_history))
    
    # Add missing command handlers
    application.add_handler(CommandHandler("wallet", check_wallet))
    application.add_handler(CommandHandler("refer", get_referral_link))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("about", bot_info))
    application.add_handler(CommandHandler("status", game_status))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    
    # Add handlers for emoji versions of keyboard buttons
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💵 ငွေထည့်မည်$"), deposit_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💸 ငွေထုတ်မည်$"), withdrawal_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 My Wallet$"), check_wallet))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏆 Leaderboard$"), show_leaderboard))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔗 Share$"), get_referral_link))
    
    # Also add handlers without emojis for backward compatibility
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ငွေထည့်မည်$"), deposit_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^ငွေထုတ်မည်$"), withdrawal_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^My Wallet$"), check_wallet))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Leaderboard$"), show_leaderboard))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Share$"), get_referral_link))

    # Handler for admin score adjustments with +number or -number
    adjustment_pattern = re.compile(r'^([+\-]\d+)$')
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(adjustment_pattern) & filters.REPLY, handle_admin_score_adjustment))
    
    # Fallback handler for any other text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unhandled_message))

    # ChatMemberHandler to detect when the bot joins/leaves a chat
    # Add handler for new chat members (for referral processing)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_member))
    
    # Add post-init callback to initialize keyboards, start scheduler, and add scheduled jobs
    async def post_init_callback(app):
        await initialize_bot_keyboards(app)
        start_scheduler()
        await add_scheduled_jobs(app)
    
    application.post_init = post_init_callback
    
    # Start the bot
    logger.info("Dice Game Bot started polling...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        # Stop the scheduler when bot shuts down
        stop_scheduler()

    # Save data on graceful shutdown
    logger.info("Bot is shutting down. Attempting to save data to JSON file.")
    save_data(global_data)

if __name__ == "__main__":
    # Call main function
    main()
