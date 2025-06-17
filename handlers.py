import logging
import asyncio
from datetime import datetime, date, timedelta
import random
import re
from typing import Optional
from apscheduler.jobstores.base import JobLookupError
import pytz
import urllib.parse

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember, ChatMemberAdministrator
from telegram.constants import ChatMemberStatus

from game_logic import DiceGame, WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER
from constants import (
    global_data, HARDCODED_ADMINS, SUPER_ADMINS, RESULT_EMOJIS, INITIAL_PLAYER_SCORE,
    ALLOWED_GROUP_IDS, get_chat_data_for_id,
    ADMIN_INITIAL_POINTS, get_admin_data,
    REFERRAL_BONUS_POINTS, MAIN_GAME_GROUP_LINK
)

from file_manager import save_data

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions (Defined first to avoid forward reference issues)
# =============================================================================

def _escape_text_for_markdown(text: str) -> str:
    """
    Escapes characters that have special meaning in plain Markdown
    to ensure they are displayed literally within a message.
    Used for content that should NOT be interpreted as Markdown formatting.
    """
    # Characters commonly needing escaping in plain Markdown:
    # *, _, `, [, ], (, ), #, +, -, ., !
    # This function is specifically for content *within* a message
    # that is already being wrapped in bold.
    # It focuses on preventing accidental formatting of user-provided strings.

    # Order matters: escape backslashes first, then other special characters
    # text = text.replace('\\', '\\\\') # Not strictly needed if we don't have literal backslashes
    special_chars = r'*_`[]()#+-.!' # Escape these if they appear literally
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
# --- END UPDATED ---

async def is_admin(chat_id, user_id, context) -> bool:
    """
    Checks if a user is an administrator in a specific chat
    or if they are one of the hardcoded global administrators.
    """
    is_hardcoded_admin = user_id in HARDCODED_ADMINS
    if is_hardcoded_admin:
        return True

    chat_admins = await get_admins_from_chat(chat_id, context)
    is_chat_admin = user_id in chat_admins

    logger.debug(f"is_admin: Checking admin status for user {user_id} in chat {chat_id}: is_chat_admin={is_chat_admin}, is_hardcoded_admin={is_hardcoded_admin}")
    return is_chat_admin or is_hardcoded_admin

async def update_group_admins(chat_id: int, context) -> bool:
    """
    Fetches the current list of administrators for a given chat
    and updates the global_data storage.
    Returns True on success, False on failure.
    """
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins if not admin.user.is_bot] # Exclude bots

        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["group_admins"] = admin_ids # Update chat-specific admin list

        save_data(global_data)

        logger.info(f"update_group_admins: Updated admin list for chat {chat_id}: {admin_ids}")
        return True
    except Exception as e:
        logger.error(f"update_group_admins: Failed to get chat administrators for chat {chat_id}: {e}", exc_info=True)
        return False

def get_or_create_global_user_data(user_id: int, first_name: Optional[str] = None, last_name: Optional[str] = None, username: Optional[str] = None):
    """
    Retrieves or initializes a user's global data (e.g., referral points, display names).
    Ensures that user data is present and updates names if more complete ones are provided.
    """
    if str(user_id) not in global_data["global_user_data"]:
        # Initialize with the best available name
        full_name_init = f"{first_name or ''} {last_name or ''}".strip()
        if not full_name_init: # If no first/last name, try username
            full_name_init = username if username else f"User {user_id}"

        global_data["global_user_data"][str(user_id)] = {
            "full_name": full_name_init,
            "username": username,
            "referral_points": 0,
            "referred_by": None,
            "pending_referrer_id": None
        }
    else:
        # Update existing user's data with more complete info if available
        user_data = global_data["global_user_data"][str(user_id)]

        # Construct new full_name from provided parts
        new_full_name = f"{first_name or ''} {last_name or ''}".strip()

        # Only update full_name if the new one is not empty and different from current,
        # or if the current one is a generic placeholder.
        if new_full_name and (user_data.get("full_name") == f"User {user_id}" or user_data.get("full_name") != new_full_name):
            user_data["full_name"] = new_full_name

        # Only update username if the new one is not empty and different from current,
        # or if the current one is None.
        if username and (user_data.get("username") is None or user_data.get("username") != username):
            user_data["username"] = username

    return global_data["global_user_data"][str(user_id)]

async def _get_user_display_name(context, user_id: int, chat_id: Optional[int] = None) -> str:
    """
    Attempts to get the display name for a user ID, formatted as "Name (username)".
    Prioritizes cached data, then fetches from Telegram API to update cache.
    """
    user_info = global_data["global_user_data"].get(str(user_id))
    cached_full_name = user_info.get("full_name") if user_info else None
    cached_username = user_info.get("username") if user_info else None

    # Try to fetch fresh data from Telegram API
    fetched_user = None
    try:
        # Prioritize getting from chat_member for more reliable first/last name
        if chat_id:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            fetched_user = chat_member.user
        else: # Fallback to get_chat if chat_id not available (e.g., from direct message to bot)
            fetched_user = await context.bot.get_chat(user_id)
    except Exception as e:
        logger.debug(f"Failed to fetch user details for {user_id} from Telegram API (possibly not in common group, or bot is not admin in group): {e}")

    if fetched_user:
        current_full_name = fetched_user.full_name
        current_username = fetched_user.username

        # Update global_user_data with the latest fetched info
        # Pass first_name and last_name explicitly to get_or_create_global_user_data
        get_or_create_global_user_data(user_id, fetched_user.first_name, fetched_user.last_name, username=fetched_user.username)

        # Decide display format
        if current_full_name and current_username:
            return f"{current_full_name} (@{current_username})"
        elif current_full_name:
            return current_full_name
        elif current_username:
            return f"@{current_username}"
        else:
            return f"User {user_id}" # Fallback if fetched user has no name/username
    elif cached_full_name or cached_username:
        # Fallback to cached data if API fetch failed but we have data
        if cached_full_name and cached_username:
            return f"{cached_full_name} (@{cached_username})"
        elif cached_full_name:
            return cached_full_name
        elif cached_username:
            return f"@{cached_username}"

    return f"User {user_id}" # Final fallback if no data at all

async def get_admins_from_chat(chat_id: int, context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> list[int]:
    """
    Fetches the list of admin user IDs for a given chat, caching them if possible.
    """
    chat_data = get_chat_data_for_id(chat_id)
    cached_admins = chat_data.get("group_admins")

    # Fetch current admins directly from Telegram
    try:
        chat_administrators = await context.bot.get_chat_administrators(chat_id)
        admin_user_ids = [admin.user.id for admin in chat_administrators if not admin.user.is_bot]

        # Add hardcoded admins to the list
        admin_user_ids.extend(HARDCODED_ADMINS)
        admin_user_ids = list(set(admin_user_ids)) # Remove duplicates

        # Cache the fetched admins
        chat_data["group_admins"] = admin_user_ids
        save_data(global_data) # Save global data after updating chat_data

        logger.info(f"Fetched and cached admins for chat {chat_id}: {admin_user_ids}")
        return admin_user_ids
    except telegram.error.TelegramError as e:
        logger.error(f"Error fetching chat administrators for {chat_id}: {e}")
        # Fallback to cached admins or hardcoded if fetching fails
        if cached_admins:
            return list(set(cached_admins + HARDCODED_ADMINS))
        return list(set(HARDCODED_ADMINS)) # Return hardcoded admins if nothing else available


# =============================================================================
# Core Game Logic Functions (Called by Job Queue)
# These need to be defined early because they are referenced by name strings
# in context.job_queue.run_once/run_daily calls.
# =============================================================================

async def refill_all_admin_points(context):
    """
    Scheduled job to refill points for all known admins.
    A known admin is any admin in HARDCODED_ADMINS or any admin
    who has ever used an admin command. This ensures all active admins are covered.
    """
    logger.info("refill_all_admin_points: Starting daily admin point refill job.")

    current_active_admin_ids = set(HARDCODED_ADMINS)

    for chat_id_str in ALLOWED_GROUP_IDS:
        chat_id = int(chat_id_str)
        chat_admins = global_data["all_chat_data"].get(str(chat_id), {}).get("group_admins", [])
        current_active_admin_ids.update(chat_admins)

    refilled_count = 0
    updated_username_count = 0

    for admin_id in current_active_admin_ids:
        if admin_id == context.bot.id:
            logger.debug(f"Skipping bot's own ID {admin_id} in admin refill.")
            continue

        admin_profile = global_data["admin_data"].get(str(admin_id))
        if not admin_profile:
            # This case should be rare if admins interact, but good for bootstrapping
            admin_profile = {
                "username": f"Admin {admin_id}",
                "chat_points": {}
            }
            global_data["admin_data"][str(admin_id)] = admin_profile
            logger.info(f"refill_all_admin_points: Initialized general admin profile for {admin_id}.")


        # Try to update username from global_user_data if available
        global_user_info = global_data["global_user_data"].get(str(admin_id))
        if global_user_info:
            latest_username = global_user_info.get("username") or global_user_info.get("full_name")
            if latest_username and admin_profile.get("username") != latest_username:
                admin_profile["username"] = latest_username
                updated_username_count += 1
                logger.debug(f"Updated username for admin {admin_id} to '{latest_username}'.")


        for chat_id_inner_str in ALLOWED_GROUP_IDS:
            chat_id_inner = int(chat_id_inner_str)

            admin_data_for_chat = get_admin_data(admin_id, chat_id_inner, username=admin_profile.get("username"))

            last_refill = admin_data_for_chat.get("last_refill")

            needs_refill = False
            if last_refill is None:
                needs_refill = True
                logger.info(f"Admin {admin_id} in chat {chat_id_inner} has no last_refill timestamp. Refilling.")
            else:
                # Ensure last_refill is a datetime object before comparison
                if isinstance(last_refill, str):
                    try:
                        last_refill = datetime.fromisoformat(last_refill)
                    except ValueError:
                        logger.warning(f"Could not parse last_refill string '{last_refill}' for admin {admin_id}. Refilling.")
                        needs_refill = True
                        last_refill = None # Reset to avoid repeated errors

                if last_refill:
                     # Make sure we compare timezone-aware with timezone-aware
                    last_refill_utc = last_refill.astimezone(pytz.utc) if last_refill.tzinfo else pytz.utc.localize(last_refill)
                    today_utc = datetime.now(pytz.utc).date()

                    if today_utc > last_refill_utc.date():
                        needs_refill = True
                        logger.info(f"Admin {admin_id} in chat {chat_id_inner} last refilled on {last_refill_utc.date()}. Refilling for {today_utc}.")
                    else:
                        logger.info(f"Admin {admin_id} in chat {chat_id_inner} already refilled today ({last_refill_utc.date()}). Skipping.")


            if needs_refill:
                admin_data_for_chat["points"] = ADMIN_INITIAL_POINTS
                admin_data_for_chat["last_refill"] = datetime.now(pytz.utc)
                refilled_count += 1
                logger.debug(f"Refilled points for admin {admin_id} in chat {chat_id_inner}. New balance: {admin_data_for_chat['points']}.")

                try:
                    # Use the most up-to-date username for notification
                    notification_username = admin_profile.get('username', f'Admin {admin_id}')
                    chat_title = "Unknown Chat"
                    try:
                        chat_obj = await context.bot.get_chat(chat_id_inner)
                        chat_title = chat_obj.title or chat_obj.first_name
                    except Exception as e:
                        logger.warning(f"Could not get chat title for chat ID {chat_id_inner}: {e}")

                    await context.bot.send_message(
                        chat_id=admin_id, # Send DM to admin
                        text=f"👑 Admin *{_escape_text_for_markdown(notification_username)}*, "
                             f"your Admin Points for the group '{_escape_text_for_markdown(chat_title)}' have been refilled to {ADMIN_INITIAL_POINTS:,}.",
                        parse_mode="Markdown"
                    )
                except telegram.error.BadRequest as e:
                    logger.warning(f"Could not send refill notification DM to admin {admin_id} for chat {chat_id_inner}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error sending refill notification DM to admin {admin_id}: {e}")


    if refilled_count > 0 or updated_username_count > 0:
        save_data(global_data)

    logger.info(f"refill_all_admin_points: Successfully refilled {ADMIN_INITIAL_POINTS:,} points for {refilled_count} instances of admins across chats. Updated {updated_username_count} admin usernames.")


async def force_admin_refill_on_startup(context):
    """
    Called on bot startup to ensure all active admins have their points refilled
    if they haven't been refilled on the current day. This addresses scenarios
    where the bot might have been offline or the scheduled job missed.
    """
    logger.info("force_admin_refill_on_startup: Checking for pending admin refills on bot startup.")
    # This function now acts as a wrapper for the main refill logic
    # to ensure consistency.
    await refill_all_admin_points(context)
    logger.info("force_admin_refill_on_startup: Check complete.")



async def refresh_all_group_admins(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """
    Scheduled task to refresh admin lists for all allowed groups.
    This ensures group_admins in global_data["all_chat_data"] are kept up-to-date.
    """
    logger.info("refresh_all_group_admins: Starting periodic refresh of all allowed group admin lists.")
    refreshed_count = 0
    for chat_id_str in ALLOWED_GROUP_IDS:
        chat_id = int(chat_id_str)
        success = await update_group_admins(chat_id, context)
        if success:
            refreshed_count += 1
    logger.info(f"refresh_all_group_admins: Completed refreshing admin lists for {refreshed_count}/{len(ALLOWED_GROUP_IDS)} allowed groups.")


async def close_bets_scheduled(context):
    """
    Scheduled job to close betting for a game and then schedule the dice roll.
    """
    job = context.job
    game = job.data
    chat_id = game.chat_id

    # Check if chat_id is an integer; if not, it might be from an old job.
    if not isinstance(chat_id, int):
        logger.warning(f"close_bets_scheduled: Received non-integer chat_id '{chat_id}'. Skipping job.")
        return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"close_bets_scheduled: Ignoring action from disallowed chat ID: {chat_id}")
        return

    logger.info(f"close_bets_scheduled: Job called for match {game.match_id} in chat {chat_id}.")

    current_game_in_context = context.chat_data.get(chat_id, {}).get("current_game")
    if chat_id in context.chat_data and "close_bets_job" in context.chat_data[chat_id]:
        del context.chat_data[chat_id]["close_bets_job"]

    if current_game_in_context is None or current_game_in_context != game:
        logger.warning(f"close_bets_scheduled: Skipping action for match {game.match_id} in chat {chat_id} as game instance changed or no game. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}.")
        return

    game.state = GAME_CLOSED
    logger.info(f"close_bets_scheduled: Bets closed for match {game.match_id} in chat {chat_id}. State set to GAME_CLOSED.")

    bet_summary_lines = [
        f"⏳ ပွဲစဉ် {game.match_id}: လောင်းကြေးတွေ ပိတ်လိုက်ပါပြီရှင့်! ⏳\n",
        "လက်ရှိလောင်းထားတာတွေကတော့:\n"
    ]

    has_bets = False
    for bet_type_key, bets_dict in game.bets.items():
        if bets_dict:
            has_bets = True
            bet_summary_lines.append(f" {bet_type_key.upper()} {RESULT_EMOJIS[bet_type_key]}:")
            sorted_bets = sorted(bets_dict.items(), key=lambda item: item[1], reverse=True)
            for uid, amount in sorted_bets:
                username_display = await _get_user_display_name(context, uid, chat_id)
                bet_summary_lines.append(f" → {username_display}: {amount} ကျပ်")

    if not has_bets:
        bet_summary_lines.append("ဒီပွဲမှာ ဘယ်သူမှ လောင်းကြေးထပ်မထားကြပါဘူးရှင့်။ စိတ်မကောင်းစရာပဲနော်。")

    bet_summary_lines.append("\nအန်စာတုံးလေးတွေ လှိမ့်နေပြီနော်... ရင်ခုန်နေပြီလား!�")

    try:
        logger.info(f"close_bets_scheduled: Attempting to send 'Bets closed and summary' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, f"*{'\n'.join(bet_summary_lines)}*", parse_mode="Markdown")
        logger.info(f"close_bets_scheduled: 'Bets closed and summary' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"close_bets_scheduled: Error sending 'Bets closed' message for chat {chat_id}: {e}", exc_info=True)

    if chat_id not in context.chat_data:
        context.chat_data[chat_id] = {}
    context.chat_data[chat_id]["roll_and_announce_job"] = context.job_queue.run_once(
        roll_and_announce_scheduled,
        10,
        chat_id=chat_id,
        data=game,
        name=f"roll_announce_{chat_id}_{game.match_id}"
    )
    logger.info(f"close_bets_scheduled: Job for roll_and_announce_scheduled set for 10 seconds for match {game.match_id} in chat {chat_id}.")
    logger.info(f"close_bets_scheduled: Function finished for match {game.match_id} in chat {chat_id}.")


async def roll_and_announce_scheduled(context):
    """
    Scheduled job to roll the dice, calculate payouts, and announce results.
    """
    job = context.job
    game = job.data
    chat_id = game.chat_id

    if not isinstance(chat_id, int):
        logger.warning(f"roll_and_announce_scheduled: Received non-integer chat_id '{chat_id}'. Skipping job.")
        return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"roll_and_announce_scheduled: Ignoring action from disallowed chat ID: {chat_id}")
        return

    logger.info(f"roll_and_announce_scheduled: Job called for match {game.match_id} in chat {chat_id}.")

    current_game_in_context = context.chat_data.get(chat_id, {}).get("current_game")
    if chat_id in context.chat_data and "roll_and_announce_job" in context.chat_data[chat_id]:
        del context.chat_data[chat_id]["roll_and_announce_job"]

    if current_game_in_context is not None and current_game_in_context != game and game.state != GAME_CLOSED:
         logger.warning(f"roll_and_announce_scheduled: Skipping action for match {game.match_id} due to invalid state or game instance change. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}, Game state: {game.state}.")
         return
    if game.state == GAME_OVER:
        logger.warning(f"roll_and_announce_scheduled: Skipping action for match {game.match_id} as it's already GAME_OVER.")
        return

    game.state = GAME_OVER

    d1, d2 = 0, 0

    try:
        logger.info(f"roll_and_announce_scheduled: Sending first animated dice for match {game.match_id}.")
        dice_message_1 = await context.bot.send_dice(chat_id=chat_id)
        d1 = dice_message_1.dice.value
        logger.info(f"roll_and_announce_scheduled: First dice rolled: {d1}.")
        await asyncio.sleep(2)

        logger.info(f"roll_and_announce_scheduled: Sending second animated dice for match {game.match_id}.")
        dice_message_2 = await context.bot.send_dice(chat_id=chat_id)
        d2 = dice_message_2.dice.value
        logger.info(f"roll_and_announce_scheduled: Second dice rolled: {d2}.")
        await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending animated dice for chat {chat_id}: {e}", exc_info=True)
        logger.warning("Falling back to random dice values due to Telegram API error.")
        d1, d2 = random.randint(1,6), random.randint(1,6)

    game.result = d1 + d2
    winning_type, multiplier, individual_payouts = game.payout(chat_id)

    save_data(global_data)

    result_message_text = (
        f"🎉 ပွဲစဉ် {game.match_id} ရဲ့ အနိုင် အရှုံး ရလဒ်တွေ ထွက်ပေါ်လာပါပြီရှင့်! 🎉\n"
        f"🎲 ရလဒ်ကတော့: {d1} + {d2} = {d1 + d2} ဖြစ်ပါတယ်!\n"
        f"🏆 အနိုင်ရလောင်းကြေးက: {winning_type.upper()} {RESULT_EMOJIS[winning_type]} ပေါ် လောင်းထားသူတွေ {multiplier} ဆ ပြန်ရမှာနော်!\n\n"
        f"အနိုင်ရရှိသူတွေကတော့:\n"
    )

    chat_specific_data = get_chat_data_for_id(chat_id)
    stats = chat_specific_data["player_stats"]

    if individual_payouts:
        payout_lines = []
        sorted_payouts = sorted(
            individual_payouts.items(),
            key=lambda item: (item[1], stats.get(str(item[0]), {}).get('username', f"User {item[0]}")), # Ensure string key
            reverse=True
        )

        for uid, winnings in sorted_payouts:
            username_display = await _get_user_display_name(context, uid, chat_id)
            player_info = stats.get(str(uid)) # Get updated player_info after payout, ensure string key

            payout_lines.append(f" ✨ {username_display}: +{winnings} ကျပ် ရရှိပြီး လက်ကျန်ငွေ: {player_info['score']}!")
        result_message_text += "\n".join(payout_lines)
    else:
        result_message_text += " ဒီပွဲမှာ ဘယ်သူမှ ကံမကောင်းခဲ့ဘူးရှင့်! စိတ်မကောင်းစရာပဲနော်。💔"

    lost_players = []
    for uid in game.participants:
        if uid not in individual_payouts:
            username_display = await _get_user_display_name(context, uid, chat_id)
            player_info = stats.get(str(uid)) # Ensure string key
            if player_info:
                lost_players.append(f" 💀 {username_display} (လက်ကျန်ငွေ: {player_info['score']}) - ကံမကောင်းခဲ့ဘူးရှင့်!")
            else:
                lost_players.append(f" 💀 {username_display} (ရမှတ်မတွေ့ပါ) - ဘယ်သူဘယ်ဝါမှန်းမသိဘဲ ရှုံးသွားတာလားရှင့်!")

    if lost_players:
        result_message_text += "\n\nဒီပွဲမှာ ကံဆိုးခဲ့ကြသူတွေကတော့:\n"
        result_message_text += "\n".join(lost_players)

    try:
        logger.info(f"roll_and_announce_scheduled: Attempting to send 'Results' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, f"*{result_message_text}*", parse_mode="Markdown")
        logger.info(f"roll_and_announce_scheduled: 'Results' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending 'Results' message for chat {chat_id}: {e}", exc_info=True)

    chat_specific_data = get_chat_data_for_id(chat_id)

    if not game.participants:
        chat_specific_data["consecutive_idle_matches"] += 1
        logger.info(f"No participants in match {game.match_id}. Consecutive idle matches for chat {chat_id}: {chat_specific_data['consecutive_idle_matches']}")
    else:
        chat_specific_data["consecutive_idle_matches"] = 0
        logger.info(f"Participants found in match {game.match_id}. Resetting idle counter for chat {chat_id}.")

    save_data(global_data)

    if chat_specific_data["consecutive_idle_matches"] >= 5:
        logger.info(f"Stopping game sequence in chat {chat_id} due to 5 consecutive idle matches.")
        await context.bot.send_message(
            chat_id,
            f"*😴 ဂိမ်းရပ်လိုက်ပါပြီရှင့်! 😴\n\n"
            f"ဆက်တိုက် ၅ ပွဲဆက် ဘယ်သူမှ လောင်းကြေးထပ်တာ မတွေ့ရလို့ ဂိမ်းကို ခဏရပ်လိုက်ပါပြီရှင့်。"
            f"ပြန်ကစားချင်ရင် Admin ကိုပြောပါရှင့်。",
            parse_mode="Markdown"
        )
        context.chat_data[chat_id].pop("current_game", None)
        context.chat_data[chat_id].pop("num_matches_total", None)
        context.chat_data[chat_id].pop("current_match_index", None)

        job_names_to_remove = [
            f"next_game_{chat_id}",
            f"close_bets_{chat_id}_{game.match_id}",
            f"roll_announce_{chat_id}_{game.match_id}",
            f"next_game_sequence_{chat_id}"
        ]
        for job_name in job_names_to_remove:
            jobs = context.job_queue.get_jobs_by_name(job_name)
            for job_obj in jobs:
                try:
                    job_obj.schedule_removal()
                    logger.info(f"Removed scheduled job {job_name} for chat {chat_id}.")
                except JobLookupError:
                    logger.warning(f"JobLookupError for '{job_name}' during auto-stop for chat {chat_id}. It might have already run or been cancelled.")

        save_data(global_data)
        return

    if chat_id in context.chat_data and context.chat_data[chat_id].get("num_matches_total") is not None:
        logger.info(f"roll_and_announce_scheduled: Multi-match sequence active. Scheduling next game in sequence for chat {chat_id}.")
        context.chat_data[chat_id]["next_game_job"] = context.job_queue.run_once(
            _manage_game_sequence,
            5,
            chat_id=chat_id,
            data={"num_matches_total": context.chat_data[chat_id]["num_matches_total"], "current_match_index": context.chat_data[chat_id]["current_match_index"]},
            name=f"next_game_sequence_{chat_id}"
        )
    else:
        if chat_id in context.chat_data and "current_game" in context.chat_data[chat_id]:
            del context.chat_data[chat_id]["current_game"]
            logger.info(f"roll_and_announce_scheduled: Cleaned up game data for chat {chat_id} after single interactive match {game.match_id}.")
        jobs = context.job_queue.get_jobs_by_name(f"next_game_{chat_id}")
        for job_obj in jobs:
            try:
                job_obj.schedule_removal()
            except JobLookupError:
                pass
        if chat_id in context.chat_data and "next_game_job" in context.chat_data[chat_id]:
             del context.chat_data[chat_id]["next_game_job"]


    logger.info(f"roll_and_announce_scheduled: Function finished for match {game.match_id} in chat {chat_id}.")


# =============================================================================
# Helper Functions for Game Flow (May call scheduled functions)
# =============================================================================

async def _start_interactive_game_round(chat_id: int, context):
    """
    Helper function to initiate a single interactive game round.
    This logic is extracted to be reusable for both single /startdice and sequential games.
    """
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"_start_interactive_game_round: Ignoring action from disallowed chat ID: {chat_id}")
        return

    chat_specific_data = get_chat_data_for_id(chat_id)
    match_id = chat_specific_data["match_counter"]
    chat_specific_data["match_counter"] += 1

    save_data(global_data)

    game = DiceGame(match_id, chat_id)
    if chat_id not in context.chat_data:
        context.chat_data[chat_id] = {}
    context.chat_data[chat_id]["current_game"] = game

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("BIG ⬆️ (Total > 7)", callback_data="bet_big"),
            InlineKeyboardButton("SMALL 🔽 (Total < 7)", callback_data="bet_small"),
            InlineKeyboardButton("LUCKY 🍀 (Total = 7)", callback_data="bet_lucky")
        ]
    ])

    await context.bot.send_message(
        chat_id,
        f"*🔥 ပွဲစဉ် {match_id}: လောင်းကြေးတွေ ဖွင့်လိုက်ပါပြီရှင့်! 🔥\n\n"
        f"💰  7 ထက်ငယ်ရင် Small 7 ထက်ကြီးရင် Big 7 ဦးဆိုရင်တော့ Lucky ဖြစ်ပါတယ်\n"
        f"ပွဲတစ်ပွဲတည်းမှာ မတူညီတဲ့ အကြီးအသေးတွေပေါ် အကြိမ်ပေါင်းများစွာ လောင်းကြေးထပ်လို့ရပါတယ်နော်။ \n\n"
        f"⏳ လောင်းကြေးတွေကို စက္ကန့် ၆၀ အတွင်း ပိတ်တော့မယ်နော်! မြန်မြန်လေး... ကံကြမ္မာက သင့်ကိုစောင့်နေတယ်။ ကံကောင်းပါစေရှင့်! ✨*",
        parse_mode="Markdown", reply_markup=keyboard
    )
    logger.info(f"_start_interactive_game_round: Match {match_id} started successfully in chat {chat_id}. Betting open for 60 seconds.")

    if chat_id not in context.chat_data:
        context.chat_data[chat_id] = {}
    context.chat_data[chat_id]["close_bets_job"] = context.job_queue.run_once(
        close_bets_scheduled,
        60,
        chat_id=chat_id,
        data=game,
        name=f"close_bets_{chat_id}_{game.match_id}"
    )
    logger.info(f"_start_interactive_game_round: Job for close_bets_scheduled scheduled for match {match_id} in chat {chat_id}.")


async def _manage_game_sequence(context):
    """
    This function is called by the job queue to start the next interactive game in a sequence.
    """
    chat_id = context.job.chat_id
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"_manage_game_sequence: Ignoring action from disallowed chat ID: {chat_id}")
        return

    chat_data_for_sequence = context.chat_data.get(chat_id, {})
    num_matches_total = chat_data_for_sequence.get("num_matches_total")
    current_match_index = chat_data_for_sequence.get("current_match_index")

    if num_matches_total is None or current_match_index is None:
        logger.error(f"_manage_game_sequence: Missing sequence state in chat {chat_id}. Aborting sequence.")
        return

    if current_match_index < num_matches_total:
        logger.info(f"_manage_game_sequence: Starting next game in sequence. Match {current_match_index + 1} of {num_matches_total} for chat {chat_id}.")
        chat_data_for_sequence["current_match_index"] += 1
        await _start_interactive_game_round(chat_id, context)
    else:
        logger.info(f"_manage_game_sequence: All {num_matches_total} matches in sequence completed for chat {chat_id}. Cleaning up.")
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["consecutive_idle_matches"] = 0
        if chat_id in context.chat_data:
            if "num_matches_total" in context.chat_data[chat_id]:
                del context.chat_data[chat_id]["num_matches_total"]
            if "current_match_index" in context.chat_data[chat_id]:
                del context.chat_data[chat_id]["current_match_index"]
            if "current_game" in context.chat_data[chat_id]:
                del context.chat_data[chat_id]["current_game"]
            if "next_game_job" in context.chat_data[chat_id]:
                try:
                    context.chat_data[chat_id]["next_game_job"].schedule_removal()
                except JobLookupError:
                    logger.warning(f"_manage_game_sequence: JobLookupError for 'next_game_job' during sequence cleanup for chat {chat_id}.")
                finally:
                    del context.chat_data[chat_id]["next_game_job"]

        save_data(global_data)

        await context.bot.send_message(
            chat_id,
            f"*🎉 ပွဲစဥ်တွေအားလုံး ပြီးဆုံးသွားပါပီရှင့် နောက်ထပ်ကစားပွဲများ စတင်ရန် Admin အားပြောပါရှင့်....❤️ 🎉*",
            parse_mode="Markdown"
        )


# =============================================================================
# Telegram Handler Functions (Commands, Callbacks, Messages)
# =============================================================================

async def ping(update: Update, context):
    """
    Responds to a /ping command to check bot responsiveness.
    """
    await update.message.reply_text("*Pong!*", parse_mode="Markdown")
    logger.info(f"Ping received from user {update.effective_user.id} in chat {update.effective_chat.id}. Replied with Pong.")


async def my_wallet(update: Update, context):
    """
    Displays the user's personal game statistics (score, wins, losses, etc.)
    and, if the user is an admin, their admin wallet balance.
    This command is accessible to all users.
    --- UPDATED: Display referral points from global_user_data and use _get_user_display_name ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int):
        logger.warning(f"my_wallet: Received non-integer chat_id '{chat_id}'.")
        return

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"my_wallet: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    logger.info(f"my_wallet: User {user_id} requested wallet and stats information in chat {chat_id}")

    global_user_info = get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)

    user_display_name = await _get_user_display_name(context, user_id, chat_id)

    if await is_admin(chat_id, user_id, context):
        admin_data = get_admin_data(user_id, chat_id, update.effective_user.username)
        admin_points = admin_data.get("points", 0)
        message_lines = [
            f"👤 {user_display_name} \n",
            f"\n👑 Admin Wallet: {admin_points:,} ကျပ်"
        ]
        logger.info(f"my_wallet: User {user_id} is admin. Displaying admin points for chat {chat_id}: {admin_points}")
        save_data(global_data)
        await update.message.reply_text(f"*{'\n'.join(message_lines)}*", parse_mode="Markdown")
        return

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(str(user_id))

    if player_stats:
        if player_stats.get("username") != username_from_update:
            player_stats["username"] = username_from_update or first_name_from_update
    else:
        player_stats = {
            "username": username_from_update or first_name_from_update,
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now(),
        }
        chat_specific_data["player_stats"][str(user_id)] = player_stats

    referral_points = global_user_info.get("referral_points", 0)

    save_data(global_data)

    message_lines = [f"👤 {user_display_name} ၏ stats:\n"]

    total_games = player_stats['wins'] + player_stats['losses']
    win_rate = 0.0
    if total_games > 0:
        win_rate = (player_stats['wins'] / total_games) * 100

    message_lines.extend([
        f" 💰 Main Wallet: {player_stats['score']:,} ကျပ်\n",
        f" 🎁 Referral Points: {referral_points:,} ကျပ်\n",
        f" ကစားခဲ့တဲ့ပွဲ: {total_games} ပွဲ\n",
        f" ✅ အနိုင်: {player_stats['wins']} ပွဲ\n",
        f" ❌ အရှုံး: {player_stats['losses']} ပွဲ\n",
        f" win rate: {win_rate:.1f}%\n",
        f" နောက်ဆုံးကစားချိန်: {player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}"
    ])

    await update.message.reply_text(f"*{'\n'.join(message_lines)}*", parse_mode="Markdown")

async def admin_wallets(update: Update, context):
    """
    Allows an admin to check the wallet balances of all other admins in the current chat.
    Displays usernames instead of IDs, and ensures no duplicate entries.
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    requester_user_id = update.effective_user.id
    requester_username = update.effective_user.username
    requester_first_name = update.effective_user.first_name
    requester_last_name = update.effective_user.last_name

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"admin_wallets: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    if not await is_admin(chat_id, requester_user_id, context):
        logger.warning(f"admin_wallets: User {requester_user_id} is not an admin and tried to check admin wallets in chat {chat_id}.")
        return await update.message.reply_text("*❌ Admin တွေပဲ တခြား Admin တွေရဲ့ Wallet တွေကို စစ်ဆေးကြည့်လို့ရတာနော်。*", parse_mode="Markdown")

    # Ensure current requester's admin data and global user data is updated
    get_admin_data(requester_user_id, chat_id, requester_username or requester_first_name)
    get_or_create_global_user_data(requester_user_id, requester_first_name, requester_last_name, username=requester_username)
    save_data(global_data)

    message_lines = [f"👑 Admin Wallet Balances👑\n"] # Updated title

    current_chat_admin_info = []

    # Only get admins for the current chat where the command was issued
    relevant_admin_ids = await get_admins_from_chat(chat_id, context)

    for admin_id in relevant_admin_ids:
        if admin_id == context.bot.id:
            continue

        # Get admin data specifically for this admin in *this* chat
        admin_data_for_chat = get_admin_data(admin_id, chat_id)

        admin_display_name = await _get_user_display_name(context, admin_id)

        current_chat_admin_info.append({
            "admin_id": admin_id,
            "chat_id": chat_id, # Always the current chat_id
            "display_name": admin_display_name,
            "points": admin_data_for_chat.get("points", 0)
        })

    if not current_chat_admin_info:
        message_lines.append("လက်ရှိမှာ Admin အချက်အလက် မရှိသေးပါဘူးရှင့်။ Admin တွေ Admin commands ကို အသုံးပြုလိုက်မှ အချက်အလက်တွေ စတင်စုဆောင်းပါလိမ့်မယ်။")
    else:
        # Sort by points in descending order
        sorted_admins = sorted(current_chat_admin_info, key=lambda x: x["points"], reverse=True)

        for i, entry in enumerate(sorted_admins):
            message_lines.append(f"\n{i+1}. {entry['display_name']} (ID: {_escape_text_for_markdown(str(entry['admin_id']))}): {entry['points']:,} ကျပ်")

    await update.message.reply_text(f"*{'\n'.join(message_lines)}*", parse_mode="Markdown")

async def start_dice(update: Update, context):
    """
    Starts a new dice game round or multiple automatic rounds.
    Only accessible by administrators.
    Usage: /startdice [number_of_matches]
    - If number_of_matches is provided, plays that many automatic matches.
    - If no number is provided, starts a single interactive betting round.
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"start_dice: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    logger.info(f"start_dice: User {user_id} attempting to start a game in chat {chat_id}")

    get_admin_data(user_id, chat_id, username_from_update or first_name_from_update)
    get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)
    save_data(global_data)

    chat_specific_data = get_chat_data_for_id(chat_id)
    if not chat_specific_data.get("group_admins"):
        logger.info(f"start_dice: Admin list for chat {chat_id} is empty or not loaded. Attempting to update it now.")
        if not await update_group_admins(chat_id, context):
            await update.message.reply_text(
                "*❌ Admin စာရင်းကို ရယူလို့မရသေးဘူးရှင့်။ Bot ကို 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားတာ သေချာလား စစ်ပေးပါဦးနော်။ ထပ်ပြီး ကြိုးစားကြည့်ပါဦး။*",
                parse_mode="Markdown"
            )
            return

    if not await is_admin(chat_id, user_id, context):
        logger.warning(f"start_dice: User {user_id} is not an admin and tried to start a game in chat {chat_id}.")
        return await update.message.reply_text("*❌ Admin တွေပဲ အန်စာတုံးဂိမ်းအသစ်ကို စလို့ရနိုင်တာပါနော်。*", parse_mode="Markdown")

    current_game = context.chat_data.get(chat_id, {}).get("current_game")
    if current_game and current_game.state != GAME_OVER:
        logger.warning(f"start_dice: Game already active in chat {chat_id}. State: {current_game.state}")
        return await update.message.reply_text("*⚠️ ဟိတ်! ဂိမ်းလေး စနေပြီရှင့်။ အရင်ပွဲလေး ပြီးသွားမှပဲ အသစ်စလို့ရမယ်နော်။ နည်းနည်းလေး စောင့်ပေးပါဦး။*", parse_mode="Markdown")

    if chat_id in context.chat_data and context.chat_data[chat_id].get("num_matches_total") is not None:
         return await update.message.reply_text("*⚠️ ပွဲစဉ်တွေ ဆက်တိုက် စထားပြီးပြီနော်။ လက်ရှိပွဲစဉ်တွေ ပြီးဆုံးသွားတဲ့အထိ စောင့်ပေးပါဦးနော်。*", parse_mode="Markdown")


    num_matches_requested = 1

    if context.args:
        try:
            num_matches_requested = int(context.args[0])
            if num_matches_requested <= 0:
                return await update.message.reply_text("*❌ ပွဲအရေအတွက်က ဂဏန်းအပြုသဘော (positive integer) ဖြစ်ရမယ်နော်。*", parse_mode="Markdown")
            elif num_matches_requested > 100:
                return await update.message.reply_text("*❌ တစ်ခါတည်း အန်စာတုံးပွဲ ၁၀၀ ပွဲအထိပဲ စီစဉ်လို့ရပါသေးတယ်နော်。*", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text(
                f"*ℹ️ /startdice အတွက် မှားယွင်းတဲ့ စာရိုက်ပုံလေး ဖြစ်နေတယ်ရှင့်။ တစ်ပွဲတည်းသော အန်စာတုံးပွဲကိုတော့ စတင်ပေးလိုက်ပါမယ်。\n"
                f"အသုံးပြုပုံလေးကတော့: `/startdice` ဆိုရင် တစ်ပွဲစမယ်။ ဒါမှမဟုတ် `/startdice <အရေအတွက်>` ဆိုရင်တော့ ဆက်တိုက်ပွဲများစွာအတွက် သုံးလို့ရပါတယ်။*",
                parse_mode="Markdown"
            )
            num_matches_requested = 1


    if num_matches_requested > 1:
        if chat_id not in context.chat_data:
            context.chat_data[chat_id] = {}
        context.chat_data[chat_id]["num_matches_total"] = num_matches_requested
        context.chat_data[chat_id]["current_match_index"] = 0

        await context.bot.send_message(
            chat_id,
            f"*🎮 ပွဲစဉ် {_escape_text_for_markdown(str(num_matches_requested))} ပွဲ စပေးထားတယ်နော်!!*",
            parse_mode="Markdown"
        )
        if chat_id not in context.chat_data:
            context.chat_data[chat_id] = {}
        context.chat_data[chat_id]["next_game_job"] = context.job_queue.run_once(
            _manage_game_sequence,
            2,
            chat_id=chat_id,
            data={"num_matches_total": num_matches_requested, "current_match_index": 0},
            name=f"sequence_start_{chat_id}"
        )
    else:
        await _start_interactive_game_round(chat_id, context)


async def button_callback(update: Update, context):
    """
    Handles inline keyboard button presses for placing bets.
    """
    query = update.callback_query
    if not query or not query.message:
        return

    chat_id = query.message.chat_id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"button_callback: Ignoring callback from disallowed chat ID: {chat_id}")
        await query.answer(f"Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}).", show_alert=True)
        return

    await query.answer()

    data = query.data
    user_id = query.from_user.id
    username_from_query = query.from_user.username
    first_name_from_query = query.from_user.first_name
    last_name_from_query = query.from_user.last_name

    get_or_create_global_user_data(user_id, first_name_from_query, last_name_from_query, username=username_from_query)
    save_data(global_data)

    if await is_admin(chat_id, user_id, context):
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"button_callback: Admin {user_id} ({user_display_name}) tried to place a bet. Blocking.")
        return await query.message.reply_text(
            f"*❌ {user_display_name} ရေ၊ Admin တွေ ဂိမ်းမှာ လောင်းကြေးထပ်လို့ မရပါဘူးနော်။ ကစားသမားတွေအတွက်ပဲ ရတာပါ။*",
            parse_mode="Markdown"
        )
    game = context.chat_data.get(chat_id, {}).get("current_game")

    if not game:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"button_callback: User {user_id} ({user_display_name}) tried to bet via button but no game active in chat {chat_id}.")
        return await query.message.reply_text(
            f"*⚠️ {user_display_name} ရေ၊ အန်စာတုံးဂိမ်းက မစသေးဘူးရှင့်။ Admin တစ်ယောက်က စပေးမှ ရမှာနော်。*",
            parse_mode="Markdown"
        )

    if game.state != WAITING_FOR_BETS:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"button_callback: User {user_id} ({user_display_name}) tried to bet via button but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await query.message.reply_text(
            f"*⚠️ {user_display_name} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်လိုက်ပြီရှင့်။ နောက်ပွဲကမှ ထပ်လောင်းလို့ရမယ်နော်!*",
            parse_mode="Markdown"
        )

    bet_type = data.split("_")[1]

    username_for_game_logic = username_from_query or first_name_from_query
    success, response_message = game.place_bet(user_id, username_for_game_logic, bet_type, 100)

    if success:
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["consecutive_idle_matches"] = 0
        logger.info(f"button_callback: Bet placed by {user_id}, resetting idle counter for chat {chat_id}.")

    await query.message.reply_text(f"*{response_message}*", parse_mode="Markdown")
    logger.info(f"button_callback: User {user_id} placed bet via button: {bet_type} (100 pts) in chat {chat_id}. Success: {success}")


async def handle_bet(update: Update, context):
    """
    Handles text-based bet commands (e.g., 'b 500', 's 200', 'l 100', 'big 50', 'lucky50').
    It now expects a single bet per message and will not be chatty on non-bet text.
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"handle_bet: Ignoring message from disallowed chat ID: {chat_id}")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name
    message_text = update.message.text.strip()

    logger.info(f"handle_bet: User {user_id} attempting to place text bet: '{message_text}' in chat {chat_id}")

    get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)
    save_data(global_data)

    if await is_admin(chat_id, user_id, context):
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"handle_bet: Admin {user_id} ({user_display_name}) tried to place a bet via text. Blocking.")
        return await update.message.reply_text(
            f"*❌ {user_display_name} ရေ၊ Admin တွေ ဂိမ်းမှာ လောင်းကြေးထပ်လို့ မရပါဘူးနော်။ ကစားသမားတွေအတွက်ပဲ ရတာပါ။*",
            parse_mode="Markdown"
        )
    game = context.chat_data.get(chat_id, {}).get("current_game")
    if not game:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"handle_bet: User {user_id} tried to place text bet but no game active in chat {chat_id}.")
        return await update.message.reply_text(
            f"*⚠️ {user_display_name} ရေ၊ အန်စာတုံးဂိမ်းက မစသေးဘူးရှင့်။ Admin တစ်ယောက်က စပေးမှ ရမှာနော်。*",
            parse_mode="Markdown"
        )

    if game.state != WAITING_FOR_BETS:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.info(f"handle_bet: User {user_id} tried to place text bet but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await update.message.reply_text(
            f"*⚠️ {user_display_name} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်လိုက်ပြီရှင့်။ နောက်ပွဲကမှ ထပ်လောင်းလို့ရမယ်နော်!*",
            parse_mode="Markdown"
        )

    bet_match = re.match(r"^(big|b|small|s|lucky|l)\s*(\d+)$", message_text, re.IGNORECASE)

    if not bet_match:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.warning(f"handle_bet: Invalid bet format for user {user_id} in message: '{message_text}' in chat {chat_id}.")
        return await update.message.reply_text(
            f"*❌ {user_display_name} ရေ၊ လောင်းကြေးထပ်တာ ပုံစံလေး မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `big 500`, `small 100`, `lucky 250` စသည်ဖြင့် ရိုက်ပေးနော်。\n"
            f"ခလုတ်တွေ နှိပ်ပြီးတော့လည်း (မူရင်း ၁၀၀ မှတ်) လောင်းလို့ရတယ်နော်!*",
            parse_mode="Markdown"
        )

    bet_type_str, amount_str = bet_match.groups()

    bet_types_map = {
        "b": "big", "big": "big",
        "s": "small", "small": "small",
        "l": "lucky", "lucky": "lucky"
    }
    bet_type = bet_types_map.get(bet_type_str.lower())

    try:
        amount = int(amount_str)
    except ValueError:
        user_display_name = await _get_user_display_name(context, user_id, chat_id)
        logger.error(f"handle_bet: Failed to convert bet amount to integer from user {user_id}: '{amount_str}' in chat {chat_id}.")
        return await update.message.reply_text(f"*❌ {user_display_name} ရေ၊ လောင်းကြေးပမာဏက English ဂဏန်းဖြစ်ရမှာနော်。", parse_mode="Markdown")

    username_for_game_logic = username_from_update or first_name_from_update
    success, msg = game.place_bet(user_id, username_for_game_logic, bet_type, amount)

    if success:
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["consecutive_idle_matches"] = 0
        logger.info(f"handle_bet: Bet placed by {user_id}, resetting idle counter for chat {chat_id}.")

    await update.message.reply_text(f"*{msg}*", parse_mode="Markdown")
    logger.info(f"handle_bet: User {user_id} placed bet: {bet_type} {amount} pts in chat {chat_id}. Success: {success}")


async def leaderboard(update: Update, context):
    """
    Displays the top 10 players by score in the current chat.
    Filters out players who haven't made any bets (still on initial 1000 points).
    --- UPDATED: Include global referral points in sorting and use _get_user_display_name ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"leaderboard: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    logger.info(f"leaderboard: User {update.effective_user.id} requested leaderboard in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    stats_for_chat = chat_specific_data["player_stats"]

    all_players = []
    for user_id_str, player_chat_stats in stats_for_chat.items():
        user_id = int(user_id_str)
        global_user_info = get_or_create_global_user_data(user_id, first_name=player_chat_stats.get("username"), username=player_chat_stats.get("username"))

        total_score = player_chat_stats["score"] + global_user_info.get("referral_points", 0)

        all_players.append({
            "user_id": user_id,
            "score": player_chat_stats["score"],
            "referral_points": global_user_info.get("referral_points", 0),
            "total_value": total_score
        })

    active_players = [
        p for p in all_players
        if p["score"] != INITIAL_PLAYER_SCORE or p["referral_points"] > 0
    ]
    top_players = sorted(active_players, key=lambda x: x["total_value"], reverse=True)[:10]

    if not top_players:
        return await update.message.reply_text("*ℹ️ ဒီ Chat ထဲမှာတော့ မှတ်တမ်းတင်ထားတဲ့ ကစားသမားတွေ မရှိသေးဘူးရှင့်။ ဂိမ်းစပြီး လောင်းကြေးထပ်လိုက်မှပဲ အမှတ်တွေတက်လာမှာနော်*", parse_mode="Markdown")

    message_lines = ["🏆 ဒီ Group ထဲက ထိပ်တန်းအနိုင်ရရှိသူတွေကတော့:\n"]
    for i, player in enumerate(top_players):
        user_display_name = await _get_user_display_name(context, player['user_id'], chat_id)
        message_lines.append(f"{i+1}. {user_display_name}: {player['score']:,}ကျပ် (Referral: {player['referral_points']:,})")

    await update.message.reply_text(f"*{'\n'.join(message_lines)}*", parse_mode="Markdown")


async def history(update: Update, context):
    """
    Displays the recent match history for the current chat (last 5 matches).
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"history: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    logger.info(f"history: User {update.effective_user.id} requested match history in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    match_history_for_chat = chat_specific_data["match_history"]

    if not match_history_for_chat:
        return await update.message.reply_text("*ℹ️ ဒီ Chat ထဲမှာတော့ ပွဲမှတ်တမ်းတွေ မရှိသေးဘူးရှင့်။ မှတ်တမ်းတွေ ဖန်တီးချင်ရင် ဂိမ်းတွေ များများ ကစားပါဦးနော်*", parse_mode="Markdown")

    message_lines = ["📜 မကြာသေးခင်က ပြီးသွားတဲ့ နောက်ဆုံး ၅ ပွဲ ကတော့:\n"]
    for match in match_history_for_chat[-5:][::-1]:
        timestamp_str = match['timestamp'].strftime('%Y-%m-%d %H:%M')
        winner_display = match['winner'].upper()
        winner_emoji = RESULT_EMOJIS.get(match['winner'], '')

        message_lines.append(
            f" • ပွဲစဉ် {_escape_text_for_markdown(str(match['match_id']))} | ရလဒ်: {str(match['result'])} ({_escape_text_for_markdown(winner_display)} {winner_emoji}) | ပါဝင်ကစားသူ: {_escape_text_for_markdown(str(match['participants']))} ယောက် | အချိန်: {timestamp_str}"
        )

    await update.message.reply_text(f"*{'\n'.join(message_lines)}*", parse_mode="Markdown")


async def adjust_score(update: Update, context):
    """
    Admin command to adjust a player's score.
    This has been updated to deduct points from the admin's personal wallet.
    Now, admins cannot adjust the score of other admins or themselves.
    --- UPDATED: Use _get_user_display_name for display ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return

    if chat_id not in ALLOWED_GROUP_IDS:
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    requester_user_id = update.effective_user.id
    requester_username = update.effective_user.username
    requester_first_name = update.effective_user.first_name
    requester_last_name = update.effective_user.last_name

    logger.info(f"adjust_score: User {requester_user_id} attempting to adjust score in chat {chat_id}")

    if not await is_admin(chat_id, requester_user_id, context):
        return await update.message.reply_text("*❌ Admin တွေပဲ ကစားသမားတွေကို ငွေထည့်ပေးလို့ရတာနော်。*", parse_mode="Markdown")

    admin_data_for_requester_chat = get_admin_data(requester_user_id, chat_id, requester_username or requester_first_name)
    get_or_create_global_user_data(requester_user_id, requester_first_name, requester_last_name, username=requester_username)
    save_data(global_data)

    admin_points = admin_data_for_requester_chat.get("points", 0)

    target_user_id = None
    amount_to_adjust = None
    target_display_name = None

    if update.message.reply_to_message:
        if not context.args or len(context.args) != 1:
            return await update.message.reply_text(
                f"*❌ ပြန်ဖြေပြီး သုံးတာ ပုံစံလေး မှားနေတယ်ရှင့်။ ကျေးဇူပြုပြီး: `/adjustscore <ပမာဏ>` ကိုပဲ သုံးပေးပါနော်。\n"
                "ဥပမာ- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` (၅၀၀ မှတ် ထည့်ဖို့ပေါ့) လို့ ရိုက်လိုက်ပါ။*",
                parse_mode="Markdown"
            )

        target_user_id = update.message.reply_to_message.from_user.id
        target_first_name = update.message.reply_to_message.from_user.first_name
        target_last_name = update.message.reply_to_message.from_user.last_name
        target_username = update.message.reply_to_message.from_user.username

        get_or_create_global_user_data(target_user_id, target_first_name, target_last_name, username=target_username)

        try:
            amount_to_adjust = int(context.args[0])
        except ValueError:
            return await update.message.reply_text(
                "*❌ ပမာဏက ဂဏန်းဖြစ်ရမှာနော်။ မှားနေတယ်ရှင့်。\n"
                "ဥပမာ- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` လို့ ရိုက်လိုက်ပါ။*",
                parse_mode="Markdown"
            )

    elif context.args and len(context.args) >= 2:
        first_arg = context.args[0]
        try:
            amount_to_adjust = int(context.args[1])
        except ValueError:
            return await update.message.reply_text(
                "*❌ ပမာဏက ဂဏန်းဖြစ်ရမှာနော်။ မှားနေတယ်ရှင့်。\n"
                f"ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100` စသည်ဖြင့် သုံးပါနော်。*",
                parse_mode="Markdown"
            )

        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]

            for uid_str, user_info in global_data["global_user_data"].items():
                if user_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = int(uid_str)
                    break

            if target_user_id is None:
                return await update.message.reply_text(
                    f"*❌ အသုံးပြုသူ '@{_escape_text_for_markdown(mentioned_username)}' ကို ရှာမတွေ့ဘူးရှင့်။ သူတို့က Bot နဲ့ အရင်က အပြန်အလှန်ပြောဖူးမှ ရမှာနော်။ ဒါမှမဟုတ် သူတို့ပို့ထားတဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး သုံးတာ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ကို ဂဏန်းနဲ့ ရိုက်ပြီး သုံးကြည့်ပါလား。",
                    parse_mode="Markdown"
                )
        else:
            try:
                target_user_id = int(first_arg)
                logger.info(f"check_user_score: Admin {requester_user_id} checking score by numeric ID for user {target_user_id}.")
                get_or_create_global_user_data(target_user_id)
            except ValueError:
                return await update.message.reply_text(
                    f"*❌ User ID ဒါမှမဟုတ် ပမာဏက မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `/adjustscore <user_id>` ဒါမှမဟုတ် `/adjustscore @username <ပမာဏ>` ကိုသုံးပေးနော်。\n"
                    f"ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`。",
                    parse_mode="Markdown"
                )

    else:
        return await update.message.reply_text(
            f"*❌ သုံးတဲ့ပုံစံလေး မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး အောက်က ပုံစံတွေထဲက တစ်ခုခုကို သုံးပေးပါ:\n"
            f"- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး: `/adjustscore <ပမာဏ>`\n"
            f"- တိုက်ရိုက်ရိုက်ထည့်ချင်ရင်: `/adjustscore <user_id>`\n"
            f"- Username နဲ့ ရိုက်ထည့်ချင်ရင်: `/adjustscore @username <ပမာဏ>`\n"
            f"ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`。",
            parse_mode="Markdown"
        )

    if target_user_id is None or amount_to_adjust is None:
        logger.error(f"adjust_score: Logic error: target_user_id ({target_user_id}) or amount_to_adjust ({amount_to_adjust}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("*❌ မထင်မှတ်ထားတဲ့ ပြဿနာလေး ဖြစ်သွားတယ်ရှင့်။ ကျေးဇူးပြုပြီး ထပ်ကြိုးစားကြည့်ပါဦးနော် ဒါမှမဟုတ် Admin ကို အကူအညီတောင်းပါ။*", parse_mode="Markdown")

    if await is_admin(chat_id, target_user_id, context):
        return await update.message.reply_text(
            "*❌ Admin တွေက တခြား Admin တွေရဲ့ ဒါမှမဟုတ် ကိုယ်တိုင်ရဲ့ Score ကို ပြောင်းလို့မရပါဘူး။*",
            parse_mode="Markdown"
        )

    if amount_to_adjust > 0 and admin_points < amount_to_adjust:
        return await update.message.reply_text(
            f"*❌ Insufficient Admin Points ❌\n\n"
            f"You tried to give {amount_to_adjust:,} points, but you only have {admin_points:,} points remaining in your wallet for this chat.*",
            parse_mode="Markdown"
        )

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats_for_chat = chat_specific_data["player_stats"]
    target_player_stats = player_stats_for_chat.get(str(target_user_id))

    if not target_player_stats:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
            fetched_username_raw = chat_member.user.username
            fetched_first_name = chat_member.user.first_name
            fetched_last_name = chat_member.user.last_name

            player_stats_for_chat[str(target_user_id)] = {
                "username": fetched_username_raw or fetched_first_name,
                "score": INITIAL_PLAYER_SCORE,
                "wins": 0, "losses": 0, "last_active": datetime.now(),
            }
            target_player_stats = player_stats_for_chat[str(target_user_id)]

            get_or_create_global_user_data(target_user_id, fetched_first_name, fetched_last_name, username=fetched_username_raw)

        except Exception as e:
            logger.error(f"adjust_score: Failed to fetch user details for {target_user_id}: {e}")
            return await update.message.reply_text(f"*❌ User ID `{_escape_text_for_markdown(str(target_user_id))}` ကို ရှာမတွေ့ပါဘူး။*", parse_mode="Markdown")

    target_display_name = await _get_user_display_name(context, target_user_id, chat_id)

    global_user_data_for_target = global_data["global_user_data"].get(str(target_user_id))
    if global_user_data_for_target and global_user_data_for_target.get("username"):
        if target_player_stats.get("username") != global_user_data_for_target["username"]:
            target_player_stats["username"] = global_user_data_for_target["username"]
    elif global_user_data_for_target and global_user_data_for_target.get("full_name"):
        if target_player_stats.get("username") != global_user_data_for_target["full_name"]:
            target_player_stats["username"] = global_user_data_for_target["full_name"]


    old_score = target_player_stats['score']
    target_player_stats['score'] += amount_to_adjust
    target_player_stats['last_active'] = datetime.now()
    new_score = target_player_stats['score']
    target_username = target_player_stats.get("username", f"User {target_user_id}")

    admin_data_for_requester_chat["points"] -= amount_to_adjust
    new_admin_points = admin_data_for_requester_chat["points"]

    save_data(global_data)

    await update.message.reply_text(
        f"*✅ Score Adjusted Successfully ✅\n\n"
        f"👤 User: {target_display_name} ({target_username})\n"
        f"💰 Adjustment: {amount_to_adjust:+,}\n"
        f"💳 User's New Wallet: {new_score:,}\n\n"
        f"👑 Your Admin Wallet: {new_admin_points:,}*",
        parse_mode="Markdown"
    )
    logger.info(f"adjust_score: Admin {requester_user_id} (New Bal: {new_admin_points}) adjusted score for {target_user_id}. User New Score: {new_score}")


async def check_user_score(update: Update, context):
    """
    Admin command to check a specific player's score and stats.
    Usage:
    - Reply to a user's message: /checkscore
    - Direct input (numeric ID): /checkscore <user_id>
    - Direct input (@username): /checkscore @username
    --- UPDATED: Display global referral points and use _get_user_display_name, remove ID from display ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"check_user_score: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    requester_user_id = update.effective_user.id
    requester_username = update.effective_user.username
    requester_first_name = update.effective_user.first_name
    requester_last_name = update.effective_user.last_name

    logger.info(f"check_user_score: User {requester_user_id} attempting to check score in chat {chat_id}")

    if not await is_admin(chat_id, requester_user_id, context):
        logger.warning(f"check_user_score: User {requester_user_id} is not an admin and tried to check score in chat {chat_id}.")
        return await update.message.reply_text("*❌ Admin တွေပဲ တခြားကစားသမားတွေရဲ့ Walletကို စစ်ဆေးကြည့်လို့ရတာနော်。*", parse_mode="Markdown")

    get_admin_data(requester_user_id, chat_id, requester_username or requester_first_name)
    get_or_create_global_user_data(requester_user_id, requester_first_name, requester_last_name, username=requester_username)
    save_data(global_data)

    target_user_id = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_first_name = update.message.reply_to_message.from_user.first_name
        target_last_name = update.message.reply_to_message.from_user.last_name
        target_username = update.message.reply_to_message.from_user.username

        get_or_create_global_user_data(target_user_id, target_first_name, target_last_name, username=target_username)
        save_data(global_data)

    elif context.args and len(context.args) == 1:
        first_arg = context.args[0]

        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]

            for uid_str, user_info in global_data["global_user_data"].items():
                if user_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = int(uid_str)
                    break

            if target_user_id == None:
                return await update.message.reply_text(
                    f"*❌ အသုံးပြုသူ '@{_escape_text_for_markdown(mentioned_username)}' ကို ရှာမတွေ့ဘူးရှင့်။ သူတို့က Bot နဲ့ အရင်က အပြန်အလှန်ပြောဖူးမှ ရတာနော်။ ဒါမှမဟုတ် သူတို့ပို့ထားတဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး သုံးတာ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ကို ဂဏန်းနဲ့ ရိုက်ပြီး သုံးကြည့်ပါ။*",
                    parse_mode="Markdown"
                )

            get_or_create_global_user_data(target_user_id, username=mentioned_username)
            save_data(global_data)

        else:
            try:
                target_user_id = int(first_arg)
                logger.info(f"check_user_score: Admin {requester_user_id} checking score by numeric ID for user {target_user_id}.")
                get_or_create_global_user_data(target_user_id)
                save_data(global_data)
            except ValueError:
                return await update.message.reply_text(
                    f"*❌ User ID ဒါမှမဟုတ် ပမာဏက မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `/checkscore <user_id>` ဒါမှမဟုတ် `/checkscore @username` ကိုသုံးပေးနော်。\n"
                    f"ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`。",
                    parse_mode="Markdown"
                )
    else:
        return await update.message.reply_text(
            f"*❌ သုံးတဲ့ပုံစံလေး မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး အောက်က ပုံစံတွေထဲက တစ်ခုခုကို သုံးပေးပါ:\n"
            f"- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး: `/checkscore`\n"
            f"- တိုက်ရိုက်ရိုက်ထည့်ချင်ရင်: `/checkscore <user_id>`\n"
            f"- Username နဲ့ ရိုက်ထည့်ချင်ရင်: `/checkscore @username`\n"
            f"ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`。",
            parse_mode="Markdown"
        )

    if target_user_id is None:
        logger.error(f"check_user_score: Logic error: target_user_id ({target_user_id}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("*❌ မထင်မှတ်ထားတဲ့ ပြဿနာလေး ဖြစ်သွားတယ်ရှင့်။ ကျေးဇူးပြုပြီး ထပ်ကြိုးစားကြည့်ပါဦးနော် ဒါမှမဟုတ် Admin ကို အကူအညီတောင်းပါ။*", parse_mode="Markdown")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(str(target_user_id))
    global_user_info = get_or_create_global_user_data(target_user_id)

    target_display_name = await _get_user_display_name(context, target_user_id, chat_id)


    if not player_stats:
        try:
            await update.message.reply_text(
                f"*👤 {target_display_name} မှာတော့ ဒီ Chat အတွက် ဂိမ်းမှတ်တမ်းတွေ မရှိသေးဘူးရှင့်。\n"
                f"💰Main Wallet: {INITIAL_PLAYER_SCORE} ကျပ်\n"
                f"Referral Points: {global_user_info.get('referral_points', 0):,} ကျပ်*",
                parse_mode="Markdown"
            )
            logger.info(f"check_user_score: Admin {requester_user_id} checked score for new user {target_user_id} (no chat stats yet).")
            return

        except Exception as e:
            logger.error(f"check_user_score: Failed to find player {target_user_id} or fetch their details in chat {chat_id}: {e}", exc_info=True)
            return await update.message.reply_text(
                f"*❌ User ID `{_escape_text_for_markdown(str(target_user_id))}` နဲ့ ကစားသမားကို ဒီ Chat ထဲမှာ ရှာမတွေ့ဘူးရှင့်။ Telegram က သူတို့ရဲ့ အချက်အလက်တွေကို ရယူလို့မရလို့ပါ။ သူတို့က ဒီ Chat ရဲ့ အဖွဲ့ဝင် ဟုတ်မဟုတ် သေချာအောင် စစ်ပေးပါဦးနော် ဒါမှမဟုတ် သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေကြည့်ပါ။*",
                parse_mode="Markdown"
            )

    global_user_data_for_target = global_data["global_user_data"].get(str(target_user_id))
    if global_user_data_for_target and global_user_data_for_target.get("username"):
        if player_stats.get("username") != global_user_data_for_target["username"]:
            player_stats["username"] = global_user_data_for_target["username"]
    elif global_user_data_for_target and global_user_data_for_target.get("full_name"):
        if player_stats.get("username") != global_user_data_for_target["full_name"]:
            player_stats["username"] = global_user_data_for_target["full_name"]

    save_data(global_data)

    total_games = player_stats['wins'] + player_stats['losses']
    win_rate = 0.0
    if total_games > 0:
        win_rate = (player_stats['wins'] / total_games) * 100
    await update.message.reply_text(
        f"*👤 {target_display_name} ရဲ့ stats:\n"
        f"💰 Wallet: {player_stats['score']:,} ကျပ်\n"
        f"🎁 Referral Points: {global_user_info.get('referral_points', 0):,} ကျပ်\n"
        f" ကစားခဲ့တဲ့ပွဲ: {total_games} ပွဲ\n"
        f" ✅ အနိုင်ပွဲ: {player_stats['wins']} ပွဲ\n"
        f" ❌ ရှုံးပွဲ: {player_stats['losses']} ပွဲ\n"
        f" Win rate: {win_rate:.1f}% \n"
        f" last active: {player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*",
        parse_mode="Markdown"
    )
    logger.info(f"check_user_score: Admin {requester_user_id} successfully checked score for user {target_user_id}.")


async def refresh_admins(update: Update, context):
    """
    Admin command to force a refresh of the group's admin list.
    --- UPDATED: Ensure global user data for requester is updated ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"refresh_admins: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    get_admin_data(user_id, chat_id, username_from_update or first_name_from_update)
    get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)
    save_data(global_data)

    if not await is_admin(chat_id, user_id, context):
        logger.warning(f"refresh_admins: User {user_id} tried to refresh admins in chat {chat_id} but is not an admin.")
        return await update.message.reply_text("*❌ Admin တွေပဲ Admin စာရင်းကို ပြန် Refresh လုပ်လို့ရတာနော်。*", parse_mode="Markdown")

    logger.info(f"refresh_admins: User {user_id} attempting to refresh admin list for chat {chat_id}.")

    if await update_group_admins(chat_id, context):
        await update.message.reply_text("*✅ Admin စာရင်းကို အောင်မြင်စွာ ပြန် Refresh လုပ်ပြီးပါပြီရှင့်! အခုဆို အချက်အလက်တွေ အသစ်ဖြစ်သွားပြီနော်。*", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "*❌ Admin စာရင်းကို ပြန် Refresh လုပ်လို့ မရသေးဘူးရှင့်။ Bot ကို 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားလား စစ်ပေးပါဦးနော်。*",
            parse_mode="Markdown"
        )


async def stop_game(update: Update, context):
    """
    Admin command to forcefully stop the current game (if active) and refund all placed bets.
    This can be used to interrupt a game or a sequence of games.
    --- UPDATED: Ensure global user data for requester and refunded users is updated and use _get_user_display_name ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"stop_game: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    logger.info(f"stop_game: User {user_id} attempting to stop a game in chat {chat_id}")

    get_admin_data(user_id, chat_id, username_from_update or first_name_from_update)
    get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)
    save_data(global_data)

    if not await is_admin(chat_id, user_id, context):
        logger.warning(f"stop_game: User {user_id} is not an admin and tried to stop a game in chat {chat_id}.")
        return await update.message.reply_text("*❌ Admin တွေပဲ လက်ရှိဂိမ်းကို ရပ်တန့်လို့ရပါတယ်နော်。*", parse_mode="Markdown")

    current_game = context.chat_data.get(chat_id, {}).get("current_game")

    if not current_game:
        logger.info(f"stop_game: No game object found in chat_data for chat {chat_id}.")
        return await update.message.reply_text(
            f"*ℹ️ လက်ရှိစထားတဲ့ အန်စာတုံးဂိမ်း မရှိသေးဘူးရှင့်။ စတင်ဖို့ Admin က စရမယ်နော်。*",
            parse_mode="Markdown"
        )

    if current_game.state == GAME_OVER:
        logger.info(f"stop_game: Game is already GAME_OVER for match {current_game.match_id} in chat {chat_id}.")
        return await update.message.reply_text(
            f"*ℹ️ ပွဲစဉ် #{_escape_text_for_markdown(str(current_game.match_id))} က ပြီးသွားပါပြီရှင့်။ ပြီးသွားတဲ့ပွဲကို ရပ်လို့မရဘူးနော်။ နောက်ပွဲကျမှ ကြိုးစားကြည့်ပါ!*",
            parse_mode="Markdown"
        )

    job_names_to_remove = [
        f"close_bets_{chat_id}_{current_game.match_id}",
        f"roll_announce_{chat_id}_{current_game.match_id}",
        f"next_game_sequence_{chat_id}"
    ]

    for job_name in job_names_to_remove:
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job_obj in jobs:
            try:
                job_obj.schedule_removal()
                logger.info(f"stop_game: Successfully cancelled job: {job_name} for chat {chat_id}.")
            except JobLookupError:
                logger.warning(f"stop_game: JobLookupError when trying to cancel job {job_name} for chat {chat_id}. It might have already run or been cancelled.")
            except Exception as e:
                logger.error(f"stop_game: Unexpected error canceling job '{job_name}' for chat {chat_id}: {e}", exc_info=True)
            if chat_id in context.chat_data:
                for key in ["close_bets_job", "roll_and_announce_job", "next_game_job"]:
                    if key in context.chat_data[chat_id]:
                        del context.chat_data[chat_id][key]


    refunded_players_info = []
    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats_for_chat = chat_specific_data["player_stats"]

    total_bets_by_user = {}

    for bet_type_dict in current_game.bets.values():
        for uid, amount_bet in bet_type_dict.items():
            total_bets_by_user[uid] = total_bets_by_user.get(uid, 0) + amount_bet

    total_refunded_amount = 0
    for uid, refunded_amount in total_bets_by_user.items():
        if str(uid) in player_stats_for_chat:
            player_stats = player_stats_for_chat[str(uid)]

            player_stats["score"] += refunded_amount
            player_stats["last_active"] = datetime.now()
            total_refunded_amount += refunded_amount

            user_display_name = await _get_user_display_name(context, uid)

            global_user_data_for_uid = global_data["global_user_data"].get(str(uid))
            if global_user_data_for_uid and global_user_data_for_uid.get("username") and player_stats.get("username") != global_user_data_for_uid["username"]:
                player_stats["username"] = global_user_data_for_uid["username"]
            elif global_user_data_for_uid and global_user_data_for_uid.get("full_name") and player_stats.get("username") != global_user_data_for_uid["full_name"]:
                player_stats["username"] = global_user_data_for_uid["full_name"]


            refunded_players_info.append(
                f" {user_display_name}: +{refunded_amount} ကျပ် (လက်ကျန်ငွေ: {player_stats['score']:,}, Referral: {global_user_data_for_uid.get('referral_points', 0):,})"
            )
            logger.info(f"stop_game: Refunded {refunded_amount} to user {uid} in chat {chat_id}. New score: {player_stats['score']}")
        else:
            user_display_name = await _get_user_display_name(context, uid)
            logger.warning(f"stop_game: Could not find player {uid} in stats for refund in chat {chat_id}. Displaying as '{user_display_name}'.")
            refunded_players_info.append(
                f" {user_display_name}: +{refunded_amount} ကျပ် (မှတ်တမ်းမရှိ) - လောင်းကြေးပြန်အမ်းပါသည်"
            )


    context.chat_data.pop(chat_id, None)

    save_data(global_data)

    refund_message = f"🛑 ပွဲစဉ် #{_escape_text_for_markdown(str(current_game.match_id))} ကို ရပ်တန့်လိုက်ပါပြီရှင့်! 🔥\n\n"
    if refunded_players_info:
        refund_message += "လောင်းကြေးတွေ အားလုံး ပြန်အမ်းပေးလိုက်ပြီနော်:\n"
        refund_message += "\n".join(refunded_players_info)
        refund_message += f"\n\nစုစုပေါင်း ပြန်အမ်းပေးလိုက်တဲ့ ပမာဏ: {total_refunded_amount} ကျပ်"
    else:
        refund_message += "လက်ရှိပွဲစဉ်မှာ လောင်းကြေးထပ်ထားတဲ့သူ မရှိလို့ ပြန်အမ်းစရာ မလိုပါဘူးရှင့်。"

    await update.message.reply_text(f"*{refund_message}*", parse_mode="Markdown")


async def deposit_points(update: Update, context):
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"deposit_points: Ignoring action from disallowed chat ID: {chat_id}")
        if update.message:
            await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name
    logger.info(f"deposit_points: User {user_id} requested deposit information in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(str(user_id))
    global_user_info = get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)

    if player_stats:
        if player_stats.get("username") != username_from_update:
            player_stats["username"] = username_from_update or first_name_from_update
    else:
        player_stats = {
            "username": username_from_update or first_name_from_update,
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now(),
        }
        chat_specific_data["player_stats"][str(user_id)] = player_stats

    save_data(global_data)

    await (update.message or update.callback_query.message).reply_text(
        f"*🪙 ငွေထည့်ရန်: 1 point = 1 kyat\n"
        f"ငွေဖြည့်သွင်းရန်အတွက် Admin ကို ဒီကနေ DM ပို့ပေးပါ 👉 @pussycat_1204\n"
        f"ကျေးဇူးတင်ပါတယ်!*",
        parse_mode="Markdown"
    )

async def withdraw_points(update: Update, context):
    """
    Handles the 'ငွေထုတ်မည်' (Withdraw) button and /withdraw command.
    Provides instructions for withdrawing points.
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"withdraw_points: Ignoring action from disallowed chat ID: {chat_id}")
        if update.message:
            await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({str(chat_id)}). Please add it to an allowed group.*", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name
    logger.info(f"withdraw_points: User {user_id} requested withdraw information in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(str(user_id))
    global_user_info = get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)

    if player_stats:
        if player_stats.get("username") != username_from_update:
            player_stats["username"] = username_from_update or first_name_from_update
    else:
        player_stats = {
            "username": username_from_update or first_name_from_update,
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now(),
        }
        chat_specific_data["player_stats"][str(user_id)] = player_stats

    save_data(global_data)

    await (update.message or update.callback_query.message).reply_text(
        f"*💸 ငွေထုတ်ရန်: 1 point = 1 kyat\n"
        f"ငွေထုတ်ယူရန်အတွက် Admin ကို ဒီကနေ DM ပို့ပေးပါ 👉 @pusycat_1204\n"
        f"ကျေးဇူးတင်ပါတယ်!*",
        parse_mode="Markdown"
    )

async def handle_share_referral(update: Update, context):
    """
    Generates a unique bot deep link for the user and sends it in a shareable format.
    The deep link will contain the referrer's user ID.
    --- UPDATED: Pass Markdown text directly to Telegram share URL for correct formatting. ---
    """
    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    bot_username = context.bot.username

    get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)
    save_data(global_data)

    if not bot_username:
        logger.error("Bot username not available for referral link generation.")
        await (update.message or update.callback_query.message).reply_text(
            f"*❌ Referral Link ထုတ်မရသေးဘူးရှင့်။ Bot ရဲ့ Username ကို Telegram မှာ သတ်မှတ်ထားတာ သေချာလား စစ်ပေးပါဦးနော်。",
            parse_mode="Markdown"
        )
        return

    bot_deep_link = f"https://t.me/{bot_username}?start={user_id}"

    user_display_name = await _get_user_display_name(context, user_id)

    share_intro = f"{user_display_name} ရေ၊ သင့် Referral Link ကို မျှဝေဖို့အတွက် အောက်က ခလုတ်ကို နှိပ်ပြီး လုပ်လို့ရပါတယ်။ (သူငယ်ချင်းတွေ Bot ကို စပြီး Message ပို့တာနဲ့ Point ရမယ်နော်!)"

    share_message_for_friend = (
        f"🌟 ကျွန်တော်တို့ရဲ့ အန်စာတုံးဂိမ်းဘော့တ်ကို လာဆော့ကြည့်ပါ! 🎲\n"
        f"ဒီ Link ကနေ Bot ကို စပြီး Message ပို့လိုက်ရုံနဲ့ ဂိမ်း Group ထဲကို အလိုအလျောက် ဝင်နိုင်မှာပါ။\n\n"
        f"👉 Bot Link (Referral): {bot_deep_link}\n\n"
        f"သူငယ်ချင်းတွေ များများဖိတ်ခေါ်လေ Referral Points များများရလေပါပဲနော်! 🎁"
    )

    encoded_share_text = urllib.parse.quote(share_message_for_friend, safe='')
    encoded_bot_deep_link = urllib.parse.quote(bot_deep_link, safe='')

    share_url = f"https://t.me/share/url?url={encoded_bot_deep_link}&text={encoded_share_text}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Referral Link ကို မျှဝေမည်", url=share_url)]
    ])

    await (update.message or update.callback_query.message).reply_text(
        f"*{share_intro}*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    logger.info(f"User {user_id} requested referral share. Sent inline share button with bot deep link: {bot_deep_link}")


async def on_chat_member_update(update: Update, context):
    """
    Handles updates related to chat members, specifically when the bot
    is added to or removed from a group, or its status changes.
    Now also tracks new user joins by checking their pending_referrer_id set by the /start command.
    --- UPDATED: Uses global_user_data for referral logic and _get_user_display_name for formatting ---
    """
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return


    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"on_chat_member_update: Ignoring new member join tracking from disallowed chat ID: {chat_id}")
        if chat_member_update.new_chat_member.user.id == context.bot.id and chat_member_update.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
            await context.bot.send_message(
                chat_id,
                f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}). Please remove it or add this group to ALLOWED_GROUP_IDS in constants.py.*",
                parse_mode="Markdown"
            )
        return

    new_chat_member = chat_member_update.new_chat_member
    old_chat_member = chat_member_update.old_chat_member
    joined_user = new_chat_member.user

    if new_chat_member.status == ChatMemberStatus.MEMBER and old_chat_member.status == ChatMemberStatus.LEFT:
        logger.info(f"User {joined_user.id} ({joined_user.username}) joined chat {chat_id}.")

        joined_user_global_info = get_or_create_global_user_data(joined_user.id, joined_user.first_name, joined_user.last_name, username=joined_user.username)

        chat_specific_data = get_chat_data_for_id(chat_id)
        player_stats = chat_specific_data["player_stats"].get(str(joined_user.id))
        if not player_stats:
            player_stats = {
                "username": joined_user.username or joined_user.first_name,
                "score": INITIAL_PLAYER_SCORE,
                "wins": 0,
                "losses": 0,
                "last_active": datetime.now(),
            }
            chat_specific_data["player_stats"][str(joined_user.id)] = player_stats
        else:
            if player_stats.get("username") != (joined_user.username or joined_user.first_name):
                player_stats["username"] = joined_user.username or joined_user.first_name

        pending_referrer_id = joined_user_global_info.get("pending_referrer_id")

        if pending_referrer_id is not None:
            logger.info(f"User {joined_user.id} joined group with pending_referrer_id: {pending_referrer_id}.")

            if pending_referrer_id == joined_user.id:
                logger.info(f"Self-referral detected for user {joined_user.id}. No points awarded.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"*{_escape_text_for_markdown(joined_user.full_name)} ရေ၊ ကိုယ့်ကိုယ်ကို ပြန်ဖိတ်လို့မရဘူးနော်။ သူငယ်ချင်းတွေကိုပဲ ဖိတ်ခေါ်လို့ရတာပါ။*",
                    parse_mode="Markdown"
                )
            elif joined_user_global_info["referred_by"] is not None:
                logger.info(f"User {joined_user.id} already referred by {joined_user_global_info['referred_by']}. Not re-awarding.")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"*🤔 {_escape_text_for_markdown(joined_user.full_name)} ရေ၊ ခင်ဗျားကို တစ်ယောက်ယောက်က အရင်တုန်းက ဖိတ်ခေါ်ထားပြီးသားမို့လို့ Referral Points တွေ ထပ်ပေးလို့မရတော့ဘူးနော်。",
                    parse_mode="Markdown"
                )
            else:
                referrer_global_info = get_or_create_global_user_data(pending_referrer_id)

                if referrer_global_info:
                    referrer_global_info["referral_points"] = referrer_global_info.get("referral_points", 0) + REFERRAL_BONUS_POINTS

                    referrer_display_name = await _get_user_display_name(context, pending_referrer_id)
                    joined_display_name = await _get_user_display_name(context, joined_user.id)

                    joined_user_global_info["referred_by"] = pending_referrer_id

                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"*🎉 {joined_display_name} အဖွဲ့ထဲသို့ ပါဝင်လာပါပြီ! "
                        f"{referrer_display_name} အား Referral Points {REFERRAL_BONUS_POINTS:,} ရရှိပါပြီ။*",
                        parse_mode="Markdown"
                    )
                    logger.info(f"User {joined_user.id} referred by {pending_referrer_id}. {REFERRAL_BONUS_POINTS} points awarded to referrer.")

                    try:
                        await context.bot.send_message(
                            chat_id=pending_referrer_id,
                            text=f"*✨ ချီးကျူးပါတယ်! သင်ဖိတ်ခေါ်ထားသော {joined_display_name} သည် group ထဲသို့ ဝင်ရောက်လာပြီဖြစ်၍ "
                            f"Referral Points {REFERRAL_BONUS_POINTS:,} ရရှိပါပြီ။ "
                            f"သင့်လက်ကျန် Referral Points: {referrer_global_info['referral_points']:,} ကျပ်*",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send direct message to referrer {pending_referrer_id}: {e}")
                else:
                    logger.warning(f"Referrer {pending_referrer_id} not found in global_user_data. No points awarded for {joined_user.id}.")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"*⚠️ {_escape_text_for_markdown(joined_user.full_name)} အဖွဲ့ထဲသို့ ပါဝင်လာပါပြီ။ သို့သော် ဖိတ်ခေါ်သူ၏အချက်အလက်ကို ရှာမတွေ့ပါ။*",
                        parse_mode="Markdown"
                    )
            joined_user_global_info["pending_referrer_id"] = None
        save_data(global_data)

    if new_chat_member.user.id == context.bot.id:
        new_status = new_chat_member.status

        if new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
            logger.info(f"on_chat_member_update: Bot was added to chat {chat_id} or its status changed. New status: {new_status}.")
            if await update_group_admins(chat_id, context):
                custom_keyboard = [
                    [KeyboardButton("ငွေထည့်မည်"), KeyboardButton("ငွေထုတ်မည်")],
                    [KeyboardButton("My Wallet"), KeyboardButton("Leaderboard"), KeyboardButton("ကစားနည်း")],
                    [KeyboardButton("Share")],
                ]
                custom_keyboard_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)

                await context.bot.send_message(
                    chat_id,
                    f"*အန်စာဂိမ်းဆော့ကစားတဲ့ Group လေးထဲမှ ကြိုဆိုပါတယ်ရှင့်🥳🥰\n"
                    f"ကဲ.....ဂိမ်းလေးစဆော့လိုက်ကြဖို့ Admin တစ်ယောက်ကို ဂိမ်းစခိုင်းလိုက်တော့နော်.......လက်ကျန်ငွေကိုစစ်ဖို့ အခုပဲ /mywallet ကိုနှိပ်ပြီးစစ်ဆေးလိုက်တော့နော်...🥰*",
                    parse_mode="Markdown",
                    reply_markup=custom_keyboard_markup
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    "*🔥 ဟိုင်း! ကျွန်တော်က အန်စာတုံးဂိမ်းဘော့တ်ပါ။ Admin စာရင်းကို ရယူရာမှာ နည်းနည်းအခက်အခဲရှိနေလို့ပါ။ 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားလား စစ်ပေးပါဦးနော်。*",
                    parse_mode="Markdown"
                )
        elif new_status == ChatMemberStatus.LEFT:
            logger.info(f"on_chat_member_update: Bot was removed from chat {chat_id}.")
            if str(chat_id) in global_data["all_chat_data"]:
                del global_data["all_chat_data"][str(chat_id)]
                save_data(global_data)
                logger.info(f"on_chat_member_update: Cleaned all_chat_data for chat {chat_id}.")
            if chat_id in context.chat_data:
                del context.chat_data[chat_id]
                logger.info(f"on_chat_member_update: Cleaned context.chat_data for chat {chat_id}.")

    save_data(global_data)


async def start(update: Update, context):
    """
    Handles the /start command, processing referral links if present,
    and sending a welcoming message with instructions and the group link.
    --- UPDATED: Uses global_user_data for referral logic and _get_user_display_name for formatting ---
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return

    user_id = update.effective_user.id
    username_from_update = update.effective_user.username
    first_name_from_update = update.effective_user.first_name
    last_name_from_update = update.effective_user.last_name

    logger.info(f"start: Received /start command from user {user_id} in chat {chat_id}")

    global_user_info = get_or_create_global_user_data(user_id, first_name_from_update, last_name_from_update, username=username_from_update)

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(str(user_id))
    if not player_stats:
        player_stats = {
            "username": username_from_update or first_name_from_update,
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now(),
        }
        chat_specific_data["player_stats"][str(user_id)] = player_stats
        logger.info(f"start: Initialized new player {user_id} chat-specific stats upon /start.")
    else:
        if player_stats.get("username") != (username_from_update or first_name_from_update):
            player_stats["username"] = username_from_update or first_name_from_update
        player_stats["last_active"] = datetime.now()


    if context.args and len(context.args) > 0:
        try:
            referrer_id_from_link = int(context.args[0])
            logger.info(f"start: User {user_id} started bot with referrer ID: {referrer_id_from_link}")

            if referrer_id_from_link != user_id and global_user_info["referred_by"] is None:
                 global_user_info["pending_referrer_id"] = referrer_id_from_link
                 logger.info(f"start: Stored pending_referrer_id {referrer_id_from_link} for user {user_id} in global_user_data.")
            elif referrer_id_from_link == user_id:
                logger.info(f"start: User {user_id} tried self-referral via bot deep link.")
                if update.effective_chat.type == "private":
                    user_display_name = await _get_user_display_name(context, user_id)
                    await update.message.reply_text(
                        f"*😅 {_escape_text_for_markdown(user_display_name)} ရေ၊ ကိုယ့်ကိုယ်ကို ပြန်ဖိတ်လို့မရဘူးနော်။ သူငယ်ချင်းတွေကိုပဲ ဖိတ်ခေါ်လို့ရတာပါ။*",
                        parse_mode="Markdown"
                    )
            elif global_user_info["referred_by"] is not None:
                logger.info(f"start: User {user_id} already referred by {global_user_info['referred_by']}.")
                if update.effective_chat.type == "private":
                    user_display_name = await _get_user_display_name(context, user_id)
                    await update.message.reply_text(
                        f"*🤔 {user_display_name} ရေ၊ ခင်ဗျားကို တစ်ယောက်ယောက်က အရင်တုန်းက ဖိတ်ခေါ်ထားပြီးသားမို့လို့ ထပ်ပြီး Referral Points တွေ ပေးလို့မရတော့ဘူးနော်*",
                        parse_mode="Markdown"
                    )

        except ValueError:
            logger.warning(f"start: Invalid referrer ID in start parameter: {context.args[0]}")
        except Exception as e:
            logger.error(f"start: Error processing start parameter for user {user_id}: {e}", exc_info=True)

    save_data(global_data)

    custom_keyboard = [
        [KeyboardButton("ငွေထည့်မည်"), KeyboardButton("ငွေထုတ်မည်")],
        [KeyboardButton("My Wallet"), KeyboardButton("Leaderboard"), KeyboardButton("ကစားနည်း"), KeyboardButton("Share")]
    ]
    custom_keyboard_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)

    welcome_message = (
        f"🌟🎲 အန်စာဂိမ်းဆော့ကစားတဲ့ Group လေးထဲမှ ကြိုဆိုပါတယ်ရှင့် 🎉🌟\n\n"
        f"ကဲ.......ကစားပွဲလိုက်ရအောင်!!အန်စာတုံးဂိမ်းလေးရဲ့ စည်းမျဥ်းတွေက ဒီလိုပါရှင့်...🥳\n\n"
        f"✨ ဂိမ်းစည်းမျဉ်းလေးတွေ:အန်စာတုံးနှစ်လုံးလှိမ့်မှာဖြစ်ပြီး အဲ့ဒီရလဒ်ကို ခန့်မှန်းရမှာပေါ့! \n"
        f" 7 ထက်ငယ်ရင် Small 7 ထက်ကြီးရင် Big 7 ဦးဆိုရင်တော့ Lucky ဖြစ်ပြီး\n"
        f" B နဲ့ S မှာလောင်းကြေးရဲ့ နှစ်ဆ ရမှာဖြစ်ပြီး\n"
        f" Lucky မှာတော့ 5ဆကြီးများတောင် ရမှာနော်....😋🥰\n\n"
        f"💰 ဘယ်လိုလောင်းမလဲ:\n"
        f" -လောင်းကြေးထပ်ဖို့အတွက်ယခုပဲ\n"
        f" - အကြီးကိုလောင်းဖို့ B 100 အသေးကိုလောင်းမယ်ဆိုရင် S 250 Lucky ကိုလောင်းဖို့အတွက်ကတော့ L 100\n"
        f" (B/S/L အနောက်က နံပတ်တွေကမိမိရဲ့လောင်းကြေးဖြစ်တာကြောင့်လိုသလိုပြုပြင်နိုင်ပါတယ်ရှင်❤️) \n\n"
        f"📊 သုံးလို့ရတဲ့ အမိန့်တွေ:\n"
        f" - /mywallet ကိုနှိပ်ပြီး မိမိရဲ့လက်ကျန်ငွေနဲ့ အချက်အလက်တွေအားလုံးစစ်ဆေးလို့ရတယ်နော်...🌷\n"
        f" - /leaderboard ကိုနှိပ်ပြီး ဒီGroupထဲက အနိုင်ရရှိမှုအများဆုံးကစားသမားတွေကို ကြည့်လိုက်ရအောင်.....🌷\n"
        f" - /history: မကြာသေးခင်က ပွဲစဉ်ရလဒ်လေးတွေ ပြန်ကြည့်ဖို့ပါ။\n"
        f" - /share: သင့်သူငယ်ချင်းတွေကို ဖိတ်ခေါ်ပြီး Referral Points တွေရယူလိုက်ပါ။\n\n"
        f"ကဲ... ကံတရားက သင့်ဘက်မှာ အမြဲရှိပါစေရှင့်! 😉"
    )

    await update.message.reply_text(
        f"*{welcome_message}*",
        parse_mode="Markdown",
        reply_markup=custom_keyboard_markup
    )

    if update.effective_chat.type == "private":
        group_link_message = (
            f"👉 ကျွန်တော်တို့ရဲ့ အန်စာတုံးဂိမ်း Group ထဲကို ဝင်ရောက်ဖို့ ဒီ Link ကို နှိပ်ပါ: \n"
            f"{MAIN_GAME_GROUP_LINK}\n\n"
            f"Group ထဲရောက်ရင် ဂိမ်းစဖို့ Admin ကိုပြောပြီး ကစားလို့ရပါပြီရှင့်!"
        )
        await update.message.reply_text(f"*{group_link_message}*", parse_mode="Markdown")
        logger.info(f"start: Sent group link to user {user_id} in private chat.")

# --- UPDATED: manual_refill command handler ---
async def manual_refill(update: Update, context):
    """
    Admin command to manually refill points for admins in the current chat.
    If replying to an admin, refills only that admin's points.
    Otherwise, refills points for all admins in the chat.
    Restricted to SUPER_ADMINS.
    """
    chat_id = update.effective_chat.id
    if not isinstance(chat_id, int): return

    if chat_id not in ALLOWED_GROUP_IDS:
        await update.message.reply_text(f"*Sorry, this bot is not authorized to run in this group ({_escape_text_for_markdown(str(chat_id))}).*", parse_mode="Markdown")
        return

    requester_user_id = update.effective_user.id
    requester_username = update.effective_user.username
    requester_first_name = update.effective_user.first_name

    # Check if the user is a super admin
    if requester_user_id not in SUPER_ADMINS:
        logger.warning(f"manual_refill: User {requester_user_id} is not a super admin and tried to use /refill in chat {chat_id}.")
        return await update.message.reply_text("*❌ Only a Super Admin can use this command.*", parse_mode="Markdown")

    target_admin_id = None
    target_admin_display_name = None

    if update.message.reply_to_message:
        # If replying to a message, refill only that admin's points
        target_admin_id = update.message.reply_to_message.from_user.id
        target_admin_display_name = await _get_user_display_name(context, target_admin_id)

        # Check if the replied-to user is actually an admin in this chat
        if not await is_admin(chat_id, target_admin_id, context):
            logger.warning(f"manual_refill: Super admin {requester_user_id} tried to refill non-admin {target_admin_id} in chat {chat_id}.")
            return await update.message.reply_text(f"*❌ {_escape_text_for_markdown(target_admin_display_name)} က Admin မဟုတ်ပါဘူးရှင့်။ Admin တွေပဲ Refill လုပ်လို့ရတာပါ။*", parse_mode="Markdown")

        logger.info(f"manual_refill: Super admin {requester_user_id} initiating refill for replied admin {target_admin_id} in chat {chat_id}.")

        admin_data_for_chat = get_admin_data(target_admin_id, chat_id, username=update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name)

        admin_data_for_chat["points"] = ADMIN_INITIAL_POINTS
        admin_data_for_chat["last_refill"] = datetime.now(pytz.utc)

        save_data(global_data)

        await update.message.reply_text(
            f"*✅ Refill Successful ✅\n\n"
            f"👑 {target_admin_display_name} ၏ Admin Wallet ကို {ADMIN_INITIAL_POINTS:,} points ဖြည့်ပေးလိုက်ပါပြီ။*",
            parse_mode="Markdown"
        )
        logger.info(f"manual_refill: Successfully refilled points for replied admin {target_admin_id} in chat {chat_id}.")

    else:
        # If not replying to a message, refill all admins in the current chat
        logger.info(f"manual_refill: Super admin {requester_user_id} initiating refill for all admins in chat {chat_id}.")

        chat_admins_to_refill = await get_admins_from_chat(chat_id, context)
        refilled_admins_count = 0
        refilled_admin_names = []

        for admin_id in chat_admins_to_refill:
            if admin_id == context.bot.id: # Don't try to refill the bot's own points
                continue

            admin_data_for_chat = get_admin_data(admin_id, chat_id)
            admin_data_for_chat["points"] = ADMIN_INITIAL_POINTS
            admin_data_for_chat["last_refill"] = datetime.now(pytz.utc)
            refilled_admins_count += 1
            refilled_admin_names.append(await _get_user_display_name(context, admin_id))
            logger.debug(f"Refilled points for admin {admin_id} in chat {chat_id}.")

        save_data(global_data)

        if refilled_admins_count > 0:
            await update.message.reply_text(
                f"*✅ Refill Successful ✅\n\n"
                f"👑 ဒီ Chat ထဲက Admin {refilled_admins_count} ယောက်ရဲ့ Admin Wallet ကို {ADMIN_INITIAL_POINTS:,} points စီ ဖြည့်ပေးလိုက်ပါပြီ။\n\n"
                f"ဖြည့်ပေးလိုက်သော Admin များ: {', '.join(refilled_admin_names)}*",
                parse_mode="Markdown"
            )
            logger.info(f"manual_refill: Successfully refilled points for {refilled_admins_count} admins in chat {chat_id}.")
        else:
            await update.message.reply_text(
                f"*ℹ️ ဒီ Chat ထဲမှာ ဖြည့်ပေးလို့ရမယ့် Admin တွေ ရှာမတွေ့ပါဘူးရှင့်။ Bot က ဒီ Chat ရဲ့ Admin List ကို မှန်ကန်စွာ ယူနိုင်တာ သေချာလား စစ်ပေးပါဦးနော်။*",
                parse_mode="Markdown"
            )
            logger.warning(f"manual_refill: No admins found to refill in chat {chat_id}.")
