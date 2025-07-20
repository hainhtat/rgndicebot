import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Union

from config.constants import RESULT_EMOJIS, GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER
from utils.formatting import escape_markdown, escape_markdown_username, escape_html

logger = logging.getLogger(__name__)

def format_markdown(text):
    """
    Keep markdown-style formatting as is for Telegram's parse_mode="Markdown".
    *bold* -> *bold*
    `code` -> `code`
    """
    # No conversion needed - return text as is for Markdown parsing
    return text

# Message templates
class MessageTemplates:
    # Game status messages
    GAME_STARTED = "🎲<b>ပွဲစဉ်#{match_id} - လောင်းကြေးဖွင့်ပါပြီ</b>🎲"
    BETTING_CLOSED = "🎲  လောင်းကြေးပိတ်ပါပြီ  🎲"
    GAME_OVER = "🏁 <b>Game over</b>\nResult: {result}"
    # Additional templates from handlers
    INVALID_TARGET_BOT = "❌ <b>Invalid target!</b>\n\nYou cannot adjust the score of a bot."
    INVALID_TARGET_ADMIN = "❌ <b>Invalid target!</b>\n\nYou cannot adjust the score of another admin."
    INSUFFICIENT_ADMIN_BALANCE = "❌ <b>Insufficient admin wallet balance!</b>\n\n💰 Your current balance: <b>{balance:,}</b> ကျပ်\n💸 Required amount: <b>{amount:,}</b> ကျပ်\n\n⏰ Admin wallets are refilled daily at 6 AM Myanmar time."
    INSUFFICIENT_USER_BALANCE = "❌ <b>Insufficient user balance!</b>\n\n👤 User: {display_name}\n💰 Current balance: <b>{balance:,}</b> ကျပ်\n💸 Required amount: <b>{amount:,}</b> ကျပ်\n\nCannot deduct more ကျပ် than the user has."
    CANNOT_DEDUCT_NEGATIVE = "❌ <b>Cannot deduct {amount:,} ကျပ်!</b>\n\n👤 User: {display_name}\n💰 Current balance: <b>{old_score:,}</b> ကျပ်\n💸 Requested deduction: <b>{deduct_amount:,}</b> ကျပ်\n\nUser would have a negative balance of <b>{new_score:,}</b> ကျပ်."
    TIME_REMAINING = "⏱️ <b>စတင်မည့်အချိန်:</b> {seconds}s"
    CLOSING_SOON = "⏱️ <b>Closing soon...</b>"
    
    # Betting instructions
    BETTING_INSTRUCTIONS = (
        "<b>လောင်းကြေးထပ်ရန်</b>\n"
"🎲 <b>BIG (8-12):</b> <b>B 500</b> or <b>BIG 500</b> လို့ရိုက်ပါ\n"
"🎯 <b>SMALL (2-6):</b> <b>S 500</b> or <b>SMALL 500</b> လို့ရိုက်ပါ\n"
"🍀 <b>LUCKY (7):</b> <b>L 500</b> or <b>LUCKY 500</b> လို့ရိုက်ပါ\n\n"
"💰 <b>လျော်မည့်ဆ:</b>\n"
        "- <b>BIG/SMALL:</b> <b>1.95x</b>\n"
        "- <b>LUCKY:</b> <b>4.5x</b>"
    )

    BETTING_PAYOUT = (
        "💰 <b>လျော်မည့်ဆ:</b>\n"
        "- <b>BIG/SMALL:</b> <b>1.95x</b>\n"
        "- <b>LUCKY:</b> <b>4.5x</b>"
    )
    
    # Bet confirmation
    BET_CONFIRMATION = "✅ {display_name} <b>{bet_type}</b> ပေါ် <b>{amount}</b> လောင်းကြေးထပ်လိုက်ပါပြီ\n\n📊 <b>Total Bets:</b>\n{total_bets_display}\n\n💰 <b>Wallet</b> - <b>{score}</b> ကျပ်\n🎁 <b>Referral</b> - <b>{referral_points}</b> ကျပ်\n🎉 <b>Bonus</b> - <b>{bonus_points}</b> ကျပ်"
    INSUFFICIENT_FUNDS = "<b>ငွေမလုံလောက်ပါ</b>\n\n💰 <b>လက်ကျန်:</b> {total} ကျပ်\n🎯 <b>လိုအပ်သည်:</b> {shortfall} ကျပ်"
    INVALID_BET_AMOUNT = "❌ <b>ငွေပမာဏ အနည်းဆုံး 100 ဖြစ်ရပါမည်</b>။"
    NO_ACTIVE_GAME = "❌ <b>No active game</b> is accepting bets right now."
    ADMIN_CANNOT_PARTICIPATE = "❌ Admins cannot participate in games."
    
    # Error messages
    GENERAL_ERROR = "❌ <b>Error:</b> {message}"
    CHAT_NOT_ALLOWED = "⚠️ This bot is only available in <b>authorized groups</b>.\nPlease join our <b>official group:</b> {group_link}"
    ADMIN_ONLY = "⚠️ This command is only available to <b>admins</b>."
    
    # User messages
    WALLET_HEADER = "💰 <b>{name}'s Wallet</b>\n\n"
    WALLET_MAIN_BALANCE = "<b>💵 Main Balance:</b> {score} ကျပ်\n"
    WALLET_REFERRAL_BONUS = "<b>🎁 Referral Bonus:</b> {referral_points} ကျပ်\n"
    WALLET_BONUS_POINTS = "<b>🎉 Bonus Points:</b> {bonus_points} ကျပ်\n"
    WALLET_TOTAL_BALANCE = "<b>📊 Total Balance:</b> {total} ကျပ်"
    
    # Game result
    GAME_RESULT_HEADER = "🎲 <b>Game Result</b>\n"
    GAME_RESULT_ROLL = "Roll: <b>{dice_result}</b> | Winner: {emoji} <b>{winning_type}</b>\n"
    WINNERS_HEADER = "<b>Winners:</b>\n"
    NO_WINNERS = "<b>No winners this round</b>\n"
    WINNER_ENTRY = "- {username}: Bet <b>{bet_amount}</b>, Won <b>{winnings}</b>\n"
    MORE_WINNERS = "...and {count} more\n"
    TOTAL_SUMMARY = "Total: Won <b>{total_won}</b> | Lost <b>{total_lost}</b>"
    
    # Game management messages
    GAME_STOPPED_INACTIVITY = "🛑 <b>3 ပွဲဆက်တိုက်ဆော့မယ့်သူမရှိလို့ ရပ်လိုက်ပါပြီ.</b>\n\n<b>Contact admins</b> to start new game:\n{admin_list}"
    BETTING_CLOSED_WITH_PARTICIPANTS = "⏱ <b>လောင်းကြေးပိတ်ပါပြီ!</b>\n\n{participants_msg}\n\n<b>Rolling dice</b> in <b>{roll_delay} seconds</b>..."
    PARTICIPANTS_HEADER = "<b>Participants({count})</b>"
    NO_PARTICIPANTS = "<b>Participants(0)</b>\n<b>No participants</b>"
    DICE_ANIMATION_FAILED = "⚠️ <b>Dice animation failed</b>, using <b>manual roll</b>\n\n{result}"
    
    # Admin messages
    GAME_STOPPED_BY_ADMIN = "🛑 <b>Game stopped</b> by admin."
    GAME_STOPPED_WITH_REFUNDS = "🛑 <b>Game stopped</b> by admin. 💰 <b>All bets</b> have been <b>refunded</b>."
    NO_GAME_IN_PROGRESS = "❌ <b>No game</b> is currently in progress."
    GAME_ALREADY_IN_PROGRESS = "❌ A <b>game is already in progress</b>. Please <b>finish the current game</b> first."
    STARTING_NEW_GAME = "🎲 <b>Starting a new dice game</b>..."
    FAILED_GAME_CREATION = "❌ Error: Failed to create a new game. Please try again."
    
    # Welcome messages
    WELCOME_WITH_REFERRAL = "👋 <b>Welcome to Rangoon Dice Bot, {name}!</b>\n\n{message}\n\n!"
    WELCOME_STANDARD = "👋 <b>Welcome to RGN Dice Bot, {name}!</b>\n\nGroup ထဲဝင်ဖို့ အောက်ကခလုတ်လေးကို နှိပ်ပြီး စဆော့လို့ရပါပြီနော်!"
    WELCOME_WITH_REFERRAL_LINK = "👋 <b>Welcome to RGN Dice Bot, {name}!</b>\n\nGroup ထဲဝင်ဖို့ အောက်ကခလုတ်လေးကို နှိပ်ပြီး စဆော့လို့ရပါပြီနော်\n\n🎁 <b>Invite Friends & Earn Rewards</b>\nShare your referral link to earn <b>{bonus} ကျပ်</b> for each new player who joins!\n\n📱 <b>Your Referral Link:</b>\n<code>{referral_link}</code>"
    
    # Deposit and withdrawal messages
    DEPOSIT_MESSAGE = "<b>ငွေထည့်ရန်</b>\n\nငွေထည့်ရန် အောက်ကခလုတ်ကိုနှိပ်ပါ"
    WITHDRAWAL_MESSAGE = "<b>ငွေထုတ်ရန်</b>\n\n💰 <b>Main Wallet:</b> {main_wallet} ကျပ်\n\n⚠️ <b>Note:</b> Only Main Wallet balance can be withdrawn (Minimum: 5,000 ကျပ်)\n\n✅ <b>Withdrawal request submitted successfully!</b>\n\nငွေထုတ်ရန် အောက်ပါ Agent ထံ ဆက်သွယ်ပါ။"
    
    # Error messages
    INVALID_COMMAND_FORMAT = "❌ <b>Invalid command format</b>\nUsage: {usage}"
    USER_ID_MUST_BE_NUMBER = "❌ <b>User ID must be a number</b>"
    AMOUNT_MUST_BE_NUMBER = "❌ <b>Amount must be a number.</b>"
    USER_NOT_FOUND_BY_ID = "❌ User with ID {user_id} not found in this chat."
    USER_NOT_FOUND_BY_USERNAME = "❌ User with username {username} not found in this chat."
    INVALID_USER_IDENTIFIER = "❌ Invalid user identifier. Use a user ID or @username."
    FAILED_TO_IDENTIFY_USER = "❌ Failed to identify user. Please try again."
    COULD_NOT_IDENTIFY_USER = "❌ Could not identify target user."
    USER_NOT_IN_RECORDS = "❌ User not found in this chat's records."
    
    # Admin command usage messages
    ADJUSTSCORE_USAGE_REPLY = "❌ Please specify an amount when replying to a user.\nUsage: /adjustscore <amount> [reason]"
    ADJUSTSCORE_USAGE_FULL = "❌ <b>Invalid command format.</b>\nUsage:\n1. Reply to user: /adjustscore <amount> [reason]\n2. Specify user: /adjustscore <user_id or @username> <amount> [reason]"
    CHECKSCORE_USAGE = "❌ <b>Invalid command format.</b>\nUsage:\n1. Reply to user: /checkscore\n2. Specify user: /checkscore <user_id or @username>"
    
    # Admin-related messages
    FAILED_REFRESH_ADMIN_LIST = "❌ Failed to refresh admin list. Please try again later."
    SUPER_ADMIN_ONLY = "⚠️ This command is only available to <b>super admins</b>."
    ADMIN_ID_MUST_BE_NUMBER = "❌ <b>Admin ID must be a number.</b>"
    ADMIN_ONLY_COMMAND = "⚠️ This command is only available to <b>admins</b>."
    ONLY_ADMINS_CAN_USE = "⚠️ This command is only available to <b>admins</b>."
    NO_ACTIVE_GAME = "❌ <b>No active game found.</b>"
    STARTING_NEW_GAME = "🎲 <b>Starting a new dice game...</b>"
    
    # Referral messages
    REFERRAL_LINK_MESSAGE = "🎮 <b>Join Rangoon Dice Official group!</b> 🎮\n\n🚀  <b>Your Rewards:</b> User တစ်ယောက် join ရင်{bonus}ကျပ်ရပါမယ်!\n🎁 <b>Their Welcome Gift:</b> Join တာနဲ့ 500ကျပ်ရပါမယ်!\n\n{referral_link}\n\n🏆 <b>Your Referral Empire:</b> {points} ကျပ် earned so far"
    REFERRAL_HEADER = "🎮 <b>Join Rangoon Dice Official group!</b> 🎮\n\n"
    REFERRAL_REWARDS = "🚀 <b>Your Rewards:</b> User တစ်ယောက် join ရင်500ကျပ်ရပါမယ်!\n"
    REFERRAL_WELCOME_GIFT = "🎁 <b>Their Welcome Gift:</b> Join တာနဲ့ 500ကျပ်ရပါမယ်!\n\n"
    REFERRAL_EMPIRE = "🏆 <b>Your Referral Empire:</b> {points} ကျပ် earned so far"
    NEW_MEMBER_WELCOME = "👋 Welcome to the group, {name}!\n\nUse /help to learn how to play the dice game."
    NEW_MEMBER_WELCOME_GAME = "🎮 Welcome {name}! Ready to play and win big! 🎲💰"
    
    # Help message
    HELP_MESSAGE = (
        "🎲 <b>RGN Dice Bot Help</b> 🎲\n\n"
        
        "🎯 <b>GAME RULES</b>\n"
        "🎲 အံစာ ၂ ခုလှိမ့်ပါမယ် ၂ ခုပေါင်းခြင်းကိုခန့်မှန်းရမှာပါ\n"
        "🔸 ပေါင်းခြင်း 2-6: <b>SMALL</b> (1.95x payout)\n"
        "🔸 ပေါင်းခြင်း 8-12: <b>BIG</b> (1.95x payout)\n"
        "🔸 ပေါင်းခြင်း 7: <b>LUCKY</b> (4.5x payout)\n\n"
        
        "💰 <b>ကစားနည်း</b>\n"
        "🔹 <b>BIG:</b> <code>B 500</code> ဒါမှမဟုတ် <code>BIG 1000</code> လို့ရိုက်ပါ\n"
        "🔹 <b>SMALL:</b> <code>S 500</code> ဒါမှမဟုတ် <code>SMALL 1000</code> လို့ရိုက်ပါ\n"
        "🔹 <b>LUCKY:</b> <code>L 500</code> ဒါမှမဟုတ် <code>LUCKY 1000</code> လို့ရိုက်ပါ\n"
        "🔹 Minimum bet: <b>100 ကျပ်</b>\n\n"
        
        "📋 <b>IMPORTANT RULES</b>\n"
        "• 🙅‍♀️ လောင်းပြီးသားကို cancel လို့မရပါဘူး\n"
        "• 👑 Admin တွေကပဲ game ကိုစလို့ရပါတယ်\n"
        
        
        "🎁 <b>REFERRAL SYSTEM</b>\n"
        "• 📤 Link ကို share ပြီး user join ရင် 500 ရပါမယ်\n"
        "• 🎉 Users အသစ်တွေက ဝင်တာနဲ့ တစ်ယောက်ကို 500 စီရမှာပါ\n"
        "• 💡 Referral သုံးဖို့ main wallet အနည်းဆုံး 500 ရှိဖို့လိုပါတယ်\n"
        "• 💵 Wallet တစ်ဝက် referrral တစ်ဝက်ဖျက်မှာပါ\n"
        "• 💵 Wallet က referral ထက်နည်းနေရင် referral ထဲကပဲနှုတ်မှာပါ\n\n"
        
        "🚀 <b>Ready to play? Wait for the next game!</b>"
    )
    
    # Admin score adjustment messages
    SCORE_ADDED = "✅ <b>{display_name}</b> ကို <b>{amount}</b> ကျပ် ဖြည့်ပြီးပါပြီ .\nOld score: <b>{old_score}</b>\nNew score: <b>{new_score}</b>{reason_text}"
    SCORE_DEDUCTED = "✅ <b>{display_name}</b> ကို <b>{amount}</b> ကျပ် နှုတ်ပြီးပါပြီ .\nOld score: <b>{old_score}</b>\nNew score: <b>{new_score}</b>{reason_text}"
    
    # User information display
    USER_INFO_HEADER = "👤 <b>User Information</b>\n\n"
    USER_INFO_USER = "<b>User:</b> {display_name}\n"
    USER_INFO_USER_ID = "<b>User ID:</b> {user_id}\n\n"
    USER_INFO_CHAT_SCORE = "<b>Wallet:</b> {score} ကျပ်\n"
    USER_INFO_WINS = "<b>Wins:</b> {wins}\n"
    USER_INFO_LOSSES = "<b>Losses:</b> {losses}\n"
    USER_INFO_REFERRAL_POINTS = "🎁 <b>Referral ကျပ်:</b> {referral_points} ကျပ်\n"
    USER_INFO_REFERRED_BY = "👤 <b>Referred By:</b> {referrer_name} ({referrer_id})\n"
    
    # Admin wallet messages
    ADMIN_WALLETS_HEADER = "💰 <b>Admin Wallets</b>\n\n"
    ADMIN_WALLET_ENTRY = "👤 <b>{username}</b>\n<b>Balance:</b> {points:,} ကျပ်\n<b>Last Refill:</b> {last_refill}\n\n"
    ADMIN_WALLET_SELF = "👤 <b>{username}</b>\n<b>Balance:</b> {points:,} ကျပ်\n<b>Last Refill:</b> {last_refill}\n"
    NO_ADMIN_WALLET = "You don't have an admin wallet yet.\n"
    NO_ADMIN_WALLETS_FOUND = "No admin wallets found for current admins in this chat.\n"
    
    # Admin refill messages
    ADMIN_NOT_FOUND = "❌ Admin {admin_id} not found."
    ADMIN_REFILLED = "✅ Refilled <b>{username}</b>'s balance to <b>{points}</b> ကျပ်."
    ALL_ADMINS_REFILLED = "✅ Refilled <b>{count}</b> admin wallets to <b>{points}</b> ကျပ် each."
    ADMIN_LIST_REFRESHED = "✅ Admin list refreshed. <b>{count}</b> admins found."
    
    # Score adjustment fallback messages
    SCORE_ADJUSTMENT_FALLBACK = "Score adjusted: {old_score} → {new_score}"
    
    # Error messages for admin/super admin access
    SUPER_ADMIN_ONLY_COMMAND = "⚠️ This command is only available to <b>super admins</b>."
    ADMIN_ONLY_FEATURE = "⚠️ This feature is only available to <b>admins</b>."
    SUPER_ADMIN_ONLY_FEATURE = "⚠️ This feature is only available to <b>super admins</b>."
    
    # Refill system messages
    NO_ACTIVE_GROUPS = "❌ No active groups found."
    INVALID_GROUP_SELECTION = "❌ Invalid group selection."
    NO_ADMINS_IN_GROUP = "❌ No admins found in the selected group."
    ERROR_PROCESSING_GROUP = "❌ Error processing group selection."
    INVALID_CALLBACK_DATA = "❌ Invalid callback data for admin refill."
    ERROR_PROCESSING_REFILL = "❌ Error processing refill action."
    ERROR_PROCESSING_CUSTOM_AMOUNT = "❌ Error processing custom amount request."
    NO_ACTIVE_REFILL_REQUEST = "❌ No active refill request. Please use /refill first."
    PROVIDE_AMOUNT_EXAMPLE = "❌ Please provide an amount. Example: /refill_amount 5000000"
    AMOUNT_MUST_BE_POSITIVE = "❌ Amount must be a positive number."
    AMOUNT_EXCEEDS_LIMIT = "❌ Amount cannot exceed 50,000,000 ကျပ်."
    INVALID_AMOUNT_NUMBER = "❌ Invalid amount. Please enter a valid number."
    ERROR_PROCESSING_REFILL_AMOUNT = "❌ Error processing refill amount."
    ADMINS_CANNOT_REFILL_ADMINS = "❌ Admins cannot refill other admins' balance. Only super admins can do this."
    
    # Removed admin panel messages - using unified system
    
    # Game callback messages
    CHAT_NOT_AUTHORIZED = "This chat is not authorized to use this bot."
    GAME_ALREADY_IN_PROGRESS_CALLBACK = "A game is already in progress. Please finish the current game first."
    FAILED_CREATE_GAME = "Failed to create a new game. Please try again."
    FAILED_CREATE_STATUS_MESSAGE = "Failed to create game status message. Please try again."
    NEW_GAME_CREATED = "New game created!"
    FAILED_UPDATE_GAME_STATUS = "Failed to update game status. Please try again."
    UNEXPECTED_ERROR = "An unexpected error occurred. Please try again."
    
    # Bet callback messages
    INFO_ABOUT_BETTING = "Info about {info_type} betting"
    INVALID_BET_FORMAT = "Invalid bet format"
    BET_PLACED_SUCCESS = "လောင်းကြေးထပ်လိုက်ပါပြီ!"
    NO_ACTIVE_GAME_CALLBACK = "No active game found"
    CRITICAL_ERROR_FALLBACK = "Critical error: {error}"
    
    # Super admin messages
    NO_PERMISSION_COMMAND = "❌ You don't have permission to use this command."
    PRIVATE_CHAT_ONLY = "❌ This command can only be used in private chat with the bot."
    NO_GROUPS_CONFIGURED = "❌ No groups are configured."
    NO_PERMISSION_FEATURE = "❌ You don't have permission to use this feature."
    NO_ADMINS_FOUND = "❌ <b>No Admins Found</b>\n\n"
    ERROR_LOADING_ADMIN_LIST = "❌ Error loading admin list. Please try again."
    
    # Admin refill messages
    ADMIN_REFILL_SUCCESS = "✅ <b>Admin Wallet Refilled!</b>\n\n💰 <b>Amount:</b> {amount} ကျပ်\n👤 <b>Admin:</b> {admin_name}\n🆔 <b>Admin ID:</b> {admin_id}\n\n<b>New Balance:</b> {new_balance} ကျပ်"


def format_game_status(game_status: Dict[str, Any], time_remaining: Optional[int] = None) -> str:
    """
    Formats a game status message with current state and betting instructions.
    """
    try:
        match_id = game_status.get('match_id', 0)
        state = game_status.get('state', '')
        result = game_status.get('result')
        
        message = MessageTemplates.GAME_STARTED.format(match_id=match_id) + "\n\n"
        
        # Add state-specific information
        if state == GAME_STATE_WAITING:
            if time_remaining is not None and time_remaining > 0:
                message += MessageTemplates.TIME_REMAINING.format(seconds=time_remaining) + "\n\n"
            else:
                message += MessageTemplates.CLOSING_SOON + "\n\n"
        elif state == GAME_STATE_CLOSED:
            message += MessageTemplates.BETTING_CLOSED + "\n\n"
        elif state == GAME_STATE_OVER and result is not None:
            message += MessageTemplates.GAME_OVER.format(result=result) + "\n\n"
        
        # Add betting instructions
        message += MessageTemplates.BETTING_PAYOUT
        
        return message
    except Exception as e:
        logger.error(f"Error formatting game status message: {str(e)}")
        return MessageTemplates.GENERAL_ERROR.format(message=str(e))


def get_parse_mode_for_message(message: str) -> str:
    """Determine the appropriate parse mode for a message based on its content."""
    if '<b>' in message or '<i>' in message or '<code>' in message or '<pre>' in message:
        return "HTML"
    else:
        return "Markdown"

async def format_bet_confirmation(bet_type: str, amount: int, result_message: str, username: str = "User", referral_points: int = 0, bonus_points: int = 0, user_id: str = None, game = None, global_data = None, context = None) -> str:
    """
    Formats a bet confirmation message.
    
    Args:
        bet_type: The type of bet (BIG, SMALL, LUCKY)
        amount: The amount bet
        result_message: The result message from process_bet (contains score info)
        username: The username of the player
        referral_points: Optional referral points used (default 0)
        bonus_points: Optional bonus points used (default 0)
        user_id: The user ID to get proper display name and total bets
        game: The current game object to get user's total bets
        global_data: Global data to get user information
    """
    # Get current wallet balance from global_data instead of parsing result_message
    score = 0
    if global_data and user_id:
        user_data = global_data.get("global_user_data", {}).get(str(user_id), {})
        # Get the current score from player_stats in chat_data
        chat_data = global_data.get("chat_data", {})
        player_stats = chat_data.get("player_stats", {})
        user_stats = player_stats.get(str(user_id), {})
        score = user_stats.get("score", 0)
    
    # Fallback: Extract score from result_message if global_data approach fails
    if score == 0 and "Your balance:" in result_message:
        try:
            # Extract the main score from "Your balance: {score} main, {referral} referral, {bonus} bonus ကျပ်"
            balance_part = result_message.split("Your balance:")[1].strip()
            score = int(balance_part.split(" main")[0])
        except (IndexError, ValueError):
            pass
    
    # Get proper display name using get_user_display_name
    display_name = escape_html(username)  # Default fallback
    if context and user_id:
        try:
            from utils.user_utils import get_user_display_name
            display_name = await get_user_display_name(context, int(user_id))
            # If it's a fallback user (User {ID} format), use the original username
            if display_name.startswith('User ') and display_name.endswith(str(user_id)):
                display_name = escape_html(username)
        except Exception:
            # Fallback to escaped username if get_user_display_name fails
            display_name = escape_html(username)
    
    # Get user's total bets display
    total_bets_display = ""
    if game and user_id:
        user_bets = []
        for bet_type_key, bets in game.bets.items():
            if user_id in bets:
                bet_amount = bets[user_id]
                if bet_type_key == "BIG":
                    user_bets.append(f"🎲 B {bet_amount} ကျပ်")
                elif bet_type_key == "SMALL":
                     user_bets.append(f"🎯 S {bet_amount} ကျပ်")
                elif bet_type_key == "LUCKY":
                    user_bets.append(f"🍀 L {bet_amount} ကျပ်")
        
        if user_bets:
            total_bets_display = "\n".join(user_bets)
        else:
            total_bets_display = f"🎲 {bet_type} {amount} ကျပ်"
    else:
        total_bets_display = f"🎲 {bet_type} {amount} ကျပ်"
    
    # Use HTML formatting for consistency
    message = f"✅ {display_name} <b>{bet_type}</b> ပေါ် <b>{amount}</b> လောင်းကြေးထပ်လိုက်ပါပြီ\n\n"
    message += f"📊 <b>Total Bets:</b>\n{total_bets_display}\n\n"
    message += f"💰 <b>Wallet</b> - <b>{score}</b> ကျပ်\n"
    message += f"🎁 <b>Referral</b> - <b>{referral_points}</b> ကျပ်\n"
    message += f"🎉 <b>Bonus</b> - <b>{bonus_points}</b> ကျပ်"
    return message


def format_insufficient_funds(score: int, referral_points: int, bonus_points: int, amount: int, committed_funds: int = 0) -> str:
    """
    Formats an insufficient funds message.
    """
    total = score + referral_points + bonus_points - committed_funds
    shortfall = amount - total
    message = MessageTemplates.INSUFFICIENT_FUNDS.format(
        total=total,
        shortfall=shortfall
    )
    if committed_funds > 0:
        message += f"\n🎯 <b>Already committed:</b> {committed_funds} ကျပ်"
    return message


def format_bet_error(error_message: str) -> str:
    """
    Formats a bet error message.
    """
    return MessageTemplates.GENERAL_ERROR.format(message=error_message)


async def format_participants_list(game, chat_data, global_data=None, context=None) -> str:
    """
    Formats a participants list with their bets.
    """
    participants_details = []
    participant_count = 0
    
    if "player_stats" in chat_data:
        for user_id_str in game.participants:
            if user_id_str in chat_data["player_stats"]:
                # Get display name using get_user_display_name
                display_name = None
                if context:
                    try:
                        from utils.user_utils import get_user_display_name
                        display_name = await get_user_display_name(context, int(user_id_str))
                        # Skip fallback users (User {ID} format)
                        if display_name.startswith('User ') and display_name.endswith(str(user_id_str)):
                            display_name = None
                    except Exception:
                        display_name = None
                
                # Only process if we have a valid display name (skip non-existent users)
                if display_name:
                    # Get user's bets
                    user_bets = []
                    for bet_type, bets in game.bets.items():
                        if user_id_str in bets:
                            bet_amount = bets[user_id_str]
                            if bet_type == "BIG":
                                user_bets.append(f"B {bet_amount}")
                            elif bet_type == "SMALL":
                                user_bets.append(f"S {bet_amount}")
                            elif bet_type == "LUCKY":
                                user_bets.append(f"L {bet_amount}")
                    
                    if user_bets:
                        bet_details = ", ".join(user_bets)
                        participants_details.append(f"<b>{display_name}</b> - {bet_details}")
                        participant_count += 1
    
    if participants_details:
        return MessageTemplates.PARTICIPANTS_HEADER.format(count=participant_count) + "\n" + "\n".join(participants_details)
    else:
        return MessageTemplates.NO_PARTICIPANTS


def format_betting_closed_message(participants_msg: str, roll_delay: int) -> str:
    """
    Formats the betting closed message with participants.
    """
    return MessageTemplates.BETTING_CLOSED_WITH_PARTICIPANTS.format(
        participants_msg=participants_msg,
        roll_delay=roll_delay
    )


def format_dice_animation_failed(result: str) -> str:
    """
    Formats the dice animation failed message.
    """
    return MessageTemplates.DICE_ANIMATION_FAILED.format(result=result)


def format_dice_result(dice1: int, dice2: int, dice_sum: int) -> str:
    """
    Formats a dice roll result message with dice emoji representations.
    """
    # Use simple string representations since actual dice animation is handled by Telegram
    dice1_str = str(dice1)
    dice2_str = str(dice2)
    
    # Determine the result type based on the dice sum
    result_type = "BIG" if dice_sum >= 8 and dice_sum <= 12 else "SMALL" if dice_sum >= 2 and dice_sum <= 6 else "LUCKY"
    
    return f"🎲 <b>Rolled Dices</b> 🎲\n\n🎯 <b>first dice rolled: {dice1_str} + second dice rolled: {dice2_str} = {dice_sum}</b>\n🏆 <b>Result: {result_type}</b>"


async def format_game_summary(result: Dict[str, Any], global_data: Dict[str, Any] = None, context=None) -> str:
    """
    Formats a game summary message.
    """
    # This is an alias for format_game_result to maintain backward compatibility
    return await format_game_result(result, global_data, context)


def format_wallet(player_stats: Dict[str, Any], global_user_data: Dict[str, Any], user_id: Optional[int] = None) -> str:
    """
    Formats a wallet message showing a user's points.
    """
    # Get user's full name and username
    full_name = global_user_data.get('full_name', 'Unknown')
    username = global_user_data.get('username')
    
    # Format display name as "Name(@username)" if username exists, otherwise just "Name"
    if full_name and username and username.strip():
        display_name = f"{escape_html(full_name)}(@{escape_html(username)})"
    else:
        display_name = escape_html(full_name or "Unknown User")
    
    score = player_stats.get('score', 0)
    referral_points = global_user_data.get('referral_points', 0)
    bonus_points = global_user_data.get('bonus_points', 0)
    total = score + referral_points + bonus_points
    
    # Use HTML formatting instead of Markdown with emojis and ကျပ်
    message = f"💰 <b>{display_name}'s Wallet</b>\n\n"
    message += f"💵 <b>Main Balance:</b> {score} ကျပ်\n"
    message += f"🎁 <b>Referral Points:</b> {referral_points} ကျပ်\n"
    message += f"🎉 <b>Bonus Points:</b> {bonus_points} ကျပ်\n"
    message += f"📊 <b>Total Balance:</b> {total} ကျပ်"
    
    return message


async def format_game_result(result: Dict[str, Any], global_data: Dict[str, Any] = None, context=None) -> str:
    """
    Formats a game result message with dice emoji representations.
    """
    # Use simple string representations since actual dice animation is handled by Telegram
    dice_result = result.get('dice_result')
    dice1, dice2 = result.get('dice_values', (0, 0))
    dice_sum = dice1 + dice2 if dice1 and dice2 else 0
    winning_type = result.get('winning_type', '').upper()
    winners = result.get('winners', [])
    losers = result.get('losers', [])
    multiplier = result.get('multiplier', 0)
    
    # Use simple string representations
    dice1_str = str(dice1)
    dice2_str = str(dice2)
    
    message = "🎲 <b>Rolled Dices</b> 🎲\n\n"
    message += f"🎯 <b>{dice1_str} + {dice2_str} = {dice_sum}</b>\n"
    message += f"🏆 <b>Result: {winning_type}</b> (x<b>{multiplier}</b>)\n\n"
    
    message += "💰 <b>Payouts:</b>\n"
    
    # Process participants and show their individual bet results
    
    # Check if there are any participants
    if not winners and not losers:
        total_bets = result.get('total_bets', 0)
        message += "<b>No winner in this match</b>\n"
        message += f"\n💵 <b>Total:</b> {total_bets} ကျပ် bet, 0 ကျပ် paid out\n"
    else:
        # Show all participants with individual bet details
        participant_count = 0
        
        # Process winners first
        for winner in winners:
            if participant_count >= 10:  # Limit to 10 participants
                break
                
            user_id = winner.get('user_id')
            display_name = None
            if user_id and context:
                from utils.user_utils import get_user_display_name
                display_name = await get_user_display_name(context, user_id)
                # Skip fallback users (User {ID} format)
                if display_name.startswith('User ') and display_name.endswith(str(user_id)):
                    display_name = None
            
            if display_name:
                wallet_balance = winner.get('wallet_balance', 'N/A')
                individual_bets = winner.get('individual_bets', [])
                
                # Show individual bet results
                bet_details = []
                for bet in individual_bets:
                    bet_type = bet['bet_type']
                    amount = bet['amount']
                    if bet['result'] == 'win':
                        bet_details.append(f"+{bet['payout']} ကျပ် ({bet_type.lower()})")
                    else:
                        bet_details.append(f"-{amount} ကျပ် ({bet_type.lower()})")
                
                bet_summary = ", ".join(bet_details)
                message += f"🎉 <b>{display_name}:</b> {bet_summary} (<b>💰 Wallet:</b> {wallet_balance} ကျပ်)\n"
                participant_count += 1
        
        # Process losers
        for loser in losers:
            if participant_count >= 10:  # Limit to 10 participants
                break
                
            user_id = loser.get('user_id')
            display_name = None
            if user_id and context:
                from utils.user_utils import get_user_display_name
                display_name = await get_user_display_name(context, user_id)
                # Skip fallback users (User {ID} format)
                if display_name.startswith('User ') and display_name.endswith(str(user_id)):
                    display_name = None
            
            if display_name:
                wallet_balance = loser.get('wallet_balance', 'N/A')
                individual_bets = loser.get('individual_bets', [])
                
                # Show individual bet results
                bet_details = []
                for bet in individual_bets:
                    bet_type = bet['bet_type']
                    amount = bet['amount']
                    if bet['result'] == 'win':
                        bet_details.append(f"+{bet['payout']} ကျပ် ({bet_type.lower()})")
                    else:
                        bet_details.append(f"-{amount} ကျပ် ({bet_type.lower()})")
                
                bet_summary = ", ".join(bet_details)
                message += f"😞 <b>{display_name}:</b> {bet_summary} (<b>💰 Wallet:</b> {wallet_balance} ကျပ်)\n"
                participant_count += 1

        total_participants = len(winners) + len(losers)
        if total_participants > 10:
            message += f"...and <b>{total_participants - 10} more participants</b>\n"

        # Show totals
        total_payout = result.get('total_payout', 0)
        total_bets = result.get('total_bets', 0)
        message += f"\n💵 <b>Total:</b> {total_bets} ကျပ် bet, {total_payout} ကျပ် paid out\n"
    
    return message


async def format_leaderboard(chat_data: Dict[str, Any], context: Any, title: str = "🏆 Leaderboard", global_data: Dict[str, Any] = None) -> str:
    """
    Formats a leaderboard message with player rankings.
    """
    if not chat_data or 'player_stats' not in chat_data:
        return f"<b>{title}</b>\n\nNo players found."
    
    player_stats = chat_data.get('player_stats', {})
    if not player_stats:
        return f"<b>{title}</b>\n\nNo players found."
    
    # Convert player_stats dictionary to a list of player dictionaries
    players = []
    for user_id, stats in player_stats.items():
        if isinstance(stats, dict):
            player = {
                'user_id': user_id,
                'score': stats.get('score', 0),
                'username': stats.get('username', 'Unknown')
            }
            players.append(player)
    
    if not players:
        return f"<b>{title}</b>\n\nNo players found."
    
    # Sort players by score in descending order
    sorted_players = sorted(players, key=lambda x: x.get('score', 0), reverse=True)
    
    # Format the leaderboard message
    message = f"<b>{title}</b>\n\n"
    valid_players = []
    
    for player in sorted_players[:20]:  # Check top 20 to get 10 valid ones
        user_id = player.get('user_id')
        display_name = None
        
        # Get proper display name using get_user_display_name
        if user_id and context:
            from utils.user_utils import get_user_display_name
            display_name = await get_user_display_name(context, int(user_id))
            # Skip fallback users (User {ID} format)
            if display_name.startswith('User ') and display_name.endswith(str(user_id)):
                display_name = None
        
        # Only add if we have a valid display name (skip non-existent users)
        if display_name:
            valid_players.append({
                'display_name': display_name,
                'score': player.get('score', 0)
            })
            
            # Stop when we have 10 valid players
            if len(valid_players) >= 10:
                break
    
    if not valid_players:
        return f"<b>{title}</b>\n\nNo valid players found."
    
    for i, player in enumerate(valid_players, 1):
        # Add ranking emojis
        if i == 1:
            rank_emoji = "🥇"
        elif i == 2:
            rank_emoji = "🥈"
        elif i == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = "🏅"
        message += f"{rank_emoji} <b>{i}.</b> <b>{player['display_name']}:</b> <b>{player['score']}</b> ကျပ်\n"
    
    return message


def format_game_history(history):
    """
    Formats a game history message with enhanced dynamic UI.
    Shows latest 5 matches with detailed statistics and visual appeal.
    """
    if not history:
        return "🎮 <b>Game History Dashboard</b> 🎮\n\n🎲 <b>No epic battles have been fought yet!</b>\n\n🚀 <b>Ready to make history? Start your first game now!</b>"
    
    from datetime import datetime
    import pytz
    from config.settings import TIMEZONE
    
    # Get current time in the configured timezone
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%m/%d")
    current_time = now.strftime("%H:%M")
    
    total_games = len(history)
    latest_games = history[-5:]
    
    # Calculate overall statistics
    total_winnings = sum(game.get('total_won', 0) for game in history)
    total_losses = sum(game.get('total_lost', 0) for game in history)
    net_result = total_winnings - total_losses
    
    # Header with statistics
    message = "🎮 <b>Game History Dashboard</b> 🎮\n"
    message += "╔═══════════════════════════╗\n"
    message += f"║  📊 Total Games: <b>{total_games}</b>\n"
    message += f"║  💎 Net Result: <b>{'+' if net_result >= 0 else ''}{net_result:,}</b>\n"
    message += f"║  🕐 Last Updated: <b>{current_time}</b>\n"
    message += "╚═══════════════════════════╝\n\n"
    
    message += "🏆 <b>Recent Battle Results</b> 🏆\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, game in enumerate(reversed(latest_games), 1):
        dice_result = game.get('dice_result', 'N/A')
        winning_type = game.get('winning_type', '').upper()
        total_won = game.get('total_won', 0)
        total_lost = game.get('total_lost', 0)
        timestamp = game.get('timestamp', '')
        
        # Parse timestamp for better display
        try:
            if timestamp:
                game_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                game_time = game_time.astimezone(tz)
                time_str = game_time.strftime("%H:%M")
            else:
                time_str = "--:--"
        except:
            time_str = "--:--"
        
        # Calculate result and choose appropriate styling
        result = total_won - total_lost
        if result > 0:
            result_str = f"+{result:,}"
            result_emoji = "🟢"
            status_emoji = "🎉"
        elif result < 0:
            result_str = f"{result:,}"
            result_emoji = "🎲"
            status_emoji = "😤"
        else:
            result_str = "±0"
            result_emoji = "🟡"
            status_emoji = "😐"
        
        # Choose dice emoji based on result
        if isinstance(dice_result, tuple) and len(dice_result) == 2:
            dice_display = f"🎲 {dice_result[0]}•{dice_result[1]}"
        else:
            dice_display = f"🎲 {dice_result}"
        
        # Choose winning type emoji
        type_emojis = {
            'BIG': '🔥',
            'SMALL': '❄️',
            'LUCKY': '⭐'
        }
        type_emoji = type_emojis.get(winning_type, '🎯')
        
        # Use the actual match_id from the game data
        match_id = game.get('match_id', total_games - len(latest_games) + len(latest_games) - i + 1)
        message += f"{status_emoji} <b>Round #{match_id}</b>\n"
        message += f"┣ {dice_display} → {type_emoji} <b>{winning_type}</b>\n"
        message += f"┣ {result_emoji} <b>{result_str}</b> ကျပ်\n"
        message += f"┗ 🕐 {time_str} • {today}\n\n"
    
    if total_games > 5:
        message += f"📈 <b>Showing latest 5 of {total_games} total games</b>\n"
        message += "💡 <b>Tip: Keep playing to climb the leaderboard!</b>"
    
    return message


# The format_wallet function is already defined above