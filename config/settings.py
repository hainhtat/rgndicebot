import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")

# Timezone settings
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Yangon")  # Default timezone

# Game settings
INITIAL_PLAYER_SCORE = int(os.environ.get("INITIAL_PLAYER_SCORE", "0"))  # Starting score for new players
ADMIN_INITIAL_POINTS = int(os.environ.get("ADMIN_INITIAL_POINTS", "10000000"))  # Starting points for admins
REFERRAL_BONUS_POINTS = int(os.environ.get("REFERRAL_BONUS_POINTS", "500"))  # Points awarded for referrals
WELCOME_BONUS_POINTS = int(os.environ.get("WELCOME_BONUS_POINTS", "500"))  # Welcome bonus for new group members

# Data file path
DATA_FILE_PATH = os.environ.get("DATA_FILE_PATH", "data.json")

# Main game group link
# This should be updated to the appropriate group link
MAIN_GAME_GROUP_LINK = os.environ.get("MAIN_GAME_GROUP_LINK", "https://t.me/dicetestmm")

# Hardcoded admin IDs
HARDCODED_ADMINS = [
    1599213796,
    # 1176326151
]  # Add your admin IDs here

# Try to load admin IDs from environment variable
env_admins = os.environ.get("HARDCODED_ADMINS", "")
if env_admins:
    try:
        HARDCODED_ADMINS = [int(admin_id.strip()) for admin_id in env_admins.split(",") if admin_id.strip()]
    except ValueError as e:
        print(f"Error parsing HARDCODED_ADMINS from environment: {e}")

# Super admin IDs
SUPER_ADMINS = [1599213796]  # Add super admin IDs here

# Try to load super admin IDs from environment variable
env_super_admins = os.environ.get("SUPER_ADMINS", "")
if env_super_admins:
    try:
        SUPER_ADMINS = [int(admin_id.strip()) for admin_id in env_super_admins.split(",") if admin_id.strip()]
    except ValueError as e:
        print(f"Error parsing SUPER_ADMINS from environment: {e}")

# Allowed group IDs
ALLOWED_GROUP_IDS = [
    -1002780424700, #test group
    # -1002689980361, #main gp
]  # Add allowed group IDs here

# Try to load allowed group IDs from environment variable
env_groups = os.environ.get("ALLOWED_GROUP_IDS", "")
if env_groups:
    try:
        ALLOWED_GROUP_IDS = [int(group_id.strip()) for group_id in env_groups.split(",") if group_id.strip()]
    except ValueError as e:
        print(f"Error parsing ALLOWED_GROUP_IDS from environment: {e}")

# Try to load allowed group IDs from file
try:
    with open("groups.txt", "r") as f:
        for line in f:
            try:
                group_id = int(line.strip().rstrip(","))
                if group_id not in ALLOWED_GROUP_IDS:
                    ALLOWED_GROUP_IDS.append(group_id)
            except ValueError:
                pass
except FileNotFoundError:
    pass

# Debug mode
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

# Function to load custom configuration
def load_custom_config():
    """Load custom configuration from config.json if it exists"""
    config_file = Path("config.json")
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")
    return {}

# Custom configuration (can override defaults)
CUSTOM_CONFIG = load_custom_config()