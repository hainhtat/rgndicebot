import logging
from datetime import datetime
from typing import Dict, List, Optional

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config.constants import global_data, get_admin_data, SUPER_ADMINS, ADMIN_WALLET_AMOUNT
from data.file_manager import save_data
from utils.telegram_utils import is_admin
from utils.message_formatter import MessageTemplates
from utils.formatting import escape_markdown

logger = logging.getLogger(__name__)


async def refill_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Super admin command to refill admin points with group selection.
    Usage: /refill
    """
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text("❌ This command is only available to super admins.")
        return
    
    # Get all groups where the bot is active
    bot_groups = []
    for chat_id_str, chat_data in global_data["chat_data"].items():
        try:
            chat_id = int(chat_id_str)
            # Try to get chat info to verify bot is still in the group
            chat_info = await context.bot.get_chat(chat_id)
            if chat_info.type in ['group', 'supergroup']:
                bot_groups.append({
                    'id': chat_id,
                    'title': chat_info.title or f"Group {chat_id}",
                    'admin_count': len([uid for uid in chat_data.get('player_stats', {}).keys() 
                                      if await is_admin(chat_id, int(uid), context)])
                })
        except Exception as e:
            logger.warning(f"Could not access group {chat_id_str}: {e}")
            continue
    
    if not bot_groups:
        await update.message.reply_text("❌ No active groups found.")
        return
    
    # Create keyboard with group options
    keyboard = []
    for group in bot_groups:
        keyboard.append([
            InlineKeyboardButton(
                f"🏢 {group['title']} ({group['admin_count']} admins)",
                callback_data=f"refill_group_{group['id']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔄 *Admin Wallet Refill*\n\nSelect a group to refill admin wallets:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_refill_group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle group selection for admin refill.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await query.edit_message_text("❌ This command is only available to super admins.")
        return
    
    # Extract group ID from callback data
    try:
        group_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid group selection.")
        return
    
    # Get admins in the selected group
    try:
        chat_data = global_data["chat_data"].get(str(group_id), {})
        admin_data = get_admin_data(user_id, group_id, update.effective_user.username or update.effective_user.first_name or f"Admin {user_id}")
        
        # Find all admins in this group
        group_admins = []
        for user_id_str in chat_data.get('player_stats', {}).keys():
            try:
                uid = int(user_id_str)
                if await is_admin(group_id, uid, context):
                    admin_info = admin_data.get(user_id_str, {})
                    username = admin_info.get('username') or f'Admin {uid}'
                    current_points = admin_info.get('chat_points', {}).get(str(group_id), {}).get('points', 0)
                    group_admins.append({
                        'id': uid,
                        'username': username,
                        'current_points': current_points
                    })
            except Exception as e:
                logger.warning(f"Error checking admin status for user {user_id_str}: {e}")
                continue
        
        if not group_admins:
            await query.edit_message_text("❌ No admins found in the selected group.")
            return
        
        # Create keyboard with admin options
        keyboard = []
        
        # Add "Refill All" options
        keyboard.append([
            InlineKeyboardButton(
                f"🔄 Refill All to Max ({len(group_admins)})",
                callback_data=f"refill_all_{group_id}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"💰 Custom Amount for All",
                callback_data=f"refill_custom_all_{group_id}"
            )
        ])
        
        # Add individual admin options
        for admin in group_admins:
            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {admin['username']} ({admin['current_points']:,} pts)",
                    callback_data=f"refill_admin_{group_id}_{admin['id']}"
                ),
                InlineKeyboardButton(
                    f"💰 Custom",
                    callback_data=f"refill_custom_{group_id}_{admin['id']}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Groups", callback_data="refill_back_to_groups")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        chat_info = await context.bot.get_chat(group_id)
        group_title = chat_info.title or f"Group {group_id}"
        
        await query.edit_message_text(
            f"🔄 *Refill Admin Wallets*\n\n*Group:* {escape_markdown(group_title)}\n\nSelect admins to refill:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error handling group selection: {e}")
        await query.edit_message_text("❌ Error processing group selection.")


async def handle_refill_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the actual refill action for admins.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await query.edit_message_text("❌ This command is only available to super admins.")
        return
    
    try:
        callback_parts = query.data.split("_")
        action = callback_parts[1]  # "all", "admin", "custom"
        
        if action == "custom":
            # Handle custom amount requests
            if len(callback_parts) >= 4 and callback_parts[2] == "all":
                # Custom amount for all admins
                group_id = int(callback_parts[3])
                await handle_custom_amount_request(update, context, group_id, "all")
            elif len(callback_parts) >= 4:
                # Custom amount for specific admin
                group_id = int(callback_parts[2])
                admin_id = int(callback_parts[3])
                await handle_custom_amount_request(update, context, group_id, "admin", admin_id)
            return
        
        group_id = int(callback_parts[2])
        admin_data = get_admin_data(user_id, group_id, update.effective_user.username or update.effective_user.first_name or f"Admin {user_id}")
        group_id_str = str(group_id)
        
        if action == "all":
            # Refill all admins in the group
            refilled_count = 0
            chat_data = global_data["chat_data"].get(group_id_str, {})
            
            for user_id_str in chat_data.get('player_stats', {}).keys():
                try:
                    uid = int(user_id_str)
                    if await is_admin(group_id, uid, context):
                        # Initialize admin data if needed
                        if user_id_str not in admin_data:
                            admin_data[user_id_str] = {
                                "username": f"Admin {uid}",
                                "chat_points": {}
                            }
                        
                        if group_id_str not in admin_data[user_id_str].get("chat_points", {}):
                            admin_data[user_id_str]["chat_points"][group_id_str] = {
                                "points": 0,
                                "last_refill": None
                            }
                        
                        # Refill to full amount
                        admin_data[user_id_str]["chat_points"][group_id_str]["points"] = ADMIN_WALLET_AMOUNT
                        admin_data[user_id_str]["chat_points"][group_id_str]["last_refill"] = datetime.now()
                        refilled_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error refilling admin {user_id_str}: {e}")
                    continue
            
            # Save data
            save_data(global_data)
            
            chat_info = await context.bot.get_chat(group_id)
            group_title = chat_info.title or f"Group {group_id}"
            
            await query.edit_message_text(
                f"✅ *Refill Complete*\n\n*Group:* {escape_markdown(group_title)}\n*Refilled:* {refilled_count} admins\n*Amount:* {ADMIN_WALLET_AMOUNT:,} points each",
                parse_mode="Markdown"
            )
            
            # Keyboard sending removed as requested
            
        elif action == "admin":
            # Refill specific admin
            if len(callback_parts) < 4:
                await query.edit_message_text("❌ Invalid callback data for admin refill.")
                return
            target_admin_id = int(callback_parts[3])
            target_admin_id_str = str(target_admin_id)
            
            # Initialize admin data if needed
            if target_admin_id_str not in admin_data:
                admin_data[target_admin_id_str] = {
                    "username": f"Admin {target_admin_id}",
                    "chat_points": {}
                }
            
            if group_id_str not in admin_data[target_admin_id_str].get("chat_points", {}):
                admin_data[target_admin_id_str]["chat_points"][group_id_str] = {
                    "points": 0,
                    "last_refill": None
                }
            
            # Refill to full amount
            admin_data[target_admin_id_str]["chat_points"][group_id_str]["points"] = ADMIN_WALLET_AMOUNT
            admin_data[target_admin_id_str]["chat_points"][group_id_str]["last_refill"] = datetime.now()
            
            # Save data
            save_data(global_data)
            
            admin_username = admin_data[target_admin_id_str].get("username") or f"Admin {target_admin_id}"
            chat_info = await context.bot.get_chat(group_id)
            group_title = chat_info.title or f"Group {group_id}"
            
            await query.edit_message_text(
                f"✅ *Refill Complete*\n\n*Group:* {escape_markdown(group_title)}\n*Admin:* {escape_markdown(admin_username)}\n*Amount:* {ADMIN_WALLET_AMOUNT:,} points",
                parse_mode="Markdown"
            )
            
            # Keyboard sending removed as requested
            
    except Exception as e:
        logger.error(f"Error handling refill action: {e}")
        await query.edit_message_text("❌ Error processing refill action.")


async def handle_custom_amount_request(update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int, refill_type: str, admin_id: Optional[int] = None) -> None:
    """
    Handle custom amount refill requests.
    """
    query = update.callback_query
    
    try:
        chat_info = await context.bot.get_chat(group_id)
        group_title = chat_info.title or f"Group {group_id}"
        
        if refill_type == "all":
            message = f"💰 *Custom Refill - All Admins*\n\n*Group:* {escape_markdown(group_title)}\n\nPlease enter the amount to refill for all admins:\n\n*Format: /refill_amount <amount>*\n*Example: /refill_amount 5000000*"
            # Store context for the amount input
            context.user_data['refill_context'] = {
                'type': 'custom_all',
                'group_id': group_id,
                'group_title': group_title
            }
        else:
            admin_data = get_admin_data(admin_id, group_id, f"Admin {admin_id}")
            admin_info = admin_data.get(str(admin_id), {})
            admin_username = admin_info.get('username') or f'Admin {admin_id}'
            current_points = admin_info.get('chat_points', {}).get(str(group_id), {}).get('points', 0)
            
            message = f"💰 *Custom Refill - Single Admin*\n\n*Group:* {escape_markdown(group_title)}\n*Admin:* {escape_markdown(admin_username)}\n*Current:* {current_points:,} points\n\nPlease enter the amount to refill:\n\n*Format: /refill_amount <amount>*\n*Example: /refill_amount 5000000*"
            # Store context for the amount input
            context.user_data['refill_context'] = {
                'type': 'custom_admin',
                'group_id': group_id,
                'group_title': group_title,
                'admin_id': admin_id,
                'admin_username': admin_username
            }
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error handling custom amount request: {e}")
        await query.edit_message_text("❌ Error processing custom amount request.")


async def handle_refill_amount_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /refill_amount command for custom refill amounts.
    """
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text("❌ This command is only available to super admins.")
        return
    
    # Check if there's a refill context
    refill_context = context.user_data.get('refill_context')
    if not refill_context:
        await update.message.reply_text("❌ No active refill request. Please use /refill first.")
        return
    
    # Parse the amount
    try:
        if not context.args:
            await update.message.reply_text("❌ Please provide an amount. Example: /refill_amount 5000000")
            return
        
        amount = int(context.args[0])
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be a positive number.")
            return
        
        if amount > 50000000:  # 50M limit
            await update.message.reply_text("❌ Amount cannot exceed 50,000,000 points.")
            return
        
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")
        return
    
    try:
        admin_data = get_admin_data(user_id, group_id, update.effective_user.username or update.effective_user.first_name or f"Admin {user_id}")
        group_id = refill_context['group_id']
        group_id_str = str(group_id)
        refill_type = refill_context['type']
        
        if refill_type == 'custom_all':
            # Refill all admins with custom amount
            refilled_count = 0
            chat_data = global_data["chat_data"].get(group_id_str, {})
            
            for user_id_str in chat_data.get('player_stats', {}).keys():
                try:
                    uid = int(user_id_str)
                    if await is_admin(group_id, uid, context):
                        # Initialize admin data if needed
                        if user_id_str not in admin_data:
                            admin_data[user_id_str] = {
                                "username": f"Admin {uid}",
                                "chat_points": {}
                            }
                        
                        if group_id_str not in admin_data[user_id_str].get("chat_points", {}):
                            admin_data[user_id_str]["chat_points"][group_id_str] = {
                                "points": 0,
                                "last_refill": None
                            }
                        
                        # Refill with custom amount
                        admin_data[user_id_str]["chat_points"][group_id_str]["points"] = amount
                        admin_data[user_id_str]["chat_points"][group_id_str]["last_refill"] = datetime.now()
                        refilled_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error refilling admin {user_id_str}: {e}")
                    continue
            
            # Save data
            save_data(global_data)
            
            await update.message.reply_text(
                f"✅ *Custom Refill Complete*\n\n*Group:* {escape_markdown(refill_context['group_title'])}\n*Refilled:* {refilled_count} admins\n*Amount:* {amount:,} points each",
                parse_mode="Markdown"
            )
            
        elif refill_type == 'custom_admin':
            # Refill specific admin with custom amount
            admin_id = refill_context['admin_id']
            admin_id_str = str(admin_id)
            
            # Initialize admin data if needed
            if admin_id_str not in admin_data:
                admin_data[admin_id_str] = {
                    "username": refill_context['admin_username'],
                    "chat_points": {}
                }
            
            if group_id_str not in admin_data[admin_id_str].get("chat_points", {}):
                admin_data[admin_id_str]["chat_points"][group_id_str] = {
                    "points": 0,
                    "last_refill": None
                }
            
            # Refill with custom amount
            admin_data[admin_id_str]["chat_points"][group_id_str]["points"] = amount
            admin_data[admin_id_str]["chat_points"][group_id_str]["last_refill"] = datetime.now()
            
            # Save data
            save_data(global_data)
            
            await update.message.reply_text(
                f"✅ *Custom Refill Complete*\n\n*Group:* {escape_markdown(refill_context['group_title'])}\n*Admin:* {escape_markdown(refill_context['admin_username'])}\n*Amount:* {amount:,} points",
                parse_mode="Markdown"
            )
        
        # Clear the refill context
        context.user_data.pop('refill_context', None)
        
    except Exception as e:
        logger.error(f"Error processing custom refill amount: {e}")
        await update.message.reply_text("❌ Error processing refill amount.")


async def handle_back_to_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle back to groups button.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check if user is a super admin
    if user_id not in SUPER_ADMINS:
        await query.edit_message_text("❌ This command is only available to super admins.")
        return
    
    # Recreate the group selection menu
    bot_groups = []
    for chat_id_str, chat_data in global_data["chat_data"].items():
        try:
            chat_id = int(chat_id_str)
            chat_info = await context.bot.get_chat(chat_id)
            if chat_info.type in ['group', 'supergroup']:
                admin_count = len([uid for uid in chat_data.get('player_stats', {}).keys() 
                                  if await is_admin(chat_id, int(uid), context)])
                bot_groups.append({
                    'id': chat_id,
                    'title': chat_info.title or f"Group {chat_id}",
                    'admin_count': admin_count
                })
        except Exception as e:
            logger.warning(f"Could not access group {chat_id_str}: {e}")
            continue
    
    if not bot_groups:
        await query.edit_message_text("❌ No active groups found.")
        return
    
    # Create keyboard with group options
    keyboard = []
    for group in bot_groups:
        keyboard.append([
            InlineKeyboardButton(
                f"🏢 {group['title']} ({group['admin_count']} admins)",
                callback_data=f"refill_group_{group['id']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔄 *Admin Wallet Refill*\n\nSelect a group to refill admin wallets:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_refill_back_to_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle back to groups button.
    """
    query = update.callback_query
    await query.answer()
    
    # Restart the refill command flow
    await refill_command(update, context)