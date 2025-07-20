import logging
import re
import os
import pytz
import asyncio
from datetime import time, datetime, timedelta
from typing import Dict
from config.settings import USE_DATABASE
from database.adapter import db_adapter

import telegram
from telegram import Update, Bot, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, ApplicationBuilder

# Import configuration and logging utilities
from config.config_manager import get_config
from utils.logging_utils import setup_logging, get_logger

# Import from reorganized modules
from config.constants import global_data, ALLOWED_GROUP_IDS
from config.settings import BOT_TOKEN, TIMEZONE, SUPER_ADMINS


# Import error handler
from utils.error_handler import error_handler, handle_error
from utils.scheduler import start_scheduler, stop_scheduler

# Import handlers from old module for backward compatibility
import handlers

# Import new handlers
from handlers.admin_handlers import adjust_score, check_user_score, refresh_admins, stop_game, admin_wallets, manual_refill, handle_admin_score_adjustment, housestats_command
from handlers.refill_handlers import refill_command, handle_refill_group_selection, handle_refill_action, handle_refill_back_to_groups, handle_refill_amount_command, handle_back_to_groups, handle_housestats_callback
# Removed admin panel handlers - using unified keyboard system
from handlers.bet_handlers import place_bet, roll_dice
from handlers import auto_roll_dice_wrapper
from handlers.game_handlers import start_game, new_game_callback, game_status, show_leaderboard, show_history, show_help, bot_info, roll_command
from handlers.user_handlers import start_command, check_wallet, refer_user, get_referral_link, deposit_handler, withdrawal_handler, handle_new_chat_member, handle_share_referral_callback
from handlers.superadmin_handlers import my_groups_command, handle_mygroups_callback
from utils.daily_bonus import process_daily_cashback

# Initialize configuration
config = get_config()

# Configure logging with rotation
log_config = config.get_section("logging")
setup_logging(
    log_level=log_config.get("level", "INFO"),
    log_file=log_config.get("file"),
    json_format=log_config.get("json_format", False),
    max_file_size_mb=log_config.get("max_file_size_mb", 10),
    backup_count=log_config.get("backup_count", 5)
)

# Get logger for this module
logger = get_logger(__name__)

# auto_roll_dice_wrapper is imported from handlers package

# Import the dynamic keyboard function
from utils.telegram_utils import create_custom_keyboard, is_admin



# Function to initialize keyboard system for allowed groups
async def initialize_keyboards(application):
    """
    Initialize keyboard system for allowed groups when bot starts.
    Keyboards are now sent on-demand when users interact.
    """
    logger.info("Initializing keyboard system for allowed groups...")
    
    # Removed keyboard initialization - using unified system without admin-specific keyboards
    logger.info("Bot startup complete - unified keyboard system active")


async def send_startup_greeting(application):
    """
    Send a greeting message with reply keyboard to all allowed groups when the bot restarts.
    """
    logger.info("Sending startup greeting with reply keyboard")
    
    greeting_message = "🎲 <b>Bot Restarted Successfully!</b>\n\n" \
                      "I'm back online and ready to serve! 🎉\n" \
                      "All systems are operational. Let's play and win big! 💰"
    
    reply_markup = create_custom_keyboard()
    
    for chat_id in ALLOWED_GROUP_IDS:
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=greeting_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            logger.info(f"Sent startup greeting with keyboard to chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send startup greeting to chat {chat_id}: {e}")
    
    logger.info("Startup greeting process completed")

# Handler for unhandled text messages
async def unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Logs unhandled text messages and provides appropriate responses.
    """
    # Get the message text from either message or edited_message
    message_text = None
    if update.message:
        message_text = update.message.text
    elif update.edited_message:
        message_text = update.edited_message.text
    
    # Skip if no text content (e.g., media messages)
    if not message_text:
        return
    
    if update.effective_chat.type == "private":
        # Just log the message without sending any response
        logger.info(f"Unhandled private message from {update.effective_user.id}: {message_text}")
    else:
        # For group chats, send user keyboard to regular users on first interaction
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if this is an allowed group
        if chat_id in ALLOWED_GROUP_IDS:
            # Just log the interaction without sending any keyboard
            # The keyboard functionality is already available through other handlers
            pass
        
        logger.info(f"Unhandled group message from {update.effective_user.id} in chat {update.effective_chat.id}: {message_text}")


async def initialize_bot_keyboards(application: Application) -> None:
    """
    Removed keyboard initialization - using unified system.
    """
    logger.info("Unified keyboard system - no initialization needed")


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
        save_data_unified(global_data)
        
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
    
    # Schedule log cleanup (once per day at 02:00 AM)
    async def cleanup_logs_async(context):
        """Async wrapper for log cleanup."""
        try:
            retention_days = log_config.get("database_log_retention_days", 30)
            success = db_adapter.cleanup_old_logs(days_to_keep=retention_days)
            if success:
                logger.info(f"Log cleanup completed successfully (keeping {retention_days} days)")
            else:
                logger.warning("Log cleanup failed")
        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")
    
    cleanup_time = time(hour=2, minute=0, tzinfo=pytz.timezone(TIMEZONE))
    application.job_queue.run_daily(
        cleanup_logs_async,
        time=cleanup_time,
        name="log_cleanup"
    )
    logger.info(f"Scheduled daily log cleanup job (every day at {cleanup_time.strftime('%H:%M')} {TIMEZONE}).")




def save_data_unified(global_data: Dict = None) -> None:
    """Unified data saving function that uses database when enabled."""
    if USE_DATABASE:
        # Database handles saving automatically - no action needed
        logger.debug("Data saving skipped - using database mode")
    else:
        logger.error("Database mode is disabled but no alternative storage configured")

def load_data_unified() -> Dict:
    """Unified data loading function that uses database when enabled."""
    from config.constants import global_data
    
    if USE_DATABASE:
        # Load data from database into global_data structure
        try:
            from database.adapter import db_adapter
            from config.settings import ALLOWED_GROUP_IDS
            
            logger.info("Loading data from database...")
            
            # Load chat data for all allowed groups
            for chat_id in ALLOWED_GROUP_IDS:
                try:
                    chat_id_str = str(chat_id)
                    
                    # Initialize chat data structure
                    if chat_id_str not in global_data["all_chat_data"]:
                        global_data["all_chat_data"][chat_id_str] = {
                            "player_stats": {},
                            "match_counter": 1,
                            "match_history": [],
                            "group_admins": [],
                            "consecutive_idle_matches": 0,
                        }
                    
                    # Load match counter
                    match_counter = db_adapter.get_chat_match_counter(chat_id)
                    global_data["all_chat_data"][chat_id_str]["match_counter"] = match_counter
                    
                    # Load recent matches for history
                    recent_matches = db_adapter.get_recent_matches(chat_id, 50)
                    global_data["all_chat_data"][chat_id_str]["match_history"] = recent_matches
                    
                    # Load leaderboard to get player stats
                    leaderboard = db_adapter.get_chat_leaderboard(chat_id, 1000)  # Get all players
                    for player in leaderboard:
                        user_id_str = str(player["user_id"])
                        global_data["all_chat_data"][chat_id_str]["player_stats"][user_id_str] = {
                            "username": player["username"],
                            "score": player["score"],
                            "total_wins": player["total_wins"],
                            "total_losses": player["total_losses"],
                            "total_bets": player["total_bets"],
                            "last_active": player["last_active"]
                        }
                except Exception as e:
                    logger.error(f"Error loading data for chat {chat_id}: {e}")
                    # Fallback to default empty structures
                    chat_id_str = str(chat_id)
                    if chat_id_str not in global_data["all_chat_data"]:
                        global_data["all_chat_data"][chat_id_str] = {
                            "player_stats": {},
                            "match_counter": 1,
                            "match_history": [],
                            "group_admins": [],
                            "consecutive_idle_matches": 0,
                        }
            
            # Load global user data from database
            logger.info("Loading global user data from database...")
            all_users = db_adapter.db_queries.get_all_users()
            for user_data in all_users:
                user_id_str = str(user_data['user_id'])
                global_data["global_user_data"][user_id_str] = {
                    "full_name": user_data.get('full_name', 'Unknown'),
                    "username": user_data.get('username'),
                    "referral_points": user_data.get('referral_points', 0),
                    "bonus_points": user_data.get('bonus_points', 0),
                    "referred_by": user_data.get('referred_by'),
                    "welcome_bonus_received": user_data.get('welcome_bonus_received', {}),
                    "last_cashback_date": user_data.get('last_cashback_date')
                }
            
            # Load admin data from database
            logger.info("Loading admin data from database...")
            admin_data_list = db_adapter.db_queries.get_all_admin_data()
            for admin_data in admin_data_list:
                user_id_str = str(admin_data['user_id'])
                chat_id_str = str(admin_data['chat_id'])
                
                # Initialize admin data structure if not exists
                if user_id_str not in global_data["admin_data"]:
                    global_data["admin_data"][user_id_str] = {
                        "username": admin_data.get('username', f"Admin {admin_data['user_id']}"),
                        "chat_points": {}
                    }
                
                # Set chat points for this admin
                global_data["admin_data"][user_id_str]["chat_points"][chat_id_str] = {
                    "points": admin_data['points'],
                    "last_refill": admin_data.get('last_refill')
                }
            
            logger.info(f"Loaded data for {len(ALLOWED_GROUP_IDS)} groups, {len(all_users)} users, and {len(admin_data_list)} admin wallets from database")
            
        except Exception as e:
            logger.error(f"Error loading data from database: {e}")
    
    return global_data

def main() -> None:
    """
    Main function to set up and run the Telegram bot.
    """
    logger.info("Starting bot setup...")

    # Initialize database if using database mode
    if USE_DATABASE:
        from database.connection import init_database
        if init_database():
            logger.info("Database initialized successfully.")
            
            # Database initialization completed successfully
            logger.info("Database is ready for use.")
        else:
            logger.error("Failed to initialize database. Exiting.")
            return
    
    # Load data from the JSON file at startup
    load_data_unified()
    logger.info("Global data loaded from file.")

    # Create the application with performance optimizations
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)  # Enable concurrent update processing
        .pool_timeout(30)  # Increase pool timeout
        .connection_pool_size(20)  # Increase connection pool size
        .read_timeout(30)  # Increase read timeout
        .write_timeout(30)  # Increase write timeout
        .connect_timeout(30)  # Increase connect timeout
        .build()
    )

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
    application.add_handler(CommandHandler("housestats", housestats_command))
    
    # Refill callback handlers
    application.add_handler(CallbackQueryHandler(handle_refill_group_selection, pattern='^refill_group_'))
    application.add_handler(CallbackQueryHandler(handle_refill_action, pattern='^refill_(all|admin|custom)_'))
    application.add_handler(CallbackQueryHandler(handle_back_to_groups, pattern='^refill_back_to_groups$'))
    application.add_handler(CallbackQueryHandler(handle_housestats_callback, pattern='^housestats_'))
    
    # Removed admin panel callback handlers - using unified keyboard system
    
    # Superadmin callback handlers
    application.add_handler(CallbackQueryHandler(handle_mygroups_callback, pattern='^mygroups_'))
    application.add_handler(CallbackQueryHandler(handle_mygroups_callback, pattern='^admin_wallets_'))
    
    # Using unified keyboard system - all users get the same reply keyboard buttons
    
    # Callback query handlers
    
    # Callback query handlers - New modules
    application.add_handler(CallbackQueryHandler(new_game_callback, pattern='^new_game$'))
    application.add_handler(CallbackQueryHandler(place_bet, pattern='^bet_'))
    application.add_handler(CallbackQueryHandler(roll_dice, pattern='^roll_dice$'))
    
    # Share referral callback handler
    application.add_handler(CallbackQueryHandler(handle_share_referral_callback, pattern='^share_referral_'))

    # Import the multiple betting handler
    from handlers.bet_handlers import place_multiple_bets
    
    # Message Handlers for multiple betting patterns
    # Handle multiple bets in one message: "b100 l200 s300", "100b 200l 300s", etc.
    multiple_bet_pattern = re.compile(r".*(?:(?:b|big|s|small|l|lucky)\s*\d+|\d+\s*(?:b|big|s|small|l|lucky)).*(?:(?:b|big|s|small|l|lucky)\s*\d+|\d+\s*(?:b|big|s|small|l|lucky)).*", re.IGNORECASE)
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(multiple_bet_pattern), place_multiple_bets))
    
    # Message Handlers for single text-based betting (e.g., 'b 500', 'big 100', '500b', '100big')
    # Enhanced patterns to handle more formats
    single_bet_patterns = [
        re.compile(r"^(big|b|small|s|lucky|l)\s*(\d+)$", re.IGNORECASE),  # b100, big 100
        re.compile(r"^(b|s|l)(\d+)$", re.IGNORECASE),  # b100, s200, l300
        re.compile(r"^(\d+)\s*(big|b|small|s|lucky|l)$", re.IGNORECASE),  # 100b, 200 big
        re.compile(r"^(\d+)(b|s|l)$", re.IGNORECASE),  # 100b, 200s, 300l
    ]
    
    # Add handlers for each single bet pattern
    for pattern in single_bet_patterns:
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex(pattern), place_bet))

    # Removed keyboard wrapper functions - using unified keyboard system without repeated keyboard sending

    # Message Handlers for the Custom Reply Keyboard Buttons
    # All users get the same keyboard buttons
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 My Wallet$"), check_wallet))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🙋‍♂️ ကစားနည်း$"), show_help))
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
    
    # Add post-init callback to initialize keyboards, start scheduler, add scheduled jobs, and send greeting
    async def post_init_callback(app):
        await initialize_bot_keyboards(app)
        start_scheduler()
        await add_scheduled_jobs(app)
        await send_startup_greeting(app)
    
    application.post_init = post_init_callback
    
    # Start the bot with performance optimizations
    logger.info("Dice Game Bot started polling...")
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Drop pending updates on startup
            poll_interval=1.0,  # Reduce polling interval for better responsiveness
            timeout=30,  # Increase timeout
            bootstrap_retries=5  # Add retry mechanism
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}")
        # Log the error but don't attempt recursive restart
        logger.error("Bot will exit. Please restart manually if needed.")
    finally:
        # Stop the scheduler when bot shuts down
        try:
            stop_scheduler()
        except Exception as e:
            # Ignore event loop closed errors during shutdown
            if "Event loop is closed" not in str(e) and "no running event loop" not in str(e):
                logger.error(f"Error stopping scheduler: {e}")
        
        # Save data on graceful shutdown
        try:
            logger.info("Bot is shutting down. Attempting to save data.")
            save_data_unified(global_data)
        except Exception as e:
            # Ignore event loop closed errors during shutdown
            if "Event loop is closed" not in str(e) and "no running event loop" not in str(e):
                logger.error(f"Error saving data on shutdown: {e}")

if __name__ == "__main__":
    # Call main function
    main()
