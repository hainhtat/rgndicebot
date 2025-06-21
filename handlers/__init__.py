# Import all handlers to make them available from the handlers package
from handlers.admin_handlers import (
    adjust_score,
    check_user_score,
    refresh_admins,
    stop_game,
    admin_wallets,
    manual_refill
)

from handlers.bet_handlers import (
    place_bet,
    roll_dice
)

from handlers.game_handlers import (
    start_game
)

from handlers.user_handlers import (
    start_command
)

# Import the original auto_roll_dice function directly
from handlers.bet_handlers import auto_roll_dice as _original_auto_roll_dice

# Create a wrapper for auto_roll_dice that handles the context parameter properly
async def auto_roll_dice_wrapper(context):
    # Import logging here to avoid circular imports
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Call the original function with None as update (since it's a scheduled job)
        # and the provided context
        await _original_auto_roll_dice(None, context)
    except Exception as e:
        # Log any errors that occur
        logger.error(f"Error in auto_roll_dice_wrapper: {str(e)}", exc_info=True)

# Replace the imported auto_roll_dice with our wrapper
auto_roll_dice = auto_roll_dice_wrapper

# Export all handlers
__all__ = [
    # Admin handlers
    'adjust_score',
    'check_user_score',
    'refresh_admins',
    'stop_game',
    'admin_wallets',
    'manual_refill',
    
    # Bet handlers
    'start_dice',
    'handle_bet',
    'button_callback',
    'auto_roll_dice',
    
    # Game handlers
    'roll_and_announce',
    'roll_and_announce_scheduled',
    'leaderboard',
    'history',
    
    # User handlers
    'start',
    'my_wallet',
    'deposit_points',
    'withdraw_points',
    'handle_share_referral',
    'on_chat_member_update'
]