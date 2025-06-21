import logging
import pytz
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import global_data, get_chat_data_for_id
from config.settings import REFERRAL_BONUS_POINTS as REFERRAL_BONUS, MAIN_GAME_GROUP_LINK as MAIN_GROUP_LINK, ALLOWED_GROUP_IDS, TIMEZONE, SUPER_ADMINS
from data.file_manager import save_data
from handlers.utils import check_allowed_chat
from utils.formatting import escape_markdown
from utils.message_formatter import format_wallet, MessageTemplates
from utils.user_utils import get_or_create_global_user_data, get_user_display_name, process_referral, process_pending_referral
from utils.telegram_utils import is_admin, get_admins_from_chat, create_custom_keyboard

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
            # Send welcome message only - keyboards are persistent and managed separately
            welcome_text = f"Welcome to the game, {escape_markdown(user.first_name)}! Your keyboard controls are already available."
            await update.message.reply_text(
                welcome_text,
                parse_mode="Markdown"
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
                name=escape_markdown(user.first_name),
                message=message
            )
            
            # Send the welcome message
            await update.message.reply_text(
                welcome_message,
                parse_mode="Markdown",
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
                            parse_mode="Markdown"
                        )
                        logger.info(f"Sent referral notification to user {referrer_id} for new member {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")
            
            # No longer sending wallet info when user clicks a referral link
            
            # Return early to avoid sending duplicate welcome message
            return
        except ValueError:
            welcome_message = MessageTemplates.WELCOME_STANDARD.format(
                name=escape_markdown(user.first_name)
            )
            
            # Send the welcome message
            await update.message.reply_text(
                welcome_message,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return
    
    # Standard welcome message with referral link (only reached if no referral parameter)
    # Get the bot username dynamically
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    # Create the referral link dynamically
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Create a share button that opens a pre-composed message with the referral link
    share_text = f"🎲 Hey! I'm having a blast playing RGN Dice Bot! Join me and let's play together - you'll get bonus points when you start! {referral_link}"
    share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"
    
    # Add a share button to the keyboard
    keyboard.append([InlineKeyboardButton("📤 Share Referral Link", url=share_url)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Standard welcome message with referral link
    welcome_message = MessageTemplates.WELCOME_WITH_REFERRAL_LINK.format(
        name=escape_markdown(user.first_name),
        bonus=REFERRAL_BONUS,
        referral_link=referral_link
    )
    
    # For private chats, don't show keyboards - only superadmins can use commands
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown",
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
        wallet_message = "💰 *Admin Wallet*\n\n"
        
        # Handle username carefully to avoid markdown parsing issues
        safe_username = username
        if username and any(char in username for char in '*_[]()~>#+-=|{}.!'):
            # If username contains special markdown characters, escape them
            safe_username = escape_markdown(username)
        
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
            save_data(global_data)
        
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
        parse_mode="Markdown"
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
            "❌ *Admins cannot use the deposit system.*\n\nAs an admin, you have access to admin wallets that are managed separately.",
            parse_mode="Markdown"
        )
        return
    
    # Get admin list for this chat
    admin_list = await get_admins_from_chat(chat_id, context)
    
    # Get admin usernames
    admin_usernames = []
    for admin_id in admin_list:
        try:
            # Try to get admin info from chat member
            chat_member = await context.bot.get_chat_member(chat_id, admin_id)
            username = chat_member.user.username
            if username:
                # Escape special Markdown characters in username
                escaped_username = username.replace('_', '\_').replace('*', '\*').replace('[', '\[').replace(']', '\]').replace('(', '\(').replace(')', '\)').replace('~', '\~').replace('`', '\`').replace('>', '\>').replace('#', '\#').replace('+', '\+').replace('-', '\-').replace('=', '\=').replace('|', '\|').replace('{', '\{').replace('}', '\}').replace('.', '\.').replace('!', '\!')
                admin_usernames.append(f"@{escaped_username}")
        except Exception as e:
            logger.error(f"Error getting admin info: {e}")
    
    # If no admin usernames found, use hardcoded admins
    if not admin_usernames:
        admin_usernames = ["@admin1", "@admin2", "@admin3"]
    
    # Format admin list
    admin_list_text = "\n".join(admin_usernames)
    
    deposit_message = MessageTemplates.DEPOSIT_MESSAGE.format(
        admin_list=admin_list_text
    )
    
    try:
        await update.message.reply_text(
            deposit_message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error sending deposit message: {e}")
        # Try without markdown parsing
        await update.message.reply_text(
            deposit_message.replace('*', ''),
            parse_mode=None
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
    
    # Check if user is an admin and restrict access
    if await is_admin(chat_id, user_id, context):
        await update.message.reply_text(
            "❌ *Admins cannot use the withdrawal system.*\n\nAs an admin, you have access to admin wallets that are managed separately.",
            parse_mode="Markdown"
        )
        return
    
    # Get admin list for this chat
    admin_list = await get_admins_from_chat(chat_id, context)
    
    # Get admin usernames
    admin_usernames = []
    for admin_id in admin_list:
        try:
            # Try to get admin info from chat member
            chat_member = await context.bot.get_chat_member(chat_id, admin_id)
            username = chat_member.user.username
            if username:
                # Escape special Markdown characters in username
                escaped_username = username.replace('_', '\_').replace('*', '\*').replace('[', '\[').replace(']', '\]').replace('(', '\(').replace(')', '\)').replace('~', '\~').replace('`', '\`').replace('>', '\>').replace('#', '\#').replace('+', '\+').replace('-', '\-').replace('=', '\=').replace('|', '\|').replace('{', '\{').replace('}', '\}').replace('.', '\.').replace('!', '\!')
                admin_usernames.append(f"@{escaped_username}")
        except Exception as e:
            logger.error(f"Error getting admin info: {e}")
    
    # If no admin usernames found, use hardcoded admins
    if not admin_usernames:
        admin_usernames = ["@admin1", "@admin2", "@admin3"]
    
    # Format admin list
    admin_list_text = "\n".join(admin_usernames)
    
    withdrawal_message = MessageTemplates.WITHDRAWAL_MESSAGE.format(
        admin_list=admin_list_text
    )
    
    try:
        await update.message.reply_text(
            withdrawal_message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error sending withdrawal message: {e}")
        # Try without markdown parsing
        await update.message.reply_text(
            withdrawal_message.replace('*', ''),
            parse_mode=None
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
        parse_mode="Markdown"
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
            "❌ *Admins cannot use the referral system.*\n\nAs an admin, you have access to admin wallets instead of the regular referral system.",
            parse_mode="Markdown"
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
    
    # Create a share button that opens a pre-composed message with the referral link
    import urllib.parse
    share_text = f"🎲 Hey! Join me in the most EPIC dice adventure ever! 🚀\n\n💥 RGN Dice Bot is absolutely INSANE! We're rolling dice, winning big, and having a blast! 🎉\n\n🎁 YOU get 500 points instantly when you join!\n💎 I get rewarded too when you become my gaming buddy!\n🔥 Together we'll dominate the leaderboards!\n\n✨ Ready to roll? Tap here: {referral_link}\n\n🏆 Let's make some dice magic happen! 🎯"
    encoded_text = urllib.parse.quote(share_text)
    share_url = f"https://t.me/share/url?url={referral_link}&text={encoded_text}"
    
    keyboard = [
        [InlineKeyboardButton("📤 Share with Friends", url=share_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create a simpler referral link message
    referral_message = MessageTemplates.REFERRAL_LINK_MESSAGE.format(
        bonus=REFERRAL_BONUS,
        referral_link=referral_link,
        points=global_user_data.get('referral_points', 0)
    )
    
    await update.message.reply_text(
        referral_message,
        parse_mode="Markdown",
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
                    parse_mode="Markdown"
                )
                logger.info(f"Sent referral notification to user {referrer_id} for new member {user_id}")
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
                name=escape_markdown(member.first_name)
            ) + f"\n\n{welcome_msg}"
        else:
            welcome_message = MessageTemplates.NEW_MEMBER_WELCOME.format(
                name=escape_markdown(member.first_name)
            )
        
        try:
            await update.message.reply_text(
                welcome_message,
                parse_mode="Markdown"
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
        
        # Send keyboard to the new member
        from utils.telegram_utils import send_keyboard_to_new_member
        await send_keyboard_to_new_member(context, chat_id, user_id)