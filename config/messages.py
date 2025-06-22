"""Message constants for the dice bot."""

# Error messages
ERROR_SELF_REFERRAL = "❌ You cannot refer yourself."
ERROR_USER_DATA_CREATION = "❌ Your user data could not be created. Please try again later."
ERROR_REFERRER_NOT_FOUND = "❌ The referrer's data could not be found. Invalid referral link."
ERROR_ALREADY_REFERRED = "❌ You have already been referred by someone else."
ERROR_CHAT_DATA_NOT_FOUND = "❌ Chat data not found."
ERROR_PLAYER_NOT_FOUND = "❌ Player not found in this chat."

# Success messages
SUCCESS_REFERRAL_WELCOME = (
    "🎉 *Welcome to RGN Dice Bot!* 🎉\n\n"
    "✨ You've been invited by *{referrer_name}* to join the fun!\n\n"
    "🎮 *Next Step:* Join our main gaming group to start playing\n"
    "🎁 *Bonus:* Both you and your friend will earn rewards!\n"
    "🚀 *Ready to roll the dice and win big?*"
)

SUCCESS_REFERRAL_BONUS = (
    "🎉 *Referral Bonus Received!*\n\n"
    "👤 *{user_name}* has joined the main group!\n"
    "💰 You've received a *{bonus_points} ကျပ်* bonus for this referral.\n"
    "💵 Your total referral ကျပ်: *{total_points}*"
)

SUCCESS_POINTS_ADDED = "✅ Added {amount} ကျပ် to {username}. New score: {score}"
SUCCESS_POINTS_DEDUCTED = "✅ Deducted {amount} ကျပ် from {username}. New score: {score}"
SUCCESS_WELCOME_BONUS = "🎉 Welcome bonus of {bonus_points} ကျပ် awarded!"

# Info messages
INFO_WELCOME_BONUS_ALREADY_RECEIVED = "Welcome bonus already received"

# Fallback names
FALLBACK_USER_NAME = "User {user_id}"
FALLBACK_USERNAME_DISPLAY = "@{username}"
FALLBACK_FULL_NAME_USERNAME = "{full_name} (@{username})"