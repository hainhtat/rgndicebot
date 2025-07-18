# 🎲 RGN Dice Bot

> A feature-rich Telegram bot for playing dice games with betting functionality, wallet management, and referral system.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-Latest-blue.svg)](https://core.telegram.org/bots/api)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Features

### 🎮 Game Features
- **Dice Rolling Game**: Bet on Big (8-12), Small (2-6), or Lucky (7) outcomes
- **Real-time Betting**: Live betting with automatic game management
- **Multiple Bet Types**: Support for various betting patterns and amounts
- **Game History**: Track all game results and statistics

### 💰 Financial System
- **Multi-Wallet System**: Main wallet, referral points, and bonus points
- **Secure Transactions**: Safe betting and payout system
- **Admin Wallet Management**: Separate admin wallets with refill system
- **Automatic Payouts**: Instant winnings distribution

### 👥 User Management
- **Referral System**: Earn rewards for inviting friends
- **User Profiles**: Comprehensive user statistics and history
- **Leaderboard**: Track top players and achievements
- **Welcome Bonuses**: New user incentives

### 🛡️ Admin Features
- **Multi-level Admin System**: Super admins and regular admins
- **Score Management**: Adjust user balances with reasons
- **Game Control**: Start, stop, and manage games
- **User Monitoring**: Check user statistics and activities

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- PostgreSQL database (optional, can use JSON file storage)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dicebot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
dicebot/
├── 📄 main.py                 # Bot initialization and command registration
├── 📁 config/                 # Configuration and settings
│   ├── constants.py           # Game constants and global variables
│   ├── settings.py            # Environment variables and settings
│   └── messages.py            # Message templates and constants
├── 📁 database/               # Database layer (PostgreSQL)
│   ├── connection.py          # Database connection management
│   ├── models.py              # Database models and schemas
│   ├── adapter.py             # Database adapter for operations
│   └── migrations/            # Database migration scripts
├── 📁 data/                   # Data models and file storage
│   └── models.py              # Data structures and JSON storage
├── 📁 game/                   # Game logic and mechanics
│   └── game_logic.py          # Core game mechanics and betting logic
├── 📁 handlers/               # Telegram command handlers
│   ├── user_handlers.py       # User commands (/start, /mywallet, etc.)
│   ├── game_handlers.py       # Game commands (/roll, /help, etc.)
│   ├── bet_handlers.py        # Betting logic and validation
│   ├── admin_handlers.py      # Admin commands and management
│   ├── superadmin_handlers.py # Super admin exclusive commands
│   └── utils.py               # Handler utility functions
├── 📁 utils/                  # Utility modules
│   ├── telegram_utils.py      # Telegram-specific utilities
│   ├── message_formatter.py   # Message templates and formatting
│   ├── error_handler.py       # Error handling and logging
│   ├── user_utils.py          # User data management
│   └── formatting.py          # Text formatting utilities
├── 📁 docs/                   # Documentation
│   ├── DATABASE_SETUP.md      # Database setup guide
│   ├── LOG_MANAGEMENT_GUIDE.md # Logging configuration
│   └── [other guides...]      # Various setup and fix guides
└── 📁 tests/                  # Test files
    └── [test files...]        # Unit and integration tests
```

## 🎮 Bot Commands

### 👤 User Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot and get welcome message |
| `/help` | Show detailed game instructions |
| `/mywallet` | Check your wallet balance and statistics |
| `/leaderboard` | View top players leaderboard |
| `/history` | View your game history |
| `/share` | Get your referral link to invite friends |

### 🎲 Game Commands
| Command | Description |
|---------|-------------|
| `/roll` | Start a new dice game (admin only) |
| `/stopgame` | Stop the current game (admin only) |
| `B 500` | Bet 500 on BIG (sum 8-12) |
| `S 1000` | Bet 1000 on SMALL (sum 2-6) |
| `L 2000` | Bet 2000 on LUCKY (sum 7) |

### 👑 Admin Commands
| Command | Description |
|---------|-------------|
| `/adjustscore <user> <amount>` | Adjust user's score |
| `/checkscore <user>` | Check user's detailed information |
| `/adminwallets` | View all admin wallet balances |
| `/refill` | Refill admin points |
| `/refreshadmins` | Refresh admin list from Telegram |

### 🔧 Super Admin Commands
| Command | Description |
|---------|-------------|
| `/mygroups` | Manage bot groups and settings |
| `/refill_amount <amount>` | Set custom refill amount |

## 📚 Documentation

Detailed documentation is available in the [`docs/`](./docs/) folder:

- **[Database Setup Guide](./docs/DATABASE_SETUP.md)** - PostgreSQL setup and configuration
- **[Log Management Guide](./docs/LOG_MANAGEMENT_GUIDE.md)** - Logging configuration and management
- **[Test Usage Guide](./docs/TEST_USAGE_GUIDE.md)** - How to run tests and testing procedures
- **[Migration Guides](./docs/)** - Various migration and fix guides

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token
ALLOWED_GROUP_IDS=group_id_1,group_id_2
SUPER_ADMIN_IDS=admin_id_1,admin_id_2

# Database Configuration (optional)
USE_DATABASE=true
DATABASE_URL=postgresql://user:password@localhost/dbname

# Game Configuration
MIN_BET_AMOUNT=100
MAX_BET_AMOUNT=1000000
DEFAULT_ADMIN_POINTS=1000000
```

### Game Rules

- **Minimum Bet**: 100 ကျပ်
- **Betting Options**:
  - **BIG** (8-12): 1.95x payout
  - **SMALL** (2-6): 1.95x payout  
  - **LUCKY** (7): 4.5x payout
- **Referral Bonus**: 500 ကျပ် per successful referral
- **Welcome Bonus**: 500 ကျပ် for new users

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues or need help:

1. Check the [documentation](./docs/) for guides
2. Search existing issues in the repository
3. Create a new issue with detailed information

## 🔄 Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and updates.