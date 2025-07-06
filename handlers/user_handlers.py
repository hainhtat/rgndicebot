import logging
import pytz
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from config.settings import USE_DATABASE
from database.adapter import db_adapter

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import global_data, get_chat_data_for_id
from config.settings import REFERRAL_BONUS_POINTS as REFERRAL_BONUS, MAIN_GAME_GROUP_LINK as MAIN_GROUP_LINK, ALLOWED_GROUP_IDS, TIMEZONE, SUPER_ADMINS

from handlers.utils import check_allowed_chat, save_data_unified, load_data_unified
from utils.formatting import escape_markdown, escape_markdown_username
from utils.message_formatter import format_wallet, MessageTemplates
from utils.user_utils import get_or_create_global_user_data, get_user_display_name, process_referral, process_pending_referral
from utils.telegram_utils import is_admin, get_admins_from_chat, create_custom_keyboard, send_keyboard_to_all_group_members
from utils.formatting import escape_html

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command in private chats and group chats.
    """
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Handle group chats
    if update.effective_chat.type != "private":
        chat_id = update.effective_chat.id
        
        # Check if this is an allowed group
        if chat_id in ALLOWED_GROUP_IDS:
            # Send welcome message
            welcome_text = f"Welcome to the game, {escape_markdown_username(user.first_name)}! Game controls are being initialized for everyone."
            await update.message.reply_text(
                welcome_text,
                parse_mode="HTML"
            )
            
            # Send keyboard to all group members
            await send_keyboard_to_all_group_members(
                context, 
                chat_id
            )
        return
    
    # Get or create global user data
    global_user_data = get_or_create_global_user_data(user_id, user.first_name, user.last_name, user.username)
    
    # Create a button for the main group
    keyboard = [
        [InlineKeyboardButton("🎮 Join Main Game Group", url=MAIN_GROUP_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check for deep linking parameter (referral)
    if context.args and len(context.args) == 1:
        try:
            referrer_id = int(context.args[0])
            
            # Check if user is already in the main group
            try:
                # Use the first allowed group ID as the main group
                main_group_id = ALLOWED_GROUP_IDS[0]
                chat_member = await context.bot.get_chat_member(main_group_id, user_id)
                is_in_group = chat_member.status not in ["left", "kicked"]
            except Exception as e:
                logger.error(f"Failed to check if user {user_id} is in group: {e}")
                is_in_group = False
            
            # Process the referral
            success, message, referrer_data = await process_referral(user_id, referrer_id, context)
            
            # Simplified welcome message with referral result
            welcome_message = MessageTemplates.WELCOME_WITH_REFERRAL.format(
                name=escape_markdown_username(user.first_name),
                message=message
            )
            
            # Send the welcome message
            await update.message.reply_text(
                welcome_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            # If referral was successful and user is already in the group, process the pending referral immediately
            if success and is_in_group:
                success, referrer_id, notification_message = await process_pending_referral(user_id, context)
                if success and notification_message:
                    try:
                        # Send a private message to the referrer
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=notification_message,
                            parse_mode="HTML"
                        )
                        logger.info(f"Sent referral notification to user {referrer_id} for new member {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")
            
            # No longer sending wallet info when user clicks a referral link
            
            # Return early to avoid sending duplicate welcome message
            return
        except ValueError:
            welcome_message = MessageTemplates.WELCOME_STANDARD.format(
                name=escape_markdown_username(user.first_name)
            )
            
            # Send the welcome message
            await update.message.reply_text(
                welcome_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return
    
    # Standard welcome message with referral link (only reached if no referral parameter)
    # Get the bot username dynamically
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    # Create the referral link dynamically
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Add a share button that sends private message instead of group message
    keyboard.append([InlineKeyboardButton("📤 Share Referral Link", callback_data=f"share_referral_{user_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Standard welcome message with referral link
    welcome_message = MessageTemplates.WELCOME_WITH_REFERRAL_LINK.format(
        name=escape_markdown_username(user.first_name),
        bonus=REFERRAL_BONUS,
        referral_link=referral_link
    )
    
    # For private chats, don't show keyboards - only superadmins can use commands
    await update.message.reply_text(
        welcome_message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    # Don't send additional messages to private chat


async def check_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Check your points balance.
    Usage: /wallet
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    # Check if user is an admin
    is_user_admin = await is_admin(chat_id, user_id, context)
    
    if is_user_admin:
        # Get or create admin data using the helper function
        from config.constants import get_admin_data
        username = update.effective_user.username or update.effective_user.first_name or f"Admin {user_id}"
        admin_wallet_data = get_admin_data(user_id, chat_id, username)
        
        chat_points = admin_wallet_data.get("points", 0)
        last_refill = admin_wallet_data.get("last_refill")
        
        # Format the last refill time
        if last_refill:
            if isinstance(last_refill, datetime):
                # Convert to the configured timezone
                tz = pytz.timezone(TIMEZONE)
                last_refill = last_refill.astimezone(tz)
                last_refill_str = last_refill.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_refill_str = str(last_refill)
        else:
            last_refill_str = "Not available"
        
        # Format the admin wallet message
        wallet_message = "💰 <b>Admin Wallet</b>\n\n"
        
        # Handle username carefully to avoid markdown parsing issues
        safe_username = username
        if username and any(char in username for char in '*_[]()~>#+-=|{}.!'):
            # If username contains special markdown characters, escape them
            safe_username = escape_markdown_username(username)
        
        wallet_message += MessageTemplates.ADMIN_WALLET_SELF.format(
            username=safe_username,
            admin_id=user_id,
            points=chat_points,
            last_refill=last_refill_str
        )
    else:
        # Regular player
        # Get chat data
        chat_data = get_chat_data_for_id(chat_id)
        
        # Get player stats
        if user_id_str not in chat_data["player_stats"]:
            chat_data["player_stats"][user_id_str] = {
                "username": update.effective_user.username or update.effective_user.first_name or f"User {user_id}",
                "score": 0,
                "wins": 0,
                "losses": 0,
                "last_active": datetime.now()
            }
            save_data_unified(global_data)
        
        player_stats = chat_data["player_stats"][user_id_str]
        
        # Get global user data for referral points
        user = update.effective_user
        global_user_data = get_or_create_global_user_data(
            user_id, 
            user.first_name, 
            user.last_name, 
            user.username
        )
        
        # Format the wallet message
        wallet_message = format_wallet(player_stats, global_user_data, user_id)
    
    # Send the wallet message
    await update.message.reply_text(
        wallet_message,
        parse_mode="HTML"
    )


async def deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle deposit requests.
    Restricted for admins as they have admin wallets.
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is an admin and restrict access
    if await is_admin(chat_id, user_id, context):
        await update.message.reply_text(
            "❌ <b>Admins cannot use the deposit system.</b>\n\nAs an admin, you have access to admin wallets that are managed separately.",
            parse_mode="HTML"
        )
        return
    
    # Create inline keyboard with button to contact @rgndiceagent
    keyboard = [
        [InlineKeyboardButton("💬 Contact Agent", url="https://t.me/rgndiceagent")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the deposit message with inline button
    await update.message.reply_text(
        MessageTemplates.DEPOSIT_MESSAGE,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def withdrawal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle withdrawal requests.
    Restricted for admins as they have admin wallets.
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Note: Admins can withdraw from their personal score, not admin wallet
    # Admin wallets are separate from personal scores
    
    # Check if user has at least 5000 points
    try:
        load_data_unified()
        chat_data = global_data["all_chat_data"].get(str(chat_id), {})
        player_stats = chat_data.get("player_stats", {}).get(str(user_id), {})
        user_score = player_stats.get("score", 0)
        
        # Get global user data for referral and bonus points
        global_user_data = global_data["global_user_data"].get(str(user_id), {})
        referral_points = global_user_data.get('referral_points', 0)
        bonus_points = global_user_data.get('bonus_points', 0)
        total_balance = user_score + referral_points + bonus_points
        
        if user_score < 5000:
            user_display_name = await get_user_display_name(context, user_id, chat_id)
            await update.message.reply_text(
                f"❌ <b>ထုတ်ရန် လက်ကျန်ငွေမလုံလောက်ပါ!</b>\n\n"
                f"👤 User: {user_display_name}\n"
                f"💰 <b>Main Wallet:</b> <b>{user_score:,}</b> ကျပ်\n\n"
                f"💸 <b>ငွေထုတ်ရန် :</b> <b>5,000</b> ကျပ်မှစတင်ထုတ်လို့ရပါတယ်နော်\n\n"
                f"<i>Note: Main wallet ထဲကငွေကိုပဲထုတ်လို့ရပါတယ်။</i>",
                parse_mode="HTML"
            )
            return
            
    except Exception as e:
        logger.error(f"Error checking user balance for withdrawal: {e}")
        await update.message.reply_text(
            "❌ <b>Error checking your balance.</b>\n\n"
            "Please try again later or contact an admin.",
            parse_mode="HTML"
        )
        return
    
    # Create inline keyboard with button to contact @rgndiceagent
    keyboard = [
        [InlineKeyboardButton("💬 Contact Agent", url="https://t.me/rgndiceagent")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get user balance information
    main_wallet = player_stats.get('score', 0)
    
    withdrawal_message = MessageTemplates.WITHDRAWAL_MESSAGE.format(
        main_wallet=main_wallet
    )
    
    await update.message.reply_text(
        withdrawal_message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def handle_share_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle share referral button callback - sends private message and opens share dialog.
    """
    query = update.callback_query
    await query.answer()
    
    # Extract user_id from callback data
    callback_data = query.data
    user_id = callback_data.split('_')[-1]
    
    # Get bot username
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    # Create referral link
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Get user's referral stats
    chat_id = update.effective_chat.id
    load_data_unified()
    chat_data = global_data.get(str(chat_id), {})
    player_stats = chat_data.get("player_stats", {}).get(str(user_id), {})
    referral_points = player_stats.get("referral_points", 0)
    
    # Create private message with referral info
    private_message = (
        f"🎮 <b>Join Rangoon Dice Official group!</b> 🎮\n\n"
        f"🚀 <b>Your Rewards:</b> User တစ်ယောက် join ရင်500ကျပ်ရပါမယ်!\n"
        f"🎁 <b>Their Welcome Gift:</b> Join တာနဲ့ 500ကျပ်ရပါမယ်!\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"🏆 <b>Your Referral Empire:</b> {referral_points:,} points earned so far"
    )
    
    # Create share text for the share dialog
    share_text = (
        f"🎲 Dice ဆော့ပြီးပိုက်ဆံရှာရအောင် 🚀\n\n"
        f"🎁 Group join လိုက်တာနဲ့ 500 ကျပ်တန်းရမှာနော်\n"        
        f"✨ Ready to roll? Tap here: {referral_link}\n\n"
        f"🏆 Let's make some dice magic happen! 🎯"
    )
    
    try:
        # Send private message to the user
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=private_message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share with Friends", switch_inline_query=share_text)]
            ])
        )
        
        # Confirm to user that message was sent privately
        await query.edit_message_text(
            text="📤 <b>Referral link sent to your private chat!</b>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error sending private share message: {e}")
        await query.edit_message_text(
            text="❌ <b>Error sending private message.</b>\n\nPlease make sure you have started a private chat with the bot first by clicking /start in a private message.",
            parse_mode="HTML"
        )


async def refer_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Refer another user to earn points.
    Usage: /refer <user_id>
    """
    # Check if the chat is allowed
    if not await check_allowed_chat(update, context):
        return
    
    # Parse command arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            MessageTemplates.INVALID_COMMAND_FORMAT.format(
                usage="/refer <user_id>"
            )
        )
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text(MessageTemplates.USER_ID_MUST_BE_NUMBER)
        return
    
    user_id = update.effective_user.id
    
    # Process the referral
    success, message = await process_referral(target_user_id, user_id, context)
    
    # Send the result message
    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


async def get_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate and send a referral link for the user.
    Restricted for admins as they cannot use the referral system.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin and restrict access
    if await is_admin(chat_id, user_id, context):
        await update.message.reply_text(
            "❌ <b>Admins cannot use the referral system.</b>\n\nAs an admin, you have access to admin wallets instead of the regular referral system.",
            parse_mode="HTML"
        )
        return
    
    user = update.effective_user
    
    # Get or create global user data
    global_user_data = get_or_create_global_user_data(user_id, user.first_name, user.last_name, user.username)
    
    # Get the bot username dynamically
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    # Create the referral link dynamically using the bot's username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Get user's referral stats
    chat_id = update.effective_chat.id
    load_data_unified()
    chat_data = global_data.get(str(chat_id), {})
    player_stats = chat_data.get("player_stats", {}).get(str(user_id), {})
    referral_points = player_stats.get("referral_points", 0)
    
    # Create private message with referral info
    private_message = (
        f"🎮 <b>Join Rangoon Dice Official group!</b> 🎮\n\n"
        f"🚀 <b>Your Rewards:</b> User တစ်ယောက် join ရင်500ကျပ်ရပါမယ်!\n"
        f"🎁 <b>Their Welcome Gift:</b> Join တာနဲ့ 500ကျပ်ရပါမယ်!\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"🏆 <b>Your Referral Empire:</b> {referral_points:,} points earned so far"
    )
    
    # Create share text for the share dialog
    share_text = (
        f"🎲 Hey! Dice ဆော့ပြီးပိုက်ဆံရှာကြမယ်! 🚀\n\n"
        f"🎁 Join တာနဲ့ 500ကျပ်ရပါမယ်!\n"
        f"🔥 Together we'll dominate the leaderboards!\n\n"
        f"✨ Group join ရန်နှိပ်ပါ {referral_link}\n\n"
        f"🏆 Let's make some dice magic happen! 🎯"
    )
    
    try:
        # Send private message to the user
        await context.bot.send_message(
            chat_id=user_id,
            text=private_message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share with Friends", switch_inline_query=share_text)]
            ])
        )
        
        # Send short confirmation in the group
        await update.message.reply_text(
            "📤 <b>Referral link sent to your private chat!</b>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error sending private referral message: {e}")
        # Fallback to group message if private message fails
        referral_message = (
            f"🎮 <b>Join Rangoon Dice Official group!</b> 🎮\n\n"
            f"🚀 <b>Your Rewards:</b> User တစ်ယောက် join ရင်500ကျပ်ရပါမယ်!\n"
            f"🎁 <b>Their Welcome Gift:</b> Join တာနဲ့ 500ကျပ်ရပါမယ်!\n\n"
            f"{referral_link}\n\n"
            f"🏆 <b>Your Referral Empire:</b> {referral_points:,} ကျပ် earned so far"
        )
        
        keyboard = [
            [InlineKeyboardButton("📤 Share with Friends", callback_data=f"share_referral_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Could not send private message.</b>\n\nPlease start a private chat with the bot first by clicking /start in a private message.\n\n{referral_message}",
            parse_mode="HTML",
            reply_markup=reply_markup
        )


async def handle_new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle new chat members, particularly for processing referrals when users join the main group.
    """
    # Check if this is the main group
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    
    # Get the new members
    new_members = update.message.new_chat_members
    
    for member in new_members:
        # Skip if the new member is a bot
        if member.is_bot:
            continue
        
        user_id = member.id
        
        # Process any pending referrals for this user
        success, referrer_id, notification_message = await process_pending_referral(user_id, context)
        
        # If referral was successful, notify the referrer
        if success and notification_message:
            try:
                # Send a private message to the referrer
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=notification_message,
                    parse_mode="HTML"
                )
                logger.info(f"Sent referral notification to user {referrer_id} for new member {user_id}")
                
                # Send notification to superadmins about referral join
                try:
                    # Get referrer and new user display names
                    referrer_name = await get_user_display_name(context, referrer_id, chat_id)
                    new_user_name = await get_user_display_name(context, user_id, chat_id)
                    
                    superadmin_message = f"🎯 <b>New Referral Join</b>\n\n" \
                             f"👤 <b>New User:</b> {escape_html(new_user_name)} ({user_id})\n" \
                             f"👥 <b>Invited by:</b> {escape_html(referrer_name)} ({referrer_id})\n" \
                             f"💰 <b>Bonus Awarded:</b> {REFERRAL_BONUS} ကျပ်"
                    
                    # Send to all superadmins
                    for superadmin_id in SUPER_ADMINS:
                        try:
                            await context.bot.send_message(
                                chat_id=superadmin_id,
                                text=superadmin_message,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Failed to send referral notification to superadmin {superadmin_id}: {e}")
                    
                    logger.info(f"Sent referral join notification to superadmins for user {user_id} referred by {referrer_id}")
                except Exception as e:
                    logger.error(f"Failed to send superadmin notifications for referral join: {e}")
                    
            except Exception as e:
                logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")
        
        # Process welcome bonus for new member
        from utils.user_utils import process_welcome_bonus
        welcome_success, welcome_msg = process_welcome_bonus(
            user_id, 
            update.message.chat_id, 
            member.first_name, 
            member.last_name, 
            member.username
        )
        
        # Welcome the new member to the group
        if welcome_success:
            welcome_message = MessageTemplates.NEW_MEMBER_WELCOME.format(
                name=escape_markdown_username(member.first_name)
            ) + f"\n\n{welcome_msg}"
        else:
            welcome_message = MessageTemplates.NEW_MEMBER_WELCOME.format(
                name=escape_markdown_username(member.first_name)
            )
        
        try:
            await update.message.reply_text(
                welcome_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
            # Try without markdown parsing
            try:
                await update.message.reply_text(
                    welcome_message.replace('*', ''),
                    parse_mode=None
                )
            except Exception as e2:
                logger.error(f"Failed to send welcome message without markdown: {e2}")
        
        # Send keyboard to all group members for the new member
        try:
            await send_keyboard_to_all_group_members(
                context,
                chat_id,
                f"🎮 Welcome {escape_markdown_username(member.first_name)}! Game controls refreshed for everyone."
            )
        except Exception as e:
            logger.error(f"Failed to send keyboard to all group members for new member {user_id}: {e}")