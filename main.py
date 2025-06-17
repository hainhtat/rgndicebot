import logging
import re
import os
import pytz  # For timezone handling
from datetime import time, datetime, timedelta  # Import datetime for comparison and timedelta for periodic job
from dotenv import load_dotenv # Import load_dotenv

# --- MODIFIED: Import telegram and telegram.ext as whole modules to avoid circular import issues ---
import telegram
import telegram.ext
# --- END MODIFIED ---

# --- MODIFIED: Import the entire handlers module ---
import handlers
# --- END MODIFIED ---

# Import global_data from constants
from constants import global_data, ALLOWED_GROUP_IDS

# NEW: Import file management functions
from file_manager import load_data, save_data

# Configure logging for the bot.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Changed to INFO for production, use DEBUG for more detail
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Define the custom reply keyboard
# --- UPDATED: Removed "Score" button, "My Wallet" is now the combined command ---
custom_keyboard = [
    [telegram.KeyboardButton("ငွေထည့်မည်"), telegram.KeyboardButton("ငွေထုတ်မည်")],
    [telegram.KeyboardButton("My Wallet"), telegram.KeyboardButton("Leaderboard"), telegram.KeyboardButton("ကစားနည်း"), telegram.KeyboardButton("Share")]
]
custom_keyboard_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)

# Handler for unhandled text messages...
async def unhandled_message(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """
    Logs unhandled text messages but does not reply, to keep the chat clean.
    """
    if update.effective_chat.type == "private":
        # For private chats, provide a friendly message if the command is not understood
        # --- UPDATED: Wrap entire message in * for bolding ---
        await update.message.reply_text(
            f"*ဘယ်လို အကူအညီလိုလဲ မသိဘူးရှင့်။ အောက်က ခလုတ်တွေ ဒါမှမဟုတ် /start ကို နှိပ်ပြီး စတင်နိုင်ပါတယ်နော်။*",
            reply_markup=custom_keyboard_markup,
            parse_mode="Markdown"
        )
        logger.info(f"Unhandled private message from {update.effective_user.id}: {update.message.text}")
    else:
        # For group chats, just log and ignore to avoid spam
        logger.info(f"Unhandled group message from {update.effective_user.id} in chat {update.effective_chat.id}: {update.message.text}")


# --- NEW: Function to add scheduled jobs ---
# This function will now be called via post_init, ensuring the application is fully initialized.
async def add_scheduled_jobs(application: telegram.ext.Application): # Explicitly type hint for clarity
    """
    Adds all recurring scheduled jobs to the application's job queue.
    This function is called after the Application is fully initialized.
    """
    # --- UPDATED: Changed time to 23:30 UTC for 6:00 AM MMT refill ---
    # Schedule daily admin point refill at 23:30 UTC, which is 6:00 AM in Myanmar (UTC+6:30)
    application.job_queue.run_daily(
        handlers.refill_all_admin_points,
        time=time(hour=23, minute=30, tzinfo=pytz.utc),
        name="daily_admin_refill"
    )
    logger.info("Scheduled daily admin point refill job for 06:00 MMT (23:30 UTC).")
    # --- END UPDATED ---

    # --- NEW: Call force_admin_refill_on_startup immediately after data load ---
    # This ensures admins are refilled if the bot starts up and they haven't been refilled today
    # and handles the persistence issue if 'last_refill' was 'null'
    # MODIFIED: Pass 'application' directly as context. At this point (post_init), application.bot will be initialized.
    await handlers.force_admin_refill_on_startup(application)
    logger.info("Completed force_admin_refill_on_startup check.")
    # --- END NEW ---

    # NEW: Schedule periodic refresh of all group admin lists
    application.job_queue.run_repeating(
        handlers.refresh_all_group_admins, # New handler function in handlers.py
        interval=timedelta(hours=6), # Refresh every 6 hours (adjust as needed)
        first=datetime.now(pytz.utc) + timedelta(minutes=1), # Start 1 minute after bot startup
        name="periodic_admin_refresh"
    )
    logger.info("Scheduled periodic group admin refresh job.")

    # --- NEW: Schedule periodic data saving ---
    application.job_queue.run_repeating(
        lambda context: save_data(global_data), # Use a lambda to pass global_data
        interval=timedelta(minutes=5), # Save every 5 minutes (adjust as needed)
        first=datetime.now(pytz.utc) + timedelta(seconds=10), # Start 10 seconds after bot startup
        name="periodic_data_save"
    )
    logger.info("Scheduled periodic data saving job (every 5 minutes).")
    # --- END NEW ---


# MODIFIED: Changed main back to a synchronous function
def main():
    """
    Main function to set up and run the Telegram bot.
    """
    logger.info("Starting bot setup...")

    # Load data from the JSON file at startup
    load_data(global_data)
    logger.info("Global data loaded from file.")

    # --- MODIFIED: Corrected how BOT_TOKEN is retrieved and referencing ApplicationBuilder ---
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    # BOT_TOKEN = "8187381656:AAHnNiWB0Z98uJ5qBvbaXCsNqHHOt1itlGg" # Use os.getenv with the correct variable name
   
    if not BOT_TOKEN:
        logger.error("Telegram Bot Token not found in environment variables. Please set BOT_TOKEN in your .env file.")
        return

    # MODIFIED: Register add_scheduled_jobs as a post_init callback
    # ApplicationBuilder().build() starts the internal loop and calls post_init
    application = telegram.ext.ApplicationBuilder().token(BOT_TOKEN).post_init(add_scheduled_jobs).build()
    # --- END MODIFIED ---

    # No need for application.create_task(add_scheduled_jobs(application)) here anymore
    # as it's now handled by post_init callback.


    # Command Handlers
    application.add_handler(telegram.ext.CommandHandler("start", handlers.start))
    # application.add_handler(telegram.ext.CommandHandler("ping", handlers.ping))
    application.add_handler(telegram.ext.CommandHandler("roll", handlers.start_dice))
    application.add_handler(telegram.ext.CommandHandler("mywallet", handlers.my_wallet))
    application.add_handler(telegram.ext.CommandHandler("leaderboard", handlers.leaderboard))
    application.add_handler(telegram.ext.CommandHandler("history", handlers.history))
    application.add_handler(telegram.ext.CommandHandler("adjustscore", handlers.adjust_score))
    application.add_handler(telegram.ext.CommandHandler("checkscore", handlers.check_user_score))
    application.add_handler(telegram.ext.CommandHandler("refreshadmins", handlers.refresh_admins))
    application.add_handler(telegram.ext.CommandHandler("stopgame", handlers.stop_game))
    application.add_handler(telegram.ext.CommandHandler("adminwallets", handlers.admin_wallets))
    application.add_handler(telegram.ext.CommandHandler("refill", handlers.manual_refill))
    application.add_handler(telegram.ext.CommandHandler("share", handlers.handle_share_referral))
     # Admin wallet check

    # CallbackQueryHandler for inline buttons
    application.add_handler(telegram.ext.CallbackQueryHandler(handlers.button_callback))

    # Message Handlers for text-based betting (e.g., 'b 500', 'big 100')
    # This regex ensures we only catch messages that look like bet commands.
    # MODIFIED: Changed telegram.re.IGNORECASE to re.IGNORECASE
    bet_pattern = re.compile(r"^(big|b|small|s|lucky|l)\s*(\d+)$", re.IGNORECASE)
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex(bet_pattern), handlers.handle_bet))

    # Message Handlers for the Custom Reply Keyboard Buttons
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^ငွေထည့်မည်$"), handlers.deposit_points))
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^ငွေထုတ်မည်$"), handlers.withdraw_points))
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^My Wallet$"), handlers.my_wallet))
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^Leaderboard$"), handlers.leaderboard))
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^ကစားနည်း$"), handlers.start))
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & telegram.ext.filters.Regex("^Share$"), handlers.handle_share_referral)) # Handler for 'Share' reply keyboard button

    # Fallback handler for any other text messages
    application.add_handler(telegram.ext.MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, unhandled_message))

    # ChatMemberHandler to detect when the bot joins/leaves a chat
    application.add_handler(telegram.ext.ChatMemberHandler(handlers.on_chat_member_update, telegram.ext.ChatMemberHandler.CHAT_MEMBER))

    logger.info("Dice Game Bot started polling...")
    # MODIFIED: Call run_polling directly, as main is now synchronous
    application.run_polling(allowed_updates=telegram.Update.ALL_TYPES)

    # --- NEW: Save data on graceful shutdown (optional but good practice) ---
    logger.info("Bot is shutting down. Attempting to save data to JSON file.")
    save_data(global_data)
    # --- END NEW --

if __name__ == "__main__":
    # MODIFIED: Call main directly, as it's now synchronous
    main()
