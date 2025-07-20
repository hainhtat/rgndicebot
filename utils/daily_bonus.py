import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import pytz
from config.settings import USE_DATABASE, TIMEZONE
from database.adapter import db_adapter

from config.constants import global_data
from config.settings import DAILY_CASHBACK_PERCENTAGE

from handlers.utils import save_data_unified

logger = logging.getLogger(__name__)

async def process_daily_cashback(context):
    """
    Process daily cashback for all users based on the new formula:
    5% of (topup amount - remaining amount at 12 AM UTC+6:30)
    This function is scheduled to run once per day.
    """
    logger.info("🎁 Starting daily cashback processing for all users...")
    
    # Get Myanmar timezone (UTC+6:30)
    tz = pytz.timezone(TIMEZONE)
    
    # Get current date and yesterday's date in Myanmar timezone
    now = datetime.now(tz)
    today = now.date()
    yesterday = today - timedelta(days=1)
    
    # Calculate midnight time for yesterday in Myanmar timezone
    yesterday_midnight = tz.localize(datetime.combine(yesterday, datetime.min.time()))
    today_midnight = tz.localize(datetime.combine(today, datetime.min.time()))
    
    # Initialize tracking structures if not exists
    if "daily_losses" not in global_data:
        global_data["daily_losses"] = {}
    if "user_topups" not in global_data:
        global_data["user_topups"] = {}
    if "global_user_data" not in global_data:
        global_data["global_user_data"] = {}
    
    total_cashback_users = 0
    total_cashback_amount = 0
    
    # Process each chat
    for chat_id_str, chat_data in global_data["all_chat_data"].items():
        if "player_stats" not in chat_data:
            continue
        
        # Process each user in the chat
        for user_id, player_stats in chat_data["player_stats"].items():
            try:
                # Get user's topup data for yesterday
                user_topups = global_data["user_topups"].get(user_id, {})
                yesterday_topup_data = user_topups.get(str(yesterday), {})
                
                if not yesterday_topup_data:
                    # If no topup data exists, try to calculate from match history
                    yesterday_topup_data = calculate_topup_from_history(
                        user_id, chat_id_str, yesterday, chat_data
                    )
                    
                    if yesterday_topup_data:
                        # Store calculated topup data
                        if user_id not in global_data["user_topups"]:
                            global_data["user_topups"][user_id] = {}
                        global_data["user_topups"][user_id][str(yesterday)] = yesterday_topup_data
                
                if not yesterday_topup_data:
                    logger.debug(f"No topup data found for user {user_id} on {yesterday}")
                    continue
                
                total_topup = yesterday_topup_data.get("total_topup", 0)
                remaining_at_midnight = yesterday_topup_data.get("remaining_at_midnight", 0)
                
                # Calculate daily loss (topup amount - remaining amount at midnight)
                daily_loss = total_topup - remaining_at_midnight
                
                if daily_loss <= 0:
                    logger.debug(f"User {user_id} had no loss on {yesterday} (topup: {total_topup}, remaining: {remaining_at_midnight})")
                    continue
                
                # Calculate 5% cashback
                cashback = int(daily_loss * DAILY_CASHBACK_PERCENTAGE)
                
                if cashback <= 0:
                    continue
                
                # Initialize global user data if not exists
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
                        db_adapter.update_user_bonus_points(int(user_id), 
                            global_data["global_user_data"][user_id]["bonus_points"])
                    except Exception as e:
                        logger.error(f"Failed to sync bonus points to database for user {user_id}: {e}")
                
                # Record the cashback in daily_losses
                if user_id not in global_data["daily_losses"]:
                    global_data["daily_losses"][user_id] = {}
                
                global_data["daily_losses"][user_id][str(yesterday)] = {
                    "total_topup": total_topup,
                    "remaining_at_midnight": remaining_at_midnight,
                    "daily_loss": daily_loss,
                    "cashback": cashback,
                    "cashback_rate": DAILY_CASHBACK_PERCENTAGE,
                    "processed_at": datetime.now().isoformat()
                }
                
                total_cashback_users += 1
                total_cashback_amount += cashback
                
                logger.info(f"💰 Awarded {cashback} ကျပ် cashback to user {user_id} for {daily_loss} ကျပ် loss (topup: {total_topup}, remaining: {remaining_at_midnight}) in chat {chat_id_str}")
                
                # Try to notify the user about their cashback
                try:
                    username = player_stats.get("username", f"User {user_id}")
                    cashback_message = (
                        f"🎁 <b>Daily Cashback Reward!</b> 🎁\n\n"
                        f"🌟 Great news! You've received your daily cashback bonus!\n\n"
                        f"💰 <b>Cashback Amount:</b> {cashback:,} ကျပ်\n"
                        f"📊 <b>Yesterday's Topup:</b> {total_topup:,} ကျပ်\n"
                        f"💳 <b>Remaining at Midnight:</b> {remaining_at_midnight:,} ကျပ်\n"
                        f"📉 <b>Daily Loss:</b> {daily_loss:,} ကျပ်\n"
                        f"🎯 <b>Cashback Rate:</b> {int(DAILY_CASHBACK_PERCENTAGE * 100)}%\n\n"
                        f"🚀 Your ကျပ် have been automatically added to your bonus wallet!\n"
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
                    
            except Exception as e:
                logger.error(f"Error processing cashback for user {user_id}: {e}")
                continue
    
    # Save the updated data
    save_data_unified(global_data)
    
    logger.info(f"🎉 Daily cashback processing completed! Processed {total_cashback_users} users with total cashback of {total_cashback_amount:,} ကျပ်.")
    
    # Send notification to super admins about daily cashback processing
    await send_daily_cashback_notification_to_super_admins(total_cashback_users, total_cashback_amount, context)


def calculate_topup_from_history(user_id: str, chat_id: str, target_date: datetime.date, chat_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate user's topup and remaining amount from match history if direct topup data is not available.
    This is a fallback method to estimate topup data from game activity.
    """
    try:
        match_history = chat_data.get("match_history", [])
        player_stats = chat_data.get("player_stats", {}).get(user_id, {})
        
        if not match_history or not player_stats:
            return None
        
        # Get matches from the target date
        target_matches = []
        for match in match_history:
            match_timestamp = match.get("timestamp")
            if isinstance(match_timestamp, str):
                match_timestamp = datetime.fromisoformat(match_timestamp)
            
            if match_timestamp.date() == target_date:
                target_matches.append(match)
        
        if not target_matches:
            return None
        
        # Calculate total bets (losses) for the day
        total_bets = 0
        total_winnings = 0
        
        for match in target_matches:
            # Check if user was a loser
            losers = match.get("losers", [])
            for loser in losers:
                if loser.get("user_id") == user_id:
                    total_bets += loser.get("bet_amount", 0)
            
            # Check if user was a winner
            winners = match.get("winners", [])
            for winner in winners:
                if winner.get("user_id") == user_id:
                    total_winnings += winner.get("payout", 0)
        
        # Estimate topup as current score + total bets - total winnings
        # This is an approximation and may not be 100% accurate
        current_score = player_stats.get("score", 0)
        estimated_topup = current_score + total_bets - total_winnings
        
        # If estimated topup is negative or zero, assume no topup
        if estimated_topup <= 0:
            return None
        
        return {
            "total_topup": max(estimated_topup, total_bets),  # At least the amount they bet
            "remaining_at_midnight": current_score,
            "estimated": True,  # Mark as estimated data
            "total_bets": total_bets,
            "total_winnings": total_winnings
        }
        
    except Exception as e:
        logger.error(f"Error calculating topup from history for user {user_id}: {e}")
        return None


async def send_daily_cashback_notification_to_super_admins(total_users, total_amount, context):
    """
    Send notification to super admins about the daily cashback processing.
    """
    try:
        from config.constants import SUPER_ADMINS
        from utils.formatting import escape_markdown
        
        if total_users == 0:
            message = (
                f"🎁 <b>Daily Cashback Report</b>\n\n"
                f"📊 <b>Status:</b> No cashback processed today\n"
                f"👥 <b>Users:</b> 0 users received cashback\n"
                f"💰 <b>Total Amount:</b> 0 ကျပ်\n\n"
                f"ℹ️ No users had qualifying losses yesterday for cashback.\n"
                f"📝 <b>Formula:</b> 5% of (topup amount - remaining amount at 12 AM UTC+6:30)"
            )
        else:
            message = (
                f"🎁 <b>Daily Cashback Report</b>\n\n"
                f"📊 <b>Status:</b> Successfully processed\n"
                f"👥 <b>Users:</b> {total_users:,} users received cashback\n"
                f"💰 <b>Total Amount:</b> {total_amount:,} ကျပ်\n"
                f"📈 <b>Cashback Rate:</b> {int(DAILY_CASHBACK_PERCENTAGE * 100)}%\n\n"
                f"📝 <b>Formula:</b> 5% of (topup amount - remaining amount at 12 AM UTC+6:30)\n"
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


async def track_user_topup(user_id: str, amount: int, context=None):
    """
    Track user topup for cashback calculation.
    This should be called whenever a user tops up their account.
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).date()
        
        if "user_topups" not in global_data:
            global_data["user_topups"] = {}
        
        if user_id not in global_data["user_topups"]:
            global_data["user_topups"][user_id] = {}
        
        today_str = str(today)
        if today_str not in global_data["user_topups"][user_id]:
            global_data["user_topups"][user_id][today_str] = {
                "total_topup": 0,
                "remaining_at_midnight": 0,
                "topup_history": []
            }
        
        # Add to total topup
        global_data["user_topups"][user_id][today_str]["total_topup"] += amount
        global_data["user_topups"][user_id][today_str]["topup_history"].append({
            "amount": amount,
            "timestamp": datetime.now(tz).isoformat()
        })
        
        logger.info(f"📈 Tracked topup of {amount:,} ကျပ် for user {user_id} on {today}")
        
        # Save data
        save_data_unified(global_data)
        
    except Exception as e:
        logger.error(f"Error tracking topup for user {user_id}: {e}")


async def update_user_midnight_balance(user_id: str, chat_id: str, balance: int):
    """
    Update user's balance at midnight for cashback calculation.
    This should be called at midnight (12 AM UTC+6:30) to record remaining balances.
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).date()
        
        if "user_topups" not in global_data:
            global_data["user_topups"] = {}
        
        if user_id not in global_data["user_topups"]:
            global_data["user_topups"][user_id] = {}
        
        today_str = str(today)
        if today_str not in global_data["user_topups"][user_id]:
            global_data["user_topups"][user_id][today_str] = {
                "total_topup": 0,
                "remaining_at_midnight": balance,
                "topup_history": []
            }
        else:
            global_data["user_topups"][user_id][today_str]["remaining_at_midnight"] = balance
        
        logger.debug(f"💳 Updated midnight balance for user {user_id}: {balance:,} ကျပ်")
        
    except Exception as e:
        logger.error(f"Error updating midnight balance for user {user_id}: {e}")