import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Dict
from config.settings import USE_DATABASE
from database.adapter import db_adapter

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.constants import get_admin_data, ADMIN_WALLET_AMOUNT, ADMIN_WALLET_REFILL_HOUR, ADMIN_WALLET_REFILL_MINUTE
from config.settings import TIMEZONE

from config.constants import global_data

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def daily_admin_wallet_refill():
    """
    Daily task to refill all admin wallets to the maximum amount.
    Runs every day at 6 AM Myanmar time.
    """
    try:
        logger.info("Starting daily admin wallet refill...")
        
        from config.constants import global_data, SUPER_ADMINS
        from telegram import Bot
        from config.settings import BOT_TOKEN
        
        admin_data = global_data.get("admin_data", {})
        refilled_count = 0
        total_admins = 0
        refill_details = []
        
        # Refill all admin wallets across all groups
        for admin_id_str, admin_info in admin_data.items():
            total_admins += 1
            username = admin_info.get("username") or f"Admin {admin_id_str}"
            chat_points = admin_info.get("chat_points", {})
            
            admin_refills = []
            for chat_id_str, wallet_info in chat_points.items():
                old_amount = wallet_info.get("points", 0)
                # Refill wallet to maximum amount
                wallet_info["points"] = ADMIN_WALLET_AMOUNT
                wallet_info["last_refill"] = datetime.now()
                refilled_count += 1
                
                # Sync with database if enabled
                if USE_DATABASE:
                    try:
                        db_adapter.update_admin_points(int(admin_id_str), int(chat_id_str), ADMIN_WALLET_AMOUNT)
                    except Exception as e:
                        logger.error(f"Failed to sync admin wallet refill to database: {e}")
                
                # Track refill details for notification
                admin_refills.append({
                    "chat_id": chat_id_str,
                    "old_amount": old_amount,
                    "new_amount": ADMIN_WALLET_AMOUNT
                })
            
            if admin_refills:
                refill_details.append({
                    "admin_id": admin_id_str,
                    "username": username,
                    "refills": admin_refills
                })
        
        # Save the updated data
        save_data_unified(global_data)
        
        # Send notification to super admins
        if refill_details:
            await send_refill_notification_to_super_admins(refill_details, refilled_count)
        
        logger.info(f"💰 Daily admin wallet refill completed! Refilled {refilled_count} wallets for {total_admins} admins. Each wallet refilled to {ADMIN_WALLET_AMOUNT:,} points.")
        
    except Exception as e:
        logger.error(f"Error during daily admin wallet refill: {e}")


async def send_refill_notification_to_super_admins(refill_details, total_refills):
    """
    Send notification to super admins about the daily refill.
    Fixed issues: proper backslash formatting, show group names instead of IDs, improved house stats.
    """
    try:
        from config.constants import SUPER_ADMINS
        from telegram import Bot
        from config.settings import BOT_TOKEN
        from utils.formatting import escape_markdown, escape_markdown_username
        from utils.user_utils import get_user_display_name
        from telegram.ext import ContextTypes
        
        bot = Bot(token=BOT_TOKEN)
        
        # Create a context for get_user_display_name
        class MockContext:
            def __init__(self, bot):
                self.bot = bot
        
        context = MockContext(bot)
        
        # Create notification message
        tz = pytz.timezone(TIMEZONE)
        # Calculate yesterday's dates in Myanmar timezone
        now = datetime.now(tz)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = yesterday_end - timedelta(days=1)
        
        # Get house stats with improved error handling
        try:
            from database.queries import get_daily_house_stats
            house_stats = get_daily_house_stats(yesterday_start, yesterday_end)
            
            # Ensure all required keys exist with default values
            house_stats = {
                'total_bets': house_stats.get('total_bets', 0),
                'total_payouts': house_stats.get('total_payouts', 0),
                'house_profit': house_stats.get('house_profit', 0),
                'total_matches': house_stats.get('total_matches', 0),
                'unique_players': house_stats.get('unique_players', 0)
            }
        except Exception as e:
            logger.error(f"Error getting house stats: {e}")
            house_stats = {
                'total_bets': 0,
                'total_payouts': 0,
                'house_profit': 0,
                'total_matches': 0,
                'unique_players': 0
            }
        
        # Format date for display
        yesterday_formatted = yesterday_start.strftime("%Y-%m-%d")
        
        # Build message with proper HTML escaping (no backslashes)
        message = "🔄 <b>Daily Report</b>\n\n"
        message += "<b>📊 House Win/Loss Statistics ({}):</b>\n".format(yesterday_formatted)
        message += "  💰 Total Bets: {:,} ကျပ်\n".format(house_stats['total_bets'])
        message += "  💸 Total Payouts: {:,} ကျပ်\n".format(house_stats['total_payouts'])
        message += "  📈 House Profit: {:,} ကျပ်\n".format(house_stats['house_profit'])
        message += "  🎲 Total Matches: {:,}\n".format(house_stats['total_matches'])
        message += "  👥 Unique Players: {:,}\n\n".format(house_stats['unique_players'])
        
        message += "<b>🔄 Admin Wallet Refills:</b>\n"
        message += "  📦 Total Refills: {:,} wallets\n".format(total_refills)
        message += "  💎 Refill Amount: {:,} points each\n\n".format(ADMIN_WALLET_AMOUNT)
        
        message += "<b>👥 Refilled Admins:</b>\n"
        
        # Group refills by chat to show group names
        chat_refills = {}
        for detail in refill_details:
            for refill in detail["refills"]:
                chat_id = refill["chat_id"]
                if chat_id not in chat_refills:
                    chat_refills[chat_id] = []
                chat_refills[chat_id].append({
                    "admin_id": detail["admin_id"],
                    "username": detail["username"],
                    "old_amount": refill["old_amount"],
                    "new_amount": refill["new_amount"]
                })
        
        # Display refills grouped by chat with group names
        for chat_id, refills in chat_refills.items():
            try:
                # Get group name instead of just showing ID
                chat = await bot.get_chat(int(chat_id))
                group_name = chat.title or f"Group {chat_id}"
                # Escape HTML special characters in group name
                group_name = group_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            except Exception as e:
                logger.error(f"Error getting group name for chat {chat_id}: {e}")
                group_name = f"Group {chat_id}"
            
            message += "\n🏠 <b>{}</b> (ID: {})\n".format(group_name, chat_id)
            
            for refill in refills:
                admin_id = int(refill["admin_id"])
                
                # Get display name with both name and username
                try:
                    display_name = await get_user_display_name(context, admin_id)
                    # Escape HTML special characters in display name
                    display_name = display_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                except Exception as e:
                    logger.error(f"Failed to get display name for admin {admin_id}: {e}")
                    # Fallback to username only with proper escaping
                    username = refill["username"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    display_name = username
                
                old_amount = refill["old_amount"]
                new_amount = refill["new_amount"]
                message += "  👤 {}: {:,} → {:,} points\n".format(display_name, old_amount, new_amount)
        
        # Add footer with timestamp
        current_time = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        message += "\n⏰ <i>Report generated at: {}</i>".format(current_time)
        
        # Send to all super admins
        for super_admin_id in SUPER_ADMINS:
            try:
                await bot.send_message(
                    chat_id=super_admin_id,
                    text=message,
                    parse_mode="HTML"
                )
                logger.info(f"Sent refill notification to super admin {super_admin_id}")
            except Exception as e:
                logger.error(f"Failed to send refill notification to super admin {super_admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error sending refill notifications: {e}")




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

def start_scheduler():
    """
    Start the scheduler for daily tasks.
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler is already running")
        return
    
    try:
        # Create scheduler with Myanmar timezone
        tz = pytz.timezone(TIMEZONE)
        
        # Create scheduler without specifying event loop
        # AsyncIOScheduler will use the current running event loop
        scheduler = AsyncIOScheduler(timezone=tz)
        
        # Add daily admin wallet refill job
        scheduler.add_job(
            daily_admin_wallet_refill,
            CronTrigger(
                hour=ADMIN_WALLET_REFILL_HOUR,
                minute=ADMIN_WALLET_REFILL_MINUTE,
                timezone=tz
            ),
            id='daily_admin_wallet_refill',
            name='Daily Admin Wallet Refill',
            replace_existing=True
        )
        
        # Add auto-roll dice job
        # Note: The auto_roll_dice job is now handled by the main application's job_queue
        # in main.py to ensure proper context is available for sending messages.
        # This scheduler is kept for other potential scheduled tasks.
        logger.info("Auto roll dice job is handled by main application's job_queue")
        
        # Start the scheduler
        scheduler.start()
        
        logger.info(f"Scheduler started. Daily admin wallet refill scheduled for {ADMIN_WALLET_REFILL_HOUR:02d}:{ADMIN_WALLET_REFILL_MINUTE:02d} {TIMEZONE}")
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        scheduler = None


def stop_scheduler():
    """
    Stop the scheduler.
    """
    global scheduler
    
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            scheduler = None
            logger.info("Scheduler stopped")
        except Exception as e:
            # Ignore event loop closed errors during shutdown
            if "Event loop is closed" not in str(e):
                logger.error(f"Error stopping scheduler: {e}")
    else:
        logger.warning("Scheduler is not running")


def get_scheduler_status() -> dict:
    """
    Get the current status of the scheduler.
    """
    global scheduler
    
    if scheduler is None:
        return {
            "running": False,
            "jobs": []
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "running": scheduler.running,
        "jobs": jobs
    }


async def manual_admin_wallet_refill():
    """
    Manual trigger for admin wallet refill (for testing purposes).
    """
    logger.info("Manual admin wallet refill triggered")
    await daily_admin_wallet_refill()