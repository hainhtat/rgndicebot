import logging
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import global_data, SUPER_ADMINS, ADMIN_WALLET_AMOUNT
from utils.telegram_utils import is_admin
from utils.formatting import escape_markdown
from utils.message_formatter import MessageTemplates

logger = logging.getLogger(__name__)


async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the Admin Panel button press.
    Shows different options based on admin level.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin in this chat
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text(MessageTemplates.ADMIN_ONLY_FEATURE)
        return
    
    is_super_admin = user_id in SUPER_ADMINS
    
    # Create keyboard based on admin level
    keyboard = []
    
    # Common admin functions
    keyboard.append([
        InlineKeyboardButton("📊 Admin Wallets", callback_data="admin_panel_wallets"),
        InlineKeyboardButton("🎯 Adjust Score", callback_data="admin_panel_adjust")
    ])
    
    keyboard.append([
        InlineKeyboardButton("👥 Check Score", callback_data="admin_panel_check"),
        InlineKeyboardButton("🔄 Refresh Admins", callback_data="admin_panel_refresh")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🛑 Stop Game", callback_data="admin_panel_stop")
    ])
    
    # Super admin only functions
    if is_super_admin:
        keyboard.append([
            InlineKeyboardButton("💰 Refill Wallets", callback_data="admin_panel_refill"),
            InlineKeyboardButton("🔧 Manual Refill", callback_data="admin_panel_manual_refill")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_type = "Super Admin" if is_super_admin else "Admin"
    
    await update.message.reply_text(
        f"👑 *{admin_type} Panel*\n\nSelect an action:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle admin panel callback queries.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin
    if not await is_admin(chat_id, user_id, context):
        await query.edit_message_text(MessageTemplates.ADMIN_ONLY_FEATURE)
        return
    
    action = query.data.replace("admin_panel_", "")
    
    try:
        if action == "wallets":
            # Import and call admin wallets function
            from handlers.admin_handlers import admin_wallets
            # Create a fake update object for the command
            fake_update = type('obj', (object,), {
                'effective_user': update.effective_user,
                'effective_chat': update.effective_chat,
                'message': type('obj', (object,), {
                    'reply_text': query.edit_message_text
                })()
            })()
            await admin_wallets(fake_update, context)
            
        elif action == "adjust":
            await query.edit_message_text(
                "🎯 *Adjust Score*\n\nUse the command: `/adjustscore @username amount`\n\nExample: `/adjustscore @john 1000`",
                parse_mode="Markdown"
            )
            
        elif action == "check":
            await query.edit_message_text(
                "👥 *Check Score*\n\nUse the command: `/checkscore @username`\n\nExample: `/checkscore @john`",
                parse_mode="Markdown"
            )
            
        elif action == "refresh":
            await query.edit_message_text(
                "🔄 *Refresh Admins*\n\nUse the command: `/refreshadmins`\n\nThis will update the admin list for this group.",
                parse_mode="Markdown"
            )
            
        elif action == "stop":
            await query.edit_message_text(
                "🛑 *Stop Game*\n\nUse the command: `/stopgame`\n\nThis will stop the current game in this group.",
                parse_mode="Markdown"
            )
            
        elif action == "refill":
            # Check if super admin
            if user_id not in SUPER_ADMINS:
                await query.edit_message_text(MessageTemplates.SUPER_ADMIN_ONLY_FEATURE)
                return
            
            # Import and call refill function
            from handlers.refill_handlers import refill_command
            fake_update = type('obj', (object,), {
                'effective_user': update.effective_user,
                'effective_chat': update.effective_chat,
                'message': type('obj', (object,), {
                    'reply_text': query.edit_message_text
                })()
            })()
            await refill_command(fake_update, context)
            
        elif action == "manual_refill":
            # Check if super admin
            if user_id not in SUPER_ADMINS:
                await query.edit_message_text(MessageTemplates.SUPER_ADMIN_ONLY_FEATURE)
                return
                
            await query.edit_message_text(
                "🔧 *Manual Refill*\n\nUse the command: `/manualrefill`\n\nThis will refill all admin wallets in this group to maximum amount.",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error handling admin panel callback: {e}")
        await query.edit_message_text(MessageTemplates.ERROR_PROCESSING_ADMIN_PANEL)