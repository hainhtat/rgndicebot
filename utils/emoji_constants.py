# Emoji constants used throughout the application

# Game result emojis
GAME_EMOJIS = {
    "big": "🎲",
"small": "🎯",
"lucky": "🍀"
}

# Status emojis
STATUS_EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "time": "⏱️",
    "locked": "🔒",
    "finished": "🏁"
}

# Feature emojis
FEATURE_EMOJIS = {
    "dice": "🎲",
    "wallet": "💰",
    "leaderboard": "🏆",
    "history": "📜",
    "help": "❓",
    "deposit": "💵",
    "withdraw": "💸",
    "share": "🔗",
    "admin": "👑"
}

# Betting emojis
BET_EMOJIS = {
    "big": "🎲",
    "small": "🎯",
    "lucky": "🍀",
    "payout": "💰"
}

# Keyboard button emojis
KEYBOARD_EMOJIS = {
    "wallet": "💰",
    "leaderboard": "🏆",
    "deposit": "💵",
    "withdraw": "💸",
    "help": "❓",
    "share": "🔗"
}

# Note: Dice emojis are now handled by Telegram's native dice animation
# The bot uses context.bot.send_dice() and extracts values from dice_msg.dice.value