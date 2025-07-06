import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from config.settings import USE_DATABASE
from database.adapter import db_adapter

from config.constants import global_data
from config.settings import DAILY_CASHBACK_PERCENTAGE

from handlers.utils import save_data_unified

logger = logging.getLogger(__name__)

async def process_daily_cashback(context):
    """
    Process daily cashback for all users based on their daily losses.
    This function is scheduled to run once per day.
    """
    logger.info("🎁 Starting daily cashback processing for all users...")
    
    # Get current date (without time) for tracking
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Initialize daily loss tracking if not exists
    if "daily_losses" not in global_data:
        global_data["daily_losses"] = {}
    
    # Process each chat
    for chat_id_str, chat_data in global_data["all_chat_data"].items():
        if "match_history" not in chat_data:
            continue
            
        # Get yesterday's matches
        yesterday_matches = []
        for match in chat_data["match_history"]:
            match_date = match["timestamp"].date() if isinstance(match["timestamp"], datetime) else datetime.fromisoformat(match["timestamp"]).date()
            if match_date == yesterday:
                yesterday_matches.append(match)
        
        if not yesterday_matches:
            continue
            
        # Calculate daily losses per user
        user_daily_losses = {}
        
        # Process each match from yesterday
        for match in yesterday_matches:
            # Process losers
            if "losers" in match and isinstance(match["losers"], list):
                for loser in match["losers"]:
                    user_id = loser.get("user_id")
                    bet_amount = loser.get("bet_amount", 0)
                    
                    if user_id:
                        if user_id not in user_daily_losses:
                            user_daily_losses[user_id] = 0
                        user_daily_losses[user_id] += bet_amount
        
        # Award cashback to users with losses
        for user_id, total_loss in user_daily_losses.items():
            if total_loss > 0:
                # Calculate cashback (5% of total loss)
                cashback = int(total_loss * DAILY_CASHBACK_PERCENTAGE)
                
                if cashback > 0:
                    # Update user's bonus points instead of main score
                    if user_id in chat_data["player_stats"]:
                        # Initialize global user data if not exists
                        if "global_user_data" not in global_data:
                            global_data["global_user_data"] = {}
                        if user_id not in global_data["global_user_data"]:
                            global_data["global_user_data"][user_id] = {
                                "referral_points": 0,
                                "bonus_points": 0,
                                "last_cashback_date": None
                            }
                        
                        # Check if user already received cashback today
                        last_cashback_date = global_data["global_user_data"][user_id].get("last_cashback_date")
                        if last_cashback_date == str(today):
                            logger.info(f"User {user_id} already received cashback today ({today}), skipping")
                            continue
                        
                        # Add cashback to bonus points
                        global_data["global_user_data"][user_id]["bonus_points"] += cashback
                        global_data["global_user_data"][user_id]["last_cashback_date"] = str(today)
                        
                        # Sync with database if enabled
                        if USE_DATABASE:
                            try:
                                # Update user's bonus points in database (using referral system for now)
                                # Note: This could be enhanced with a dedicated bonus points table
                                pass  # Bonus points are stored in global_data for now
                            except Exception as e:
                                logger.error(f"Failed to sync bonus points to database: {e}")
                        
                        # Record the cashback in daily_losses
                        if user_id not in global_data["daily_losses"]:
                            global_data["daily_losses"][user_id] = {}
                        
                        # Store the cashback info
                        global_data["daily_losses"][user_id][str(yesterday)] = {
                            "total_loss": total_loss,
                            "cashback": cashback,
                            "processed_at": datetime.now().isoformat()
                        }
                        
                        logger.info(f"💰 Awarded {cashback} ကျပ် cashback to user {user_id} for {total_loss} ကျပ် loss in chat {chat_id_str}")
                        
                        # Try to notify the user about their cashback with an engaging message
                        try:
                            cashback_message = (
                                f"🎁 *Daily Cashback Reward!* 🎁\n\n"
                                f"🌟 Great news! You've received your daily cashback bonus!\n\n"
                                f"💰 *Cashback Amount:* {cashback:,} ကျပ်\n"
                                f"📊 *Yesterday's Activity:* {total_loss:,} ကျပ်\n"
                                f"🎯 *Cashback Rate:* {int(DAILY_CASHBACK_PERCENTAGE * 100)}%\n\n"
                                f"🚀 Your ကျပ် have been automatically added to your wallet!\n"
                                f"🎲 Ready for another exciting day of gaming?"
                            )
                            
                            await context.bot.send_message(
                                chat_id=int(user_id),
                                text=cashback_message,
                                parse_mode="HTML"
                            )
                            logger.info(f"✅ Successfully sent cashback notification to user {user_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to notify user {user_id} about cashback: {e}")
    
    # Save the updated data
    save_data_unified(global_data)
    
    # Count total users who received cashback
    total_cashback_users = 0
    total_cashback_amount = 0
    
    for chat_id_str, chat_data in global_data["all_chat_data"].items():
        if "match_history" not in chat_data:
            continue
        yesterday_matches = []
        for match in chat_data["match_history"]:
            match_date = match["timestamp"].date() if isinstance(match["timestamp"], datetime) else datetime.fromisoformat(match["timestamp"]).date()
            if match_date == yesterday:
                yesterday_matches.append(match)
        
        if yesterday_matches:
            user_daily_losses = {}
            for match in yesterday_matches:
                if "losers" in match and isinstance(match["losers"], list):
                    for loser in match["losers"]:
                        user_id = loser.get("user_id")
                        bet_amount = loser.get("bet_amount", 0)
                        if user_id:
                            if user_id not in user_daily_losses:
                                user_daily_losses[user_id] = 0
                            user_daily_losses[user_id] += bet_amount
            
            for user_id, total_loss in user_daily_losses.items():
                if total_loss > 0:
                    cashback = int(total_loss * DAILY_CASHBACK_PERCENTAGE)
                    if cashback > 0:
                        total_cashback_users += 1
                        total_cashback_amount += cashback
    
    logger.info(f"🎉 Daily cashback processing completed! Processed {total_cashback_users} users with total cashback of {total_cashback_amount:,} ကျပ်.")
    
    # Send notification to super admins about daily cashback processing
    await send_daily_cashback_notification_to_super_admins(total_cashback_users, total_cashback_amount, context)


async def send_daily_cashback_notification_to_super_admins(total_users, total_amount, context):
    """
    Send notification to super admins about the daily cashback processing.
    """
    try:
        from config.constants import SUPER_ADMINS
        from utils.formatting import escape_markdown
        
        if total_users == 0:
            message = (
                f"🎁 *Daily Cashback Report*\n\n"
                f"📊 *Status:* No cashback processed today\n"
                f"👥 *Users:* 0 users received cashback\n"
                f"💰 *Total Amount:* 0 ကျပ်\n\n"
                f"ℹ️ No users had losses yesterday to qualify for cashback."
            )
        else:
            message = (
                f"🎁 *Daily Cashback Report*\n\n"
                f"📊 *Status:* Successfully processed\n"
                f"👥 *Users:* {total_users:,} users received cashback\n"
                f"💰 *Total Amount:* {total_amount:,} ကျပ်\n"
                f"📈 *Cashback Rate:* 10%\n\n"
                f"✅ All eligible users have been notified via private message."
            )
        
        # Send to each super admin
        for super_admin_id in SUPER_ADMINS:
            try:
                await context.bot.send_message(
                    chat_id=super_admin_id,
                    text=message,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Successfully sent daily cashback report to super admin {super_admin_id}")
            except Exception as e:
                logger.error(f"❌ Failed to notify super admin {super_admin_id} about daily cashback: {e}")
                
    except Exception as e:
        logger.error(f"Error sending daily cashback notification to super admins: {e}")