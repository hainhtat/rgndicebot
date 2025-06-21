# RGN Dice Bot

A Telegram bot for playing dice games with betting functionality.

## Features

- Dice rolling game with betting on Big, Small, or Lucky numbers
- User wallet system with points
- Referral system with bonus points
- Admin management system
- Leaderboard functionality
- Game history tracking

## Project Structure

```
├── main.py                 # Bot initialization and command registration
├── config/
│   ├── __init__.py         # Package initialization
│   ├── constants.py        # Game constants and configuration
│   └── settings.py         # Environment variables and settings
├── data/
│   ├── __init__.py         # Package initialization
│   ├── file_manager.py     # Data persistence functions
│   └── models.py           # Data models and structures
├── game/
│   ├── __init__.py         # Package initialization
│   └── game_logic.py       # Game mechanics and betting logic
├── handlers/
│   ├── __init__.py         # Package initialization and handler exports
│   ├── admin_handlers.py   # Admin-specific command handlers
│   ├── bet_handlers.py     # Betting-related command handlers
│   ├── game_handlers.py    # Game-related command handlers
│   ├── user_handlers.py    # User-related command handlers
│   └── utils.py            # Utility functions for handlers
├── utils/
│   ├── __init__.py         # Package initialization
│   ├── formatting.py       # Text formatting utilities
│   ├── telegram_utils.py   # Telegram-specific utility functions
│   └── user_utils.py       # User data management utilities
├── data.json               # Persistent data storage
├── requirements.txt        # Project dependencies
└── .env                    # Environment variables
```

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up your environment variables in `.env`
4. Run the bot: `python main.py`

## Commands

- `/start` - Start the bot and get instructions
- `/roll` - Start a new dice game
- `/mywallet` - Check your wallet balance
- `/leaderboard` - View the leaderboard
- `/history` - View game history
- `/share` - Get a referral link

## Admin Commands

- `/adjustscore` - Adjust a user's score
- `/checkscore` - Check a user's score
- `/refreshadmins` - Refresh the admin list
- `/stopgame` - Stop the current game
- `/adminwallets` - View admin wallets
- `/refill` - Refill admin points