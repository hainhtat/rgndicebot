import logging
import asyncio
from datetime import datetime, time
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.constants import get_admin_data, ADMIN_WALLET_AMOUNT, ADMIN_WALLET_REFILL_HOUR, ADMIN_WALLET_REFILL_MINUTE
from config.settings import TIMEZONE
from data.file_manager import save_data
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
        save_data(global_data)
        
        # Send notification to super admins
        if refill_details:
            await send_refill_notification_to_super_admins(refill_details, refilled_count)
        
        logger.info(f"💰 Daily admin wallet refill completed! Refilled {refilled_count} wallets for {total_admins} admins. Each wallet refilled to {ADMIN_WALLET_AMOUNT:,} points.")
        
    except Exception as e:
        logger.error(f"Error during daily admin wallet refill: {e}")


async def send_refill_notification_to_super_admins(refill_details, total_refills):
    """
    Send notification to super admins about the daily refill.
    """
    try:
        from config.constants import SUPER_ADMINS
        from telegram import Bot
        from config.settings import BOT_TOKEN
        from utils.formatting import escape_markdown, escape_markdown_username
        
        bot = Bot(token=BOT_TOKEN)
        
        # Create notification message
        message = f"🔄 *Daily Admin Wallet Refill Report*\n\n"
        message += f"*Total Refills:* {total_refills} wallets\n"
        message += f"*Refill Amount:* {ADMIN_WALLET_AMOUNT:,} points each\n\n"
        message += f"*Refilled Admins:*\n"
        
        for detail in refill_details:
            username = escape_markdown_username(detail["username"])
            admin_id = detail["admin_id"]
            message += f"\n👤 *{username}* ({admin_id})\n"
            
            for refill in detail["refills"]:
                chat_id = refill["chat_id"]
                old_amount = refill["old_amount"]
                new_amount = refill["new_amount"]
                message += f"  📊 Chat {chat_id}: {old_amount:,} → {new_amount:,} points\n"
        
        # Send to all super admins
        for super_admin_id in SUPER_ADMINS:
            try:
                await bot.send_message(
                    chat_id=super_admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent refill notification to super admin {super_admin_id}")
            except Exception as e:
                logger.error(f"Failed to send refill notification to super admin {super_admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error sending refill notifications: {e}")


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