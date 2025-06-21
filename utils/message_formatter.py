import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Union

from config.constants import RESULT_EMOJIS, GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER
from utils.formatting import escape_markdown

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
    GAME_STARTED = "🎲*ပွဲစဉ်#{match_id} - လောင်းကြေးဖွင့်ပါပြီ*🎲"
    BETTING_CLOSED = "🎲  လောင်းကြေးပိတ်ပါပြီ  🎲"
    GAME_OVER = "🏁 *Game over*\nResult: {result}"
    TIME_REMAINING = "⏱️ *စတင်မည့်အချိန်:* {seconds}s"
    CLOSING_SOON = "⏱️ *Closing soon...*"
    
    # Betting instructions
    BETTING_INSTRUCTIONS = (
        "*လောင်းကြေးထပ်ရန်*\n"
"🔴 *BIG (8-12):* *B 500* or *BIG 500* လို့ရိုက်ပါ\n"
"⚫ *SMALL (2-6):* *S 500* or *SMALL 500* လို့ရိုက်ပါ\n"
"🍀 *LUCKY (7):* *L 500* or *LUCKY 500* လို့ရိုက်ပါ\n\n"
"💰 *လျော်မည့်ဆ:*\n"
        "- *BIG/SMALL:* *2x*\n"
        "- *LUCKY:* *5x*"
    )
    
    # Bet confirmation
    BET_CONFIRMATION = "✅ {display_name} *{bet_type}* ပေါ် *{amount}* လောင်းကြေးထပ်လိုက်ပါပြီ\n\n📊 *Total Bets:*\n{total_bets_display}\n\n💰 *Wallet* - *{score}* ကျပ်\n🎁 *Referral* - *{referral_points}* ကျပ်"
    INSUFFICIENT_FUNDS = "❌ သင့်တွင် *လုံလောက်သော ငွေမရှိပါ*။ 💰*Wallet:* {score} + *{referral_points}* referral points = *{total}*"
    INVALID_BET_AMOUNT = "❌ *ငွေပမာဏ အနည်းဆုံး 1 ဖြစ်ရပါမည်*။"
    NO_ACTIVE_GAME = "❌ *No active game* is accepting bets right now."
    
    # Error messages
    GENERAL_ERROR = "❌ *Error:* {message}"
    CHAT_NOT_ALLOWED = "⚠️ This bot is only available in *authorized groups*.\nPlease join our *official group:* {group_link}"
    ADMIN_ONLY = "⚠️ This command is only available to *admins*."
    
    # User messages
    WALLET_HEADER = "💰 *{name}'s Wallet*\n\n"
    WALLET_MAIN_BALANCE = "*💵 Main Balance:* {score} ကျပ်\n"
    WALLET_REFERRAL_BONUS = "*🎁 Referral Bonus:* {referral_points} ကျပ်\n"
    WALLET_TOTAL_BALANCE = "*📊 Total Balance:* {total} ကျပ်"
    
    # Game result
    GAME_RESULT_HEADER = "🎲 *Game Result*\n"
    GAME_RESULT_ROLL = "Roll: *{dice_result}* | Winner: {emoji} *{winning_type}*\n"
    WINNERS_HEADER = "*Winners:*\n"
    NO_WINNERS = "*No winners this round*\n"
    WINNER_ENTRY = "- {username}: Bet *{bet_amount}*, Won *{winnings}*\n"
    MORE_WINNERS = "...and {count} more\n"
    TOTAL_SUMMARY = "Total: Won *{total_won}* | Lost *{total_lost}*"
    
    # Game management messages
    GAME_STOPPED_INACTIVITY = "🛑 *3 ပွဲဆက်တိုက်ဆော့မယ့်သူမရှိလို့ ရပ်လိုက်ပါပြီ.*\n\n*Contact admins* to start new game:\n{admin_list}"
    BETTING_CLOSED_WITH_PARTICIPANTS = "⏱ *လောင်းကြေးပိတ်ပါပြီ!*\n\n{participants_msg}\n\n*Rolling dice* in *{roll_delay} seconds*..."
    PARTICIPANTS_HEADER = "*Participants({count})*"
    NO_PARTICIPANTS = "*Participants(0)*\n*No participants*"
    DICE_ANIMATION_FAILED = "⚠️ *Dice animation failed*, using *manual roll*\n\n{result}"
    
    # Admin messages
    GAME_STOPPED_BY_ADMIN = "🛑 *Game stopped* by admin."
    GAME_STOPPED_WITH_REFUNDS = "🛑 *Game stopped* by admin. 💰 *All bets* have been *refunded*."
    NO_GAME_IN_PROGRESS = "❌ *No game* is currently in progress."
    GAME_ALREADY_IN_PROGRESS = "❌ A *game is already in progress*. Please *finish the current game* first."
    STARTING_NEW_GAME = "🎲 *Starting a new dice game*..."
    FAILED_GAME_CREATION = "❌ Error: Failed to create a new game. Please try again."
    
    # User welcome messages
    WELCOME_WITH_REFERRAL = "👋 *Welcome to Rangoon Dice Bot, {name}!*\n\n{message}\n\n!"
    WELCOME_STANDARD = "👋 *Welcome to RGN Dice Bot, {name}!*\n\nGroup ထဲဝင်ဖို့ အောက်ကခလုတ်လေးကို နှိပ်ပြီး စဆော့လို့ရပါပြီနော်!"
    WELCOME_WITH_REFERRAL_LINK = "👋 *Welcome to RGN Dice Bot, {name}!*\n\nGroup ထဲဝင်ဖို့ အောက်ကခလုတ်လေးကို နှိပ်ပြီး စဆော့လို့ရပါပြီနော်\n\n🎁 *Invite Friends & Earn Rewards*\nShare your referral link to earn *{bonus} points* for each new player who joins!\n\n📱 *Your Referral Link:*\n`{referral_link}`"
    
    # Deposit and withdrawal messages
    DEPOSIT_MESSAGE = "*ငွေထည့်ရန်*\n\nငွေထည့်ရန် အောက်ပါ Admin များထံ ဆက်သွယ်ပါ။\n\n{admin_list}"
    WITHDRAWAL_MESSAGE = "*ငွေထုတ်ရန်*\n\nငွေထုတ်ရန် အောက်ပါ Admin များထံ ဆက်သွယ်ပါ။\n\n{admin_list}"
    
    # Error messages
    INVALID_COMMAND_FORMAT = "❌ *Invalid command format*\nUsage: {usage}"
    USER_ID_MUST_BE_NUMBER = "❌ *User ID must be a number*"
    AMOUNT_MUST_BE_NUMBER = "❌ Amount must be a number."
    USER_NOT_FOUND_BY_ID = "❌ User with ID {user_id} not found in this chat."
    USER_NOT_FOUND_BY_USERNAME = "❌ User with username {username} not found in this chat."
    INVALID_USER_IDENTIFIER = "❌ Invalid user identifier. Use a user ID or @username."
    FAILED_TO_IDENTIFY_USER = "❌ Failed to identify user. Please try again."
    COULD_NOT_IDENTIFY_USER = "❌ Could not identify target user."
    USER_NOT_IN_RECORDS = "❌ User not found in this chat's records."
    
    # Admin command usage messages
    ADJUSTSCORE_USAGE_REPLY = "❌ Please specify an amount when replying to a user.\nUsage: /adjustscore <amount> [reason]"
    ADJUSTSCORE_USAGE_FULL = "❌ Invalid command format.\nUsage:\n1. Reply to user: /adjustscore <amount> [reason]\n2. Specify user: /adjustscore <user_id or @username> <amount> [reason]"
    CHECKSCORE_USAGE = "❌ Invalid command format.\nUsage:\n1. Reply to user: /checkscore\n2. Specify user: /checkscore <user_id or @username>"
    
    # Admin-related messages
    FAILED_REFRESH_ADMIN_LIST = "❌ Failed to refresh admin list. Please try again later."
    SUPER_ADMIN_ONLY = "⚠️ This command is only available to super admins."
    ADMIN_ID_MUST_BE_NUMBER = "❌ Admin ID must be a number."
    ADMIN_ONLY_COMMAND = "⚠️ This command is only available to admins."
    ONLY_ADMINS_CAN_USE = "❌ Only admins can use this command."
    NO_ACTIVE_GAME = "❌ No active game found."
    STARTING_NEW_GAME = "🎲 Starting a new dice game..."
    
    # Referral messages
    REFERRAL_LINK_MESSAGE = "🎮 *Join Rangoon Dice Official group!* 🎮\n\n🚀 Ready to turn your friends into gaming partners? Share the excitement of RGN Dice Bot and watch the rewards roll in!\n\n💎 *Your Rewards:* User တစ်ယောက် join ရင်{bonus}ကျပ်ရပါမယ်!\n🎁 *Their Welcome Gift:*ကျပ်ရပါမယ်!\n🔥 *Double the Fun:* More friends = More games = More wins for everyone!\n\n✨ *Your Magic Invite Link:*\n{referral_link}\n\n🏆 *Your Referral Empire:* {points} points earned so far\n\n🎯 Ready to build your gaming network? Share now and let the dice decide your fortune!"
    NEW_MEMBER_WELCOME = "👋 Welcome to the group, {name}!\n\nUse /help to learn how to play the dice game."
    
    # Help message
    HELP_MESSAGE = "🎲 *RGN Dice Bot Help* 🎲\n\n*Game rules :*\n• အံစာတုံး ၂ တုံးလှိမ့်ပါမယ်\n• ၂ခု ပေါင်းခြင်း 2-6: *SMALL* \n• ၂ခု ပေါင်းခြင်း 8-12: *BIG* \n• ၂ခု ပေါင်းခြင်း 7: *LUCKY*\n\n*ကစားနည်း :*\n• Big ပေါ်လောင်းရန် B 500, Big 5000 စသဖြင့်လောင်းလို့ရပါတယ်\n• Small ပေါ်လောင်းရန် S 500, Small 2000 စသဖြင့်လောင်းလို့ရပါတယ်\n• LUCKY ပေါ်လောင်းရန် L 5000, LUCKY 50000 စသဖြင့်လောင်းလို့ရပါတယ်\n\n*Rules :*\n• အနည်းဆုံး ၁၀၀ ကျပ်မှစတင်လောင်းလို့ရပါတယ်\n• လောင်းပြီးသားဟာကို cancel လို့မရပါဘူး\n• admin တွေကပဲ game ကိုစတင်လို့ရပါတယ်\n\n*Points:*\n• Big/Small ဆိုရင် 2 ဆရပါမယ်\n• LUCKY ဆိုရင် 5 ဆရပါမယ်\n• Share ခလုတ်လေးနှိပ်ပြီး သူငယ််ချင်းတွေကို ပို့ပေးလို့ရပါတယ် \n• Share ထားတယ့် link ကနေတစ်ဆင့်ဝင်လာရင် ၅၀၀ ကျပ်ရရှိမှာဖြစ်ပါတယ်"
    
    # Admin score adjustment messages
    SCORE_ADDED = "✅ *{display_name}* ကို *{amount}* ကျပ် ဖြည့်ပြီးပါပြီ .\nOld score: *{old_score}*\nNew score: *{new_score}*{reason_text}"
    SCORE_DEDUCTED = "✅ *{display_name}* ကို *{amount}* ကျပ် နှုတ်ပြီးပါပြီ .\nOld score: *{old_score}*\nNew score: *{new_score}*{reason_text}"
    
    # User information display
    USER_INFO_HEADER = "👤 *User Information*\n\n"
    USER_INFO_USER = "*User:* {display_name}\n"
    USER_INFO_USER_ID = "*User ID:* {user_id}\n\n"
    USER_INFO_CHAT_SCORE = "*Wallet:* {score} points\n"
    USER_INFO_WINS = "*Wins:* {wins}\n"
    USER_INFO_LOSSES = "*Losses:* {losses}\n"
    USER_INFO_REFERRAL_POINTS = "🎁 *Referral Points:* {referral_points} points\n"
    USER_INFO_REFERRED_BY = "👤 *Referred By:* {referrer_name} ({referrer_id})\n"
    
    # Admin wallet messages
    ADMIN_WALLETS_HEADER = "💰 *Admin Wallets*\n\n"
    ADMIN_WALLET_ENTRY = "👤 *{username}* ({admin_id})\nPoints: {points}\nLast Refill: {last_refill}\n\n"
    ADMIN_WALLET_SELF = "👤 *{username}* ({admin_id})\nPoints: {points}\nLast Refill: {last_refill}\n"
    NO_ADMIN_WALLET = "You don't have an admin wallet yet.\n"
    NO_ADMIN_WALLETS_FOUND = "No admin wallets found for current admins in this chat.\n"
    
    # Admin refill messages
    ADMIN_NOT_FOUND = "❌ Admin {admin_id} not found."
    ADMIN_REFILLED = "✅ Refilled {username}'s points to {points}."
    ALL_ADMINS_REFILLED = "✅ Refilled {count} admin wallets to {points} points each."
    ADMIN_LIST_REFRESHED = "✅ Admin list refreshed. {count} admins found."
    
    # Score adjustment fallback messages
    SCORE_ADJUSTMENT_FALLBACK = "Score adjusted: {old_score} → {new_score}"


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
        message += MessageTemplates.BETTING_INSTRUCTIONS
        
        return message
    except Exception as e:
        logger.error(f"Error formatting game status message: {str(e)}")
        return MessageTemplates.GENERAL_ERROR.format(message=str(e))


def format_bet_confirmation(bet_type: str, amount: int, result_message: str, username: str = "User", referral_points: int = 0, user_id: str = None, game = None, global_data = None) -> str:
    """
    Formats a bet confirmation message.
    
    Args:
        bet_type: The type of bet (BIG, SMALL, LUCKY)
        amount: The amount bet
        result_message: The result message from process_bet (contains score info)
        username: The username of the player
        referral_points: Optional referral points used (default 0)
        user_id: The user ID to get proper display name and total bets
        game: The current game object to get user's total bets
        global_data: Global data to get user information
    """
    # Extract score from result_message if needed
    score = 0
    if "Your balance:" in result_message:
        try:
            score = int(result_message.split("Your balance:")[1].strip().split()[0])
        except (IndexError, ValueError):
            pass
    
    # Get proper display name
    display_name = username
    if global_data and user_id:
        user_global_data = global_data.get('global_user_data', {}).get(user_id, {})
        full_name = user_global_data.get('full_name', username)
        telegram_username = user_global_data.get('username')
        
        if telegram_username and telegram_username.strip():
            display_name = f"{escape_markdown(full_name)}(@{escape_markdown(telegram_username)})"
        else:
            display_name = escape_markdown(full_name)
    
    # Get user's total bets display
    total_bets_display = ""
    if game and user_id:
        user_bets = []
        for bet_type_key, bets in game.bets.items():
            if user_id in bets:
                bet_amount = bets[user_id]
                if bet_type_key == "BIG":
                    user_bets.append(f"🔴 B {bet_amount} ကျပ်")
                elif bet_type_key == "SMALL":
                    user_bets.append(f"🔵 S {bet_amount} ကျပ်")
                elif bet_type_key == "LUCKY":
                    user_bets.append(f"🍀 L {bet_amount} ကျပ်")
        
        if user_bets:
            total_bets_display = "\n".join(user_bets)
        else:
            total_bets_display = f"🔴 {bet_type} {amount} ကျပ်"
    else:
        total_bets_display = f"🔴 {bet_type} {amount} ကျပ်"
    
    return MessageTemplates.BET_CONFIRMATION.format(
        display_name=display_name,
        amount=amount,
        bet_type=bet_type,
        score=score,
        referral_points=referral_points,
        total_bets_display=total_bets_display
    )


def format_insufficient_funds(score: int, referral_points: int, amount: int) -> str:
    """
    Formats an insufficient funds message.
    """
    total = score + referral_points
    return MessageTemplates.INSUFFICIENT_FUNDS.format(
        score=score,
        referral_points=referral_points,
        total=total
    )


def format_bet_error(error_message: str) -> str:
    """
    Formats a bet error message.
    """
    return MessageTemplates.GENERAL_ERROR.format(message=error_message)


def format_participants_list(game, chat_data, global_data=None) -> str:
    """
    Formats a participants list with their bets.
    """
    participants_details = []
    participant_count = 0
    
    if "player_stats" in chat_data:
        for user_id_str in game.participants:
            if user_id_str in chat_data["player_stats"]:
                # Get display name from global data if available
                display_name = "Unknown"
                if global_data:
                    user_global_data = global_data.get('global_user_data', {}).get(user_id_str, {})
                    full_name = user_global_data.get('full_name', 'Unknown')
                    telegram_username = user_global_data.get('username')
                    
                    if telegram_username and telegram_username.strip():
                        display_name = f"{escape_markdown(full_name)}(@{escape_markdown(telegram_username)})"
                    else:
                        display_name = escape_markdown(full_name)
                else:
                    # Fallback to chat data username
                    username = chat_data["player_stats"][user_id_str].get("username", "Unknown")
                    display_name = escape_markdown(username)
                
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
                    participants_details.append(f"*{display_name}* - {bet_details}")
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
    
    return f"🎲 *Rolled Dices* 🎲\n\n🎯 *first dice rolled: {dice1_str} + second dice rolled: {dice2_str} = {dice_sum}*\n🏆 *Result: {result_type}*"


def format_game_summary(result: Dict[str, Any], global_data: Dict[str, Any] = None) -> str:
    """
    Formats a game summary message.
    """
    # This is an alias for format_game_result to maintain backward compatibility
    return format_game_result(result, global_data)


def format_wallet(player_stats: Dict[str, Any], global_user_data: Dict[str, Any], user_id: Optional[int] = None) -> str:
    """
    Formats a wallet message showing a user's points.
    """
    # Get user's full name and username
    full_name = global_user_data.get('full_name', 'Unknown')
    username = global_user_data.get('username')
    
    # Format display name as "Name(@username)" if username exists, otherwise just "Name"
    if full_name and username and username.strip():
        display_name = f"{escape_markdown(full_name)}(@{escape_markdown(username)})"
    else:
        display_name = escape_markdown(full_name or "Unknown User")
    
    score = player_stats.get('score', 0)
    referral_points = global_user_data.get('referral_points', 0)
    total = score + referral_points
    
    # Use the new format requested by user
    message = f"💰 *{display_name}'s Wallet*\n\n"
    message += f"*Wallet:* {score} points\n"
    message += f"*Referral Points:* {referral_points} points\n"
    message += f"*Total:* {total} points"
    
    return message


def format_game_result(result: Dict[str, Any], global_data: Dict[str, Any] = None) -> str:
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
    
    message = "🎲 *Rolled Dices* 🎲\n\n"
    message += f"🎯 *{dice1_str} + {dice2_str} = {dice_sum}*\n"
    message += f"🏆 *Result: {winning_type}* (x*{multiplier}*)\n\n"
    
    message += "💰 *Payouts:*\n"
    
    # Combine all participants and show their payouts
    all_participants = []
    
    # Add winners with positive amounts
    for winner in winners:
        # Get proper display name
        user_id = winner.get('user_id')
        display_name = "Unknown"
        if user_id and global_data:
            user_global_data = global_data.get('global_user_data', {}).get(str(user_id), {})
            full_name = user_global_data.get('full_name', 'Unknown')
            telegram_username = user_global_data.get('username')
            
            if telegram_username and telegram_username.strip():
                display_name = f"{escape_markdown(full_name)}(@{escape_markdown(telegram_username)})"
            else:
                display_name = escape_markdown(full_name)
        else:
            # Fallback to winner username
            display_name = escape_markdown(winner.get('username', 'Unknown'))
        
        bet_amount = winner.get('bet_amount', 0)
        winnings = winner.get('winnings', 0)
        # Get wallet balance from winner data if available
        wallet_balance = winner.get('wallet_balance', 'N/A')
        all_participants.append({
            'username': display_name,
            'amount': f"+{winnings}",
            'wallet': wallet_balance
        })
    
    # Add losers with negative amounts
    for loser in losers:
        # Get proper display name
        user_id = loser.get('user_id')
        display_name = "Unknown"
        if user_id and global_data:
            user_global_data = global_data.get('global_user_data', {}).get(str(user_id), {})
            full_name = user_global_data.get('full_name', 'Unknown')
            telegram_username = user_global_data.get('username')
            
            if telegram_username and telegram_username.strip():
                display_name = f"{escape_markdown(full_name)}(@{escape_markdown(telegram_username)})"
            else:
                display_name = escape_markdown(full_name)
        else:
            # Fallback to loser username
            display_name = escape_markdown(loser.get('username', 'Unknown'))
        
        bet_amount = loser.get('bet_amount', 0)
        # Get wallet balance from loser data if available
        wallet_balance = loser.get('wallet_balance', 'N/A')
        all_participants.append({
            'username': display_name,
            'amount': f"-{bet_amount}",
            'wallet': wallet_balance
        })
    
    # Check if there are any participants
    if not all_participants:
        message += "*No participants* in this match\n"
    else:
        # Show all participants in the new format
        for participant in all_participants[:10]:  # Limit to 10 participants
            username = participant['username']
            amount = participant['amount']
            wallet = participant['wallet']
            message += f"*{username}:* {amount} (*wallet:* {wallet})\n"

        if len(all_participants) > 10:
            message += f"...and *{len(all_participants) - 10} more participants*\n"

        # Show totals
        total_payout = result.get('total_payout', 0)
        total_bets = result.get('total_bets', 0)
        message += f"\n💵 Total: {total_bets} bet, {total_payout} paid out\n"
    
    return message


def format_leaderboard(chat_data: Dict[str, Any], context: Any, title: str = "🏆 Leaderboard", global_data: Dict[str, Any] = None) -> str:
    """
    Formats a leaderboard message with player rankings.
    """
    if not chat_data or 'player_stats' not in chat_data:
        return f"*{title}*\n\nNo players found."
    
    player_stats = chat_data.get('player_stats', {})
    if not player_stats:
        return f"*{title}*\n\nNo players found."
    
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
        return f"*{title}*\n\nNo players found."
    
    # Sort players by score in descending order
    sorted_players = sorted(players, key=lambda x: x.get('score', 0), reverse=True)
    
    # Format the leaderboard message
    message = f"*{title}*\n\n"
    for i, player in enumerate(sorted_players[:10], 1):  # Show top 10 players
        user_id = player.get('user_id')
        display_name = "Unknown"
        
        # Get proper display name from global_data
        if user_id and global_data:
            user_global_data = global_data.get('global_user_data', {}).get(str(user_id), {})
            full_name = user_global_data.get('full_name', 'Unknown')
            telegram_username = user_global_data.get('username')
            
            if telegram_username and telegram_username.strip():
                display_name = f"{escape_markdown(full_name)}(@{escape_markdown(telegram_username)})"
            else:
                display_name = escape_markdown(full_name)
        else:
            # Fallback to stored username
            username = player.get('username', 'Unknown')
            if isinstance(username, str) and username != 'Unknown':
                display_name = escape_markdown(username)
            else:
                display_name = 'Unknown'
        
        score = player.get('score', 0)
        message += f"*{i}.* *{display_name}:* *{score}* points\n"
    
    return message


def format_game_history(history):
    """
    Formats a game history message with enhanced dynamic UI.
    Shows latest 5 matches with detailed statistics and visual appeal.
    """
    if not history:
        return "🎮 *Game History Dashboard* 🎮\n\n🎲 *No epic battles have been fought yet!*\n\n🚀 *Ready to make history? Start your first game now!*"
    
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
    message = "🎮 *Game History Dashboard* 🎮\n"
    message += "╔═══════════════════════════╗\n"
    message += f"║  📊 Total Games: *{total_games}*\n"
    message += f"║  💎 Net Result: *{'+' if net_result >= 0 else ''}{net_result:,}*\n"
    message += f"║  🕐 Last Updated: *{current_time}*\n"
    message += "╚═══════════════════════════╝\n\n"
    
    message += "🏆 *Recent Battle Results* 🏆\n"
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
            result_emoji = "🔴"
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
        message += f"{status_emoji} *Round #{match_id}*\n"
        message += f"┣ {dice_display} → {type_emoji} *{winning_type}*\n"
        message += f"┣ {result_emoji} *{result_str}* points\n"
        message += f"┗ 🕐 {time_str} • {today}\n\n"
    
    if total_games > 5:
        message += f"📈 *Showing latest 5 of {total_games} total games*\n"
        message += "💡 *Tip: Keep playing to climb the leaderboard!*"
    
    return message


# The format_wallet function is already defined above