import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import pytz
import telegram
from telegram import Update
from telegram.ext import ContextTypes

from config.constants import global_data, get_chat_data_for_id, get_admin_data, SUPER_ADMINS
from config.constants import GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER, ADMIN_WALLET_AMOUNT
from config.settings import ADMIN_INITIAL_POINTS, TIMEZONE
from data.file_manager import save_data
from handlers.utils import check_admin_permission, get_current_game
from utils.formatting import escape_markdown
from utils.message_formatter import MessageTemplates
from utils.telegram_utils import is_admin, update_group_admins, get_admins_from_chat
from utils.user_utils import get_user_display_name, adjust_user_score
from utils.error_handler import error_handler, BotError

logger = logging.getLogger(__name__)


async def adjust_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to adjust a user's score.
    Usage: /adjustscore <user_id or username or reply> <amount> [reason]
    """
    # Check if user is an admin
    if not await check_admin_permission(update, context):
        return
    
    chat_id = update.effective_chat.id
    chat_data = get_chat_data_for_id(chat_id)
    
    # Parse command arguments
    args = context.args
    
    # Check if replying to a message
    target_user = None
    amount = 0
    reason = ""
    
    if update.message.reply_to_message:
        # Get user from replied message
        target_user = update.message.reply_to_message.from_user
        
        if not args:
            await update.message.reply_text(MessageTemplates.ADJUSTSCORE_USAGE_REPLY)
            return
            
        try:
            amount = int(args[0])
            if len(args) > 1:
                reason = " ".join(args[1:])
        except ValueError:
            await update.message.reply_text(MessageTemplates.AMOUNT_MUST_BE_NUMBER)
            return
    else:
        # Not replying to a message, need user ID/username and amount
        if len(args) < 2:
            await update.message.reply_text(MessageTemplates.ADJUSTSCORE_USAGE_FULL)
            return
            
        # Try to parse first argument as user ID or username
        user_identifier = args[0]
        
        try:
            # Check if it's a user ID
            if user_identifier.isdigit():
                target_user_id = int(user_identifier)
                try:
                    target_user = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_user = target_user.user
                except telegram.error.TelegramError:
                    await update.message.reply_text(MessageTemplates.USER_NOT_FOUND_BY_ID.format(user_id=target_user_id))
                    return
            # Check if it's a username
            elif user_identifier.startswith('@'):
                username = user_identifier[1:]  # Remove @ symbol
                # Try to find user by username in chat data
                found = False
                for user_id_str, stats in chat_data["player_stats"].items():
                    if stats.get("username", "").lower() == username.lower():
                        try:
                            target_user = await context.bot.get_chat_member(chat_id, int(user_id_str))
                            target_user = target_user.user
                            found = True
                            break
                        except telegram.error.TelegramError:
                            continue
                if not found:
                    await update.message.reply_text(MessageTemplates.USER_NOT_FOUND_BY_USERNAME.format(username=user_identifier))
                    return
            else:
                await update.message.reply_text(MessageTemplates.INVALID_USER_IDENTIFIER)
                return
                
            # Parse amount and reason
            try:
                amount = int(args[1])
                if len(args) > 2:
                    reason = " ".join(args[2:])
            except ValueError:
                await update.message.reply_text(MessageTemplates.AMOUNT_MUST_BE_NUMBER)
                return
                
        except Exception as e:
            logger.error(f"Error parsing user identifier: {e}")
            await update.message.reply_text(MessageTemplates.FAILED_TO_IDENTIFY_USER)
            return
    
    if not target_user:
        await update.message.reply_text(MessageTemplates.COULD_NOT_IDENTIFY_USER)
        return
        
    target_user_id = target_user.id
    target_user_id_str = str(target_user_id)
    
    # Check if user exists in this chat's player stats
    if target_user_id_str not in chat_data["player_stats"]:
        # Initialize player stats
        username = target_user.username or target_user.first_name or f"User {target_user_id}"
        chat_data["player_stats"][target_user_id_str] = {
            "username": username,
            "score": 0,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now()
        }
    
    # Check admin wallet and deduct/add points
    admin_id = update.effective_user.id
    admin_username = update.effective_user.username or update.effective_user.first_name or f"Admin {admin_id}"
    
    # Get admin wallet data
    admin_wallet_data = get_admin_data(admin_id, chat_id, admin_username)
    
    # Check if admin has enough points for positive adjustments (giving points to users)
    if amount > 0 and admin_wallet_data["points"] < amount:
        await update.message.reply_text(
            f"❌ *Insufficient admin wallet balance!*\n\n"
            f"💰 Your current balance: *{admin_wallet_data['points']:,}* points\n"
            f"💸 Required amount: *{amount:,}* points\n\n"
            f"⏰ Admin wallets are refilled daily at 6 AM Myanmar time.",
            parse_mode="Markdown"
        )
        return
    
    # Adjust admin wallet points based on the action
    if amount > 0:
        # Giving points to user - deduct from admin wallet
        admin_wallet_data["points"] -= amount
        wallet_action = f"deducted {amount:,} points"
    else:
        # Taking points from user - add to admin wallet
        admin_wallet_data["points"] += abs(amount)
        wallet_action = f"added {abs(amount):,} points"
    
    # Log the admin wallet transaction
    logger.info(f"Admin wallet transaction - Admin {admin_id} ({admin_username}) {wallet_action}. New balance: {admin_wallet_data['points']:,} points in chat {chat_id}")
    
    # Adjust the score
    player_stats = chat_data["player_stats"][target_user_id_str]
    old_score = player_stats["score"]
    player_stats["score"] += amount
    
    # Save the updated data
    save_data(global_data)
    
    # Get user display name without escaping markdown characters
    display_name = await get_user_display_name(context, target_user_id, chat_id)
    # No longer escaping the display name
    
    # Format reason text if provided
    reason_text = f"\nReason: {reason}" if reason else ""
    
    # Send confirmation message
    try:
        if amount > 0:
            message_text = MessageTemplates.SCORE_ADDED.format(
                display_name=display_name,
                amount=amount,
                old_score=old_score,
                new_score=player_stats['score'],
                reason_text=reason_text
            )
        else:
            message_text = MessageTemplates.SCORE_DEDUCTED.format(
                display_name=display_name,
                amount=abs(amount),
                old_score=old_score,
                new_score=player_stats['score'],
                reason_text=reason_text
            )
        try:
            await update.message.reply_text(
                message_text,
                parse_mode="Markdown"
            )
        except telegram.error.BadRequest as e:
            if "can't parse entities" in str(e).lower():
                # Fallback to plain text if Markdown parsing fails
                await update.message.reply_text(message_text.replace('*', ''))
    except telegram.error.BadRequest as e:
        # Fallback to plain text if Markdown parsing fails
        if "can't parse entities" in str(e):
            if amount > 0:
                await update.message.reply_text(
                    MessageTemplates.SCORE_ADDED.format(
                        display_name=display_name,
                        amount=amount,
                        old_score=old_score,
                        new_score=player_stats['score'],
                        reason_text=reason_text
                    )
                )
            else:
                await update.message.reply_text(
                    MessageTemplates.SCORE_DEDUCTED.format(
                        display_name=display_name,
                        amount=abs(amount),
                        old_score=old_score,
                        new_score=player_stats['score'],
                        reason_text=reason_text
                    )
                )
        else:
            # Re-raise if it's a different error
            raise


async def check_user_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to check a user's score.
    Usage: 
    - /checkscore <user_id or @username>
    - Reply to a message with /checkscore
    """
    # Check if user is an admin
    if not await check_admin_permission(update, context):
        return
    
    chat_id = update.effective_chat.id
    chat_data = get_chat_data_for_id(chat_id)
    
    # Check if replying to a message
    target_user = None
    
    if update.message.reply_to_message:
        # Get user from replied message
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
    else:
        # Not replying to a message, need user ID/username
        args = context.args
        if not args:
            await update.message.reply_text(MessageTemplates.CHECKSCORE_USAGE)
            return
            
        # Try to parse first argument as user ID or username
        user_identifier = args[0]
        
        try:
            # Check if it's a user ID
            if user_identifier.isdigit():
                target_user_id = int(user_identifier)
                try:
                    target_user = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_user = target_user.user
                except telegram.error.TelegramError:
                    await update.message.reply_text(MessageTemplates.USER_NOT_FOUND_BY_ID.format(user_id=target_user_id))
                    return
            # Check if it's a username
            elif user_identifier.startswith('@'):
                username = user_identifier[1:]  # Remove @ symbol
                # Try to find user by username in chat data
                found = False
                for user_id_str, stats in chat_data["player_stats"].items():
                    if stats.get("username", "").lower() == username.lower():
                        try:
                            target_user = await context.bot.get_chat_member(chat_id, int(user_id_str))
                            target_user = target_user.user
                            found = True
                            break
                        except telegram.error.TelegramError:
                            continue
                if not found:
                    await update.message.reply_text(MessageTemplates.USER_NOT_FOUND_BY_USERNAME.format(username=user_identifier))
                    return
            else:
                await update.message.reply_text(MessageTemplates.INVALID_USER_IDENTIFIER)
                return
        except Exception as e:
            logger.error(f"Error parsing user identifier: {e}")
            await update.message.reply_text(MessageTemplates.FAILED_TO_IDENTIFY_USER)
            return
    
    if not target_user:
        await update.message.reply_text(MessageTemplates.COULD_NOT_IDENTIFY_USER)
        return
        
    target_user_id = target_user.id
    target_user_id_str = str(target_user_id)
    
    # Check if user exists in this chat
    if target_user_id_str not in chat_data["player_stats"]:
        await update.message.reply_text(MessageTemplates.USER_NOT_IN_RECORDS)
        return
    
    # Get user stats
    player_stats = chat_data["player_stats"][target_user_id_str]
    global_user_data = global_data["global_user_data"].get(target_user_id_str, {})
    
    # Get user display name
    display_name = await get_user_display_name(context, target_user_id, chat_id)
    
    # Calculate win rate
    wins = player_stats.get('total_wins', 0)
    losses = player_stats.get('total_losses', 0)
    total_games = wins + losses
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    # Format the message with emojis and win rate
    message = "👤 *User Information*\n\n"
    message += f"🎮 *Player:* {display_name}\n\n"
    message += f"💰 *Wallet:* {player_stats['score']} points\n"
    message += f"🏆 *Wins:* {wins}\n"
    message += f"💔 *Losses:* {losses}\n"
    message += f"📊 *Win Rate:* {win_rate:.1f}%\n"
    
    if global_user_data:
        message += MessageTemplates.USER_INFO_REFERRAL_POINTS.format(
            referral_points=global_user_data.get('referral_points', 0)
        )
        
        if global_user_data.get('referred_by'):
            referrer_id = global_user_data['referred_by']
            referrer_name = await get_user_display_name(context, referrer_id, chat_id)
            message += MessageTemplates.USER_INFO_REFERRED_BY.format(
                referrer_name=escape_markdown(referrer_name),
                referrer_id=referrer_id
            )
    
    # Send the message
    try:
        await update.message.reply_text(message, parse_mode="Markdown")
    except telegram.error.BadRequest as e:
        if "can't parse entities" in str(e).lower():
            # Fallback to plain text if Markdown parsing fails
            await update.message.reply_text(message)
        else:
            # Re-raise if it's a different error
            raise


async def refresh_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to refresh the admin list for a chat.
    Usage: /refreshadmins
    """
    # Check if user is an admin
    if not await check_admin_permission(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Update the admin list
    success = await update_group_admins(chat_id, context)
    
    if success:
        chat_data = get_chat_data_for_id(chat_id)
        admin_count = len(chat_data.get("group_admins", []))
        await update.message.reply_text(MessageTemplates.ADMIN_LIST_REFRESHED.format(count=admin_count))
    else:
        await update.message.reply_text(MessageTemplates.FAILED_REFRESH_ADMIN_LIST)


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to stop the current game.
    Usage: /stopgame
    """
    # Check if user is an admin
    if not await check_admin_permission(update, context):
        return
    
    chat_id = update.effective_chat.id
    chat_data = get_chat_data_for_id(chat_id)
    
    # Use get_current_game which handles state validation
    from handlers.utils import get_current_game
    
    current_game = get_current_game(chat_id)
    
    if not current_game:
        await update.message.reply_text(MessageTemplates.NO_GAME_IN_PROGRESS)
        return
    
    # Process refunds if there are bets
    has_bets = False
    for bet_type in current_game.bets:
        if current_game.bets[bet_type]:
            has_bets = True
            break
    
    if has_bets:
        # Refund all bets
        for bet_type, bets in current_game.bets.items():
            for user_id_str, amount in bets.items():
                if user_id_str in chat_data["player_stats"]:
                    chat_data["player_stats"][user_id_str]["score"] += amount
        
        # Clear the game
        chat_data["current_game"] = None
        
        # Set a cooldown flag to prevent auto_roll_dice from creating a new game immediately
        # This will be checked by auto_roll_dice
        chat_data["manual_stop_cooldown"] = datetime.now()
        
        # Save the updated data
        save_data(global_data)
        
        await update.message.reply_text(MessageTemplates.GAME_STOPPED_WITH_REFUNDS)
        
        # Keyboard sending removed as requested
    else:
        # No bets to refund
        chat_data["current_game"] = None
        
        # Set a cooldown flag to prevent auto_roll_dice from creating a new game immediately
        # This will be checked by auto_roll_dice
        chat_data["manual_stop_cooldown"] = datetime.now()
        
        # Save the updated data
        save_data(global_data)
        await update.message.reply_text(MessageTemplates.GAME_STOPPED_BY_ADMIN)
        
        # Keyboard sending removed as requested


async def admin_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command to view admin wallets.
    Usage: /adminwallets
    """
    # Check if user is an admin
    if not await check_admin_permission(update, context):
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    is_super_admin = user_id in SUPER_ADMINS
    
    # Get admin data
    admin_data = global_data["admin_data"]
    chat_id_str = str(chat_id)
    
    # Get current admins in this chat
    current_admins = await get_admins_from_chat(chat_id, context)
    
    # Format the message
    message = MessageTemplates.ADMIN_WALLETS_HEADER
    
    if is_super_admin:
        # Super admins can see all admin wallets for current admins in the chat
        admin_count = 0
        for admin_id in current_admins:
            admin_id_str = str(admin_id)
            if admin_id_str in admin_data:
                admin_count += 1
                data = admin_data[admin_id_str]
                username = data.get("username") or f"Admin {admin_id}"
                chat_points = data.get("chat_points", {}).get(chat_id_str, {}).get("points", 0)
                last_refill = data.get("chat_points", {}).get(chat_id_str, {}).get("last_refill")
                
                if last_refill:
                    # Format the last refill time
                    if isinstance(last_refill, datetime):
                        # Convert to the configured timezone
                        tz = pytz.timezone(TIMEZONE)
                        last_refill = last_refill.astimezone(tz)
                        last_refill_str = last_refill.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        last_refill_str = str(last_refill)
                else:
                    last_refill_str = "Never"
                
                message += MessageTemplates.ADMIN_WALLET_ENTRY.format(
                    username=escape_markdown(username),
                    admin_id=admin_id,
                    points=chat_points,
                    last_refill=last_refill_str
                )
        
        if admin_count == 0:
            message += MessageTemplates.NO_ADMIN_WALLETS_FOUND
    else:
        # Regular admins can only see their own wallet
        admin_id_str = str(user_id)
        if admin_id_str in admin_data:
            data = admin_data[admin_id_str]
            username = data.get("username") or f"Admin {user_id}"
            chat_points = data.get("chat_points", {}).get(chat_id_str, {}).get("points", 0)
            last_refill = data.get("chat_points", {}).get(chat_id_str, {}).get("last_refill")
            
            if last_refill:
                # Format the last refill time
                if isinstance(last_refill, datetime):
                    # Convert to the configured timezone
                    tz = pytz.timezone(TIMEZONE)
                    last_refill = last_refill.astimezone(tz)
                    last_refill_str = last_refill.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_refill_str = str(last_refill)
            else:
                last_refill_str = "Never"
            
            message += MessageTemplates.ADMIN_WALLET_SELF.format(
                username=escape_markdown(username),
                admin_id=user_id,
                points=chat_points,
                last_refill=last_refill_str
            )
        else:
            message += MessageTemplates.NO_ADMIN_WALLET
    
    # Send the message
    try:
        await update.message.reply_text(message, parse_mode="Markdown")
    except telegram.error.BadRequest as e:
        # Fallback to plain text if Markdown parsing fails
        if "can't parse entities" in str(e):
            # Remove Markdown formatting
            plain_message = message.replace('**', '')
            await update.message.reply_text(plain_message)
        else:
            # Re-raise if it's a different error
            raise


async def manual_refill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Super admin command to manually refill admin points.
    Usage: /refill [admin_id]
    """
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text(MessageTemplates.SUPER_ADMIN_ONLY)
        return
    
    chat_id = update.effective_chat.id
    args = context.args
    
    if args:
        # Refill specific admin
        try:
            admin_id = int(args[0])
        except ValueError:
            await update.message.reply_text(MessageTemplates.ADMIN_ID_MUST_BE_NUMBER)
            return
        
        # Check if admin exists
        admin_id_str = str(admin_id)
        if admin_id_str not in global_data["admin_data"]:
            await update.message.reply_text(MessageTemplates.ADMIN_NOT_FOUND.format(admin_id=admin_id))
            return
        
        # Refill admin points
        admin_data = global_data["admin_data"][admin_id_str]
        chat_id_str = str(chat_id)
        
        if chat_id_str not in admin_data.get("chat_points", {}):
            admin_data["chat_points"][chat_id_str] = {
                "points": 0,
                "last_refill": None
            }
        
        # Check if target is an admin and current user is not super admin
        if admin_id != user_id and admin_id not in SUPER_ADMINS:
            # Regular admins cannot refill other admins
            await update.message.reply_text("❌ Admins cannot refill other admins' points. Only super admins can do this.")
            return
        
        admin_data["chat_points"][chat_id_str]["points"] = ADMIN_WALLET_AMOUNT
        admin_data["chat_points"][chat_id_str]["last_refill"] = datetime.now()
        
        # Save the updated data
        save_data(global_data)
        
        username = admin_data.get("username") or f"Admin {admin_id}"
        await update.message.reply_text(
            MessageTemplates.ADMIN_REFILLED.format(username=username, points=ADMIN_WALLET_AMOUNT)
        )
    else:
        # Refill all admins
        refilled_count = 0
        chat_id_str = str(chat_id)
        
        for admin_id_str, admin_data in global_data["admin_data"].items():
            if chat_id_str not in admin_data.get("chat_points", {}):
                admin_data["chat_points"][chat_id_str] = {
                    "points": 0,
                    "last_refill": None
                }
            
            admin_data["chat_points"][chat_id_str]["points"] = ADMIN_WALLET_AMOUNT
            admin_data["chat_points"][chat_id_str]["last_refill"] = datetime.now()
            refilled_count += 1
        
        # Save the updated data
        save_data(global_data)
        
        await update.message.reply_text(
            MessageTemplates.ALL_ADMINS_REFILLED.format(count=refilled_count, points=ADMIN_WALLET_AMOUNT)
        )


async def handle_admin_score_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle admin replies with +number or -number to adjust user scores.
    This function processes messages from admins that are replies to other users
    and contain just +number or -number to adjust their score.
    """
    # Check if this is a reply to another message
    if not update.message or not update.message.reply_to_message:
        return
    
    # Check if user is an admin
    if not await is_admin(update.effective_chat.id, update.effective_user.id, context):
        return
    
    # Check if the message matches the pattern +number or -number
    message_text = update.message.text.strip()
    adjustment_pattern = re.compile(r'^([+\-]\d+)$')
    match = adjustment_pattern.match(message_text)
    
    if not match:
        return  # Not a score adjustment message
    
    # Extract the amount
    amount_str = match.group(1)
    try:
        amount = int(amount_str)
    except ValueError:
        return  # Not a valid number
    
    # Get the target user from the replied message
    target_user = update.message.reply_to_message.from_user
    if not target_user:
        return
    
    chat_id = update.effective_chat.id
    chat_data = get_chat_data_for_id(chat_id)
    target_user_id = target_user.id
    target_user_id_str = str(target_user_id)
    
    # Check if user exists in this chat's player stats
    if target_user_id_str not in chat_data["player_stats"]:
        # Initialize player stats
        username = target_user.username or target_user.first_name or f"User {target_user_id}"
        chat_data["player_stats"][target_user_id_str] = {
            "username": username,
            "score": 0,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now()
        }
    
    # Check admin wallet and deduct/add points
    admin_id = update.effective_user.id
    admin_username = update.effective_user.username or update.effective_user.first_name or f"Admin {admin_id}"
    
    # Get admin wallet data
    admin_wallet_data = get_admin_data(admin_id, chat_id, admin_username)
    
    # Check if admin has enough points for positive adjustments (giving points to users)
    if amount > 0 and admin_wallet_data["points"] < amount:
        await update.message.reply_text(
            f"❌ *Insufficient admin wallet balance!*\n\n"
            f"💰 Your current balance: *{admin_wallet_data['points']:,}* points\n"
            f"💸 Required amount: *{amount:,}* points\n\n"
            f"⏰ Admin wallets are refilled daily at 6 AM Myanmar time.",
            parse_mode="Markdown"
        )
        return
    
    # Adjust admin wallet points based on the action
    if amount > 0:
        # Giving points to user - deduct from admin wallet
        admin_wallet_data["points"] -= amount
        wallet_action = f"deducted {amount:,} points"
    else:
        # Taking points from user - add to admin wallet
        admin_wallet_data["points"] += abs(amount)
        wallet_action = f"added {abs(amount):,} points"
    
    # Log the admin wallet transaction
    logger.info(f"Admin wallet transaction (quick adjust) - Admin {admin_id} ({admin_username}) {wallet_action}. New balance: {admin_wallet_data['points']:,} points in chat {chat_id}")
    
    # Adjust the score
    player_stats = chat_data["player_stats"][target_user_id_str]
    old_score = player_stats["score"]
    player_stats["score"] += amount
    
    # Save the updated data
    save_data(global_data)
    
    # Get user display name
    display_name = await get_user_display_name(context, target_user_id, chat_id)
    
    # Format reason text (empty for +amount/-amount adjustments)
    reason_text = ""
    
    # Send confirmation message
    try:
        if amount > 0:
            message_text = MessageTemplates.SCORE_ADDED.format(
                display_name=display_name,
                amount=amount,
                old_score=old_score,
                new_score=player_stats['score'],
                reason_text=reason_text
            )
        else:
            message_text = MessageTemplates.SCORE_DEDUCTED.format(
                display_name=display_name,
                amount=abs(amount),
                old_score=old_score,
                new_score=player_stats['score'],
                reason_text=reason_text
            )
        try:
            await update.message.reply_text(
                message_text,
                parse_mode="Markdown"
            )
        except telegram.error.BadRequest as e:
            if "can't parse entities" in str(e).lower():
                # Fallback to plain text if Markdown parsing fails
                await update.message.reply_text(message_text.replace('*', ''))
    except Exception as e:
        logger.error(f"Error sending confirmation message: {e}")
        # Fallback to simple message
        await update.message.reply_text(MessageTemplates.SCORE_ADJUSTMENT_FALLBACK.format(
            old_score=old_score,
            new_score=player_stats['score']
        ))