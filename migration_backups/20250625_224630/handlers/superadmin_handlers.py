import logging
from typing import Dict, Any, List
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import global_data, SUPER_ADMIN_IDS, ALLOWED_GROUP_IDS
from utils.telegram_utils import create_inline_keyboard
from utils.error_handler import error_handler
from data.file_manager import save_data
from utils.message_formatter import MessageTemplates

logger = logging.getLogger(__name__)


@error_handler
async def my_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show list of groups for superadmin to manage refills.
    Usage: /mygroups
    """
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMIN_IDS:
        # Using simple markdown instead of HTML conversion
        await update.message.reply_text(
            MessageTemplates.NO_PERMISSION_COMMAND,
            parse_mode="Markdown"
        )
        return
    
    # Only work in private chats
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            MessageTemplates.PRIVATE_CHAT_ONLY,
            parse_mode="Markdown"
        )
        return
    
    # Get all allowed groups
    if not ALLOWED_GROUP_IDS:
        await update.message.reply_text(
            MessageTemplates.NO_GROUPS_CONFIGURED,
            parse_mode="Markdown"
        )
        return
    
    # Create buttons for each group
    keyboard = []
    for group_id in ALLOWED_GROUP_IDS:
        try:
            # Get group info
            chat = await context.bot.get_chat(group_id)
            group_name = chat.title or f"Group {group_id}"
            
            # Create button for this group
            keyboard.append([
                InlineKeyboardButton(
                    f"🎮 {group_name}",
                    callback_data=f"mygroups_select_{group_id}"
                )
            ])
        except Exception as e:
            logger.error(f"Error getting info for group {group_id}: {e}")
            # Still add the group with ID only
            keyboard.append([
                InlineKeyboardButton(
                    f"🎮 Group {group_id}",
                    callback_data=f"mygroups_select_{group_id}"
                )
            ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "*🎮 My Groups*\n\n"
        "Select a group to manage refills and admin wallets:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_groups_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the groups list for callback queries.
    """
    query = update.callback_query
    
    # Get configured groups
    configured_groups = get_configured_groups()
    
    if not configured_groups:
        await query.edit_message_text(
            MessageTemplates.NO_GROUPS_CONFIGURED + "\n\n"
            "No groups have been configured yet. Please add groups to the configuration first.",
            parse_mode="Markdown"
        )
        return
    
    # Create keyboard with group options
    keyboard = []
    for group_id, group_name in configured_groups.items():
        keyboard.append([
            InlineKeyboardButton(
                f"🏢 {group_name}",
                callback_data=f"group_{group_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "*🎮 My Groups*\n\n"
        "Select a group to manage refills and admin wallets:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


@error_handler
async def handle_mygroups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from /mygroups command.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMIN_IDS:
        await query.edit_message_text(
            MessageTemplates.NO_PERMISSION_FEATURE,
            parse_mode="Markdown"
        )
        return
    
    data = query.data
    
    if data.startswith("mygroups_select_"):
        # Extract group ID
        group_id = int(data.replace("mygroups_select_", ""))
        
        try:
            # Get group info
            chat = await context.bot.get_chat(group_id)
            group_name = chat.title or f"Group {group_id}"
        except Exception as e:
            logger.error(f"Error getting info for group {group_id}: {e}")
            group_name = f"Group {group_id}"
        
        # Create management options for this group
        keyboard = [
            [
                InlineKeyboardButton(
                    "💰 Refill All Players",
                    callback_data=f"refill_all_{group_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "👑 Refill All Admins",
                    callback_data=f"refill_all_{group_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "👤 Refill Specific Admin",
                    callback_data=f"refill_specific_{group_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💼 Admin Wallets",
                    callback_data=f"admin_wallets_{group_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back to Groups",
                    callback_data="mygroups_back"
                )
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"*🎮 {group_name}*\n\n"
            f"Group ID: `{group_id}`\n\n"
            "Choose an action:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif data == "mygroups_back":
        # Go back to group selection - create a new update object for message context
        from telegram import Update as TelegramUpdate
        # Create a mock message update for the callback
        if update.callback_query and update.callback_query.message:
            # Use edit_message_text instead of calling my_groups_command
            await show_groups_list(update, context)
        else:
            await query.edit_message_text(MessageTemplates.ERROR_GO_BACK_GROUPS)
    
    elif data.startswith("admin_wallets_"):
        # Show admin wallets for specific group
        group_id = int(data.replace("admin_wallets_", ""))
        await show_group_admin_wallets(update, context, group_id)
    
    elif data.startswith("refill_specific_"):
        # Show specific admin selection for refill
        group_id = int(data.replace("refill_specific_", ""))
        await show_specific_admin_refill(update, context, group_id)
    
    elif data.startswith("refill_all_") or data.startswith("refill_admin_"):
        # Handle refill actions
        from handlers.refill_handlers import handle_refill_action
        await handle_refill_action(update, context)


async def show_specific_admin_refill(update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int) -> None:
    """
    Show specific admin selection for refill.
    """
    query = update.callback_query
    
    try:
        # Get group info
        chat = await context.bot.get_chat(group_id)
        group_name = chat.title or f"Group {group_id}"
        
        # Get admins from the group
        admins = await get_admins_from_chat(group_id, context)
        
        if not admins:
            await query.edit_message_text(
                MessageTemplates.NO_ADMINS_FOUND +
                f"*Group:* {escape_markdown(group_name)}\n\n"
                f"No admins found in this group.",
                parse_mode="Markdown"
            )
            return
        
        # Create keyboard with admin options
        keyboard = []
        admin_data = global_data["admin_data"]
        
        for admin_id in admins:
            admin_id_str = str(admin_id)
            
            # Get admin username
            if admin_id_str in admin_data:
                admin_username = admin_data[admin_id_str].get("username", f"Admin {admin_id}")
                current_points = admin_data[admin_id_str].get('chat_points', {}).get(str(group_id), {}).get('points', 0)
            else:
                # Try to get username from Telegram
                try:
                    admin_user = await context.bot.get_chat_member(group_id, admin_id)
                    admin_username = admin_user.user.username or admin_user.user.first_name or f"Admin {admin_id}"
                except Exception:
                    admin_username = f"Admin {admin_id}"
                current_points = 0
            
            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {admin_username} ({current_points:,} pts)",
                    callback_data=f"refill_admin_{group_id}_{admin_id}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back to Group Options",
                callback_data=f"mygroups_select_{group_id}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👤 *Refill Specific Admin*\n\n"
            f"*Group:* {escape_markdown(group_name)}\n\n"
            f"Select an admin to refill:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error showing specific admin refill for group {group_id}: {e}")
        await query.edit_message_text(
            MessageTemplates.ERROR_LOADING_ADMIN_LIST
        )


async def show_group_admin_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int) -> None:
    """
    Show admin wallets for a specific group.
    """
    query = update.callback_query
    
    try:
        # Get group info
        chat = await context.bot.get_chat(group_id)
        group_name = chat.title or f"Group {group_id}"
    except Exception as e:
        logger.error(f"Error getting info for group {group_id}: {e}")
        group_name = f"Group {group_id}"
    
    # Get admin data
    admin_data = global_data["admin_data"]
    chat_id_str = str(group_id)
    
    # Get current admins in this chat
    from utils.telegram_utils import get_admins_from_chat
    try:
        current_admins = await get_admins_from_chat(group_id, context)
    except Exception as e:
        logger.error(f"Error getting admins for group {group_id}: {e}")
        current_admins = []
    
    # Format the message
    message = f"*👑 Admin Wallets - {group_name}*\n\n"
    
    admin_count = 0
    for admin_id in current_admins:
        admin_id_str = str(admin_id)
        admin_count += 1
        
        # Get admin data if exists, otherwise use defaults
        if admin_id_str in admin_data:
            data = admin_data[admin_id_str]
            username = data.get("username") or f"Admin {admin_id}"
            # Fix: Properly access nested chat_points structure
            chat_points_data = data.get("chat_points", {}).get(chat_id_str, {})
            if isinstance(chat_points_data, dict):
                chat_points = chat_points_data.get("points", 0)
                last_refill = chat_points_data.get("last_refill")
            else:
                chat_points = 0
                last_refill = None
        else:
            # Admin not in data yet, show defaults
            try:
                admin_user = await context.bot.get_chat_member(group_id, admin_id)
                username = admin_user.user.username or admin_user.user.first_name or f"Admin {admin_id}"
            except Exception:
                username = f"Admin {admin_id}"
            chat_points = 0
            last_refill = None
        
        if last_refill:
            # Format the last refill time
            if isinstance(last_refill, datetime):
                last_refill_str = last_refill.strftime("%Y-%m-%d %H:%M")
            else:
                last_refill_str = str(last_refill)
            message += f"👤 *@{username}*\n"
            message += f"   💰 Points: `{chat_points:,}`\n"
            message += f"   🕒 Last Refill: {last_refill_str}\n\n"
        else:
            message += f"👤 *@{username}*\n"
            message += f"   💰 Points: `{chat_points:,}`\n"
            message += f"   🕒 Last Refill: Never\n\n"
    
    if admin_count == 0:
        message += "No admin wallets found for this group."
    
    # Add back button
    keyboard = [[
        InlineKeyboardButton(
            "🔙 Back to Group Options",
            callback_data=f"mygroups_select_{group_id}"
        )
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )