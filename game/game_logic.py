import random
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from config.settings import USE_DATABASE
from database.adapter import db_adapter

# Import configuration and logging utilities
from config.config_manager import get_config
from utils.logging_utils import get_logger
from utils.error_handler import BotError, GameStateError, InvalidBetError
from utils.message_formatter import format_insufficient_funds

# Import constants
from config.constants import (
    GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER,
    BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY,
    DEFAULT_BIG_MULTIPLIER, DEFAULT_SMALL_MULTIPLIER, DEFAULT_LUCKY_MULTIPLIER,
    DEFAULT_MIN_BET, DEFAULT_MAX_BET, DEFAULT_IDLE_GAME_LIMIT,
    get_chat_data_for_id
)

# Import from utils
from utils.user_utils import get_or_create_global_user_data

from config.settings import REFERRAL_POINTS_BET_RATIO, MIN_MAIN_SCORE_REQUIRED

# Get logger for this module
logger = get_logger(__name__)

# Get configuration
config = get_config()


def save_data_unified(global_data: Dict) -> None:
    """Unified data saving function that uses database when enabled."""
    # Import the proper save function from main
    from main import save_data_unified as main_save_data_unified
    main_save_data_unified(global_data)


class DiceGame:
    """Class representing a dice game instance for a specific chat."""

    def __init__(self, match_id: int, chat_id: int):
        """Initialize a new dice game."""
        self.match_id = match_id
        self.chat_id = chat_id
        self.state = GAME_STATE_WAITING
        self.bets = {BET_TYPE_BIG: {}, BET_TYPE_SMALL: {}, BET_TYPE_LUCKY: {}}
        self.participants = set()
        self.result = None
        self.created_at = datetime.now()

        # Get configuration values
        self.min_bet = config.get("game", "min_bet", DEFAULT_MIN_BET)
        self.max_bet = config.get("game", "max_bet", DEFAULT_MAX_BET)
        self.big_multiplier = config.get(
            "game", "big_multiplier", DEFAULT_BIG_MULTIPLIER)
        self.small_multiplier = config.get(
            "game", "small_multiplier", DEFAULT_SMALL_MULTIPLIER)
        self.lucky_multiplier = config.get(
            "game", "lucky_multiplier", DEFAULT_LUCKY_MULTIPLIER)

        logger.info(
            f"New game created: match_id={match_id}, chat_id={chat_id}")

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the game."""
        return {
            "match_id": self.match_id,
            "chat_id": self.chat_id,
            "state": self.state,
            "bets": self.bets,
            "participants": list(self.participants),
            "result": self.result,
            "created_at": self.created_at,
            "min_bet": self.min_bet,
            "max_bet": self.max_bet
        }


def place_bet(
        game: DiceGame,
        user_id: int,
        username: str,
        bet_type: str,
        amount: int,
        chat_data: Dict,
        global_data: Dict,
        chat_id: int) -> str:
    """Place a bet for a player in the current game.
    
    Args:
        game: The current DiceGame instance
        user_id: The Telegram user ID of the player
        username: The Telegram username of the player
        bet_type: The type of bet (BIG, SMALL, or LUCKY)
        amount: The amount to bet
        chat_data: The chat-specific data dictionary
        global_data: The global data dictionary
        chat_id: The Telegram chat ID
        
    Returns:
        A message indicating the result of the bet placement
        
    Raises:
        GameStateError: If the game is not in the GAME_STATE_WAITING state
        InvalidBetError: If the bet amount is invalid
    """
    # Check if the game is in the correct state
    if game.state != GAME_STATE_WAITING:
        logger.warning(f"Bet attempt in invalid game state: {game.state} by user {user_id}")
        raise GameStateError("Betting is currently closed.")
    
    # Normalize bet type to uppercase
    bet_type = bet_type.upper()
    
    # Validate bet type
    if bet_type not in [BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY]:
        logger.warning(f"Invalid bet type: {bet_type} by user {user_id}")
        raise InvalidBetError(f"Invalid bet type: {bet_type}")
    
    # Validate bet amount
    if amount < game.min_bet:
        logger.warning(f"Bet amount too small: {amount} (min: {game.min_bet}) by user {user_id}")
        raise InvalidBetError(f"Minimum bet amount is {game.min_bet}.")
    
    if amount > game.max_bet:
        logger.warning(f"Bet amount too large: {amount} (max: {game.max_bet}) by user {user_id}")
        raise InvalidBetError(f"Maximum bet amount is {game.max_bet}.")
    
    # Get or initialize player stats
    if USE_DATABASE:
        chat_data_db = get_chat_data_for_id(chat_id)
        player_stats = chat_data_db.get("player_stats", {})
    else:
        if "player_stats" not in chat_data:
            chat_data["player_stats"] = {}
        player_stats = chat_data["player_stats"]

    # Get or create player stats
    if USE_DATABASE:
        try:
            current_player = db_adapter.get_or_create_player_stats(
                user_id, chat_id, username)
            # Update the local player_stats dict for consistency
            if "player_stats" not in chat_data:
                chat_data["player_stats"] = {}
            chat_data["player_stats"][str(user_id)] = current_player
            player_stats = chat_data["player_stats"]
        except Exception as db_error:
            logger.error(
                f"Database error getting player stats for user {user_id}: {db_error}")
            # Fallback to local data
            if str(user_id) not in player_stats:
                new_player_data = {
                    "username": username,
                    "score": config.get('user', 'new_user_bonus', 0),
                    "total_bets": 0,
                    "total_wins": 0,
                    "total_losses": 0,
                    "last_active": datetime.now().isoformat()
                }
                chat_data["player_stats"][str(user_id)] = new_player_data
                player_stats[str(user_id)] = new_player_data
            current_player = player_stats[str(user_id)]
    else:
        # Create new player if doesn't exist
        if str(user_id) not in player_stats:
            new_player_data = {
                "username": username,
                "score": config.get('user', 'new_user_bonus', 0),
                "total_bets": 0,
                "total_wins": 0,
                "total_losses": 0,
                "last_active": datetime.now().isoformat()
            }
            chat_data["player_stats"][str(user_id)] = new_player_data
            player_stats[str(user_id)] = new_player_data

        # Get current player data
        current_player = player_stats[str(user_id)]

    # Ensure all required keys exist in current player data
    if "total_bets" not in current_player:
        current_player["total_bets"] = 0
    if "total_wins" not in current_player:
        current_player["total_wins"] = 0
    if "total_losses" not in current_player:
        current_player["total_losses"] = 0

    # Update username if it has changed
    if current_player["username"] != username and username:
        current_player["username"] = username

    # Get global user data for referral points and bonus points
    global_user_data = get_or_create_global_user_data(user_id, username=username)
    
    # Calculate funds already committed to bets in this game
    user_id_str = str(user_id)
    committed_funds = 0
    for bet_type_key, bets in game.bets.items():
        if user_id_str in bets:
            committed_funds += bets[user_id_str]
    
    # Calculate available funds
    if USE_DATABASE:
        main_score = db_adapter.get_player_score(user_id, chat_id)
        referral_points = db_adapter.get_user_referral_points(user_id)
        bonus_points = db_adapter.get_user_bonus_points(user_id)
    else:
        main_score = current_player["score"]
        referral_points = global_user_data.get("referral_points", 0)
        bonus_points = global_user_data.get("bonus_points", 0)
    
    total_available = main_score + referral_points + bonus_points - committed_funds
    
    if total_available < amount:
        logger.warning(
            f"Insufficient funds: {total_available} < {amount} for user {user_id}")
        insufficient_message = format_insufficient_funds(
            main_score, referral_points, bonus_points, amount, committed_funds)
        raise InvalidBetError(insufficient_message)
    
    original_amount = amount
    
    # Initialize usage counters
    referral_points_used = 0
    bonus_points_used = 0
    main_score_used = 0
    
    # Use bonus points first (no restrictions)
    if bonus_points > 0:
        bonus_points_used = min(bonus_points, amount)
        if USE_DATABASE:
            db_adapter.update_user_bonus_points(
                user_id, bonus_points - bonus_points_used)
        else:
            global_user_data["bonus_points"] -= bonus_points_used
        amount -= bonus_points_used
    
    # Use referral points if needed
    # Assuming can_use_referral is True and max_referral_for_bet is defined as
    # amount * REFERRAL_POINTS_BET_RATIO
    max_referral_for_bet = int(amount * REFERRAL_POINTS_BET_RATIO)
    if amount > 0 and referral_points > 0:
        if main_score < MIN_MAIN_SCORE_REQUIRED:
            if main_score < amount:
                if USE_DATABASE:
                    db_adapter.update_user_bonus_points(
                        user_id, bonus_points + bonus_points_used)
                else:
                    global_user_data["bonus_points"] += bonus_points_used
                raise InvalidBetError(
                    format_insufficient_funds(
                        main_score,
                        referral_points,
                        bonus_points,
                        amount,
                        committed_funds))
            main_score_used = amount
            amount = 0
        else:
            referral_points_used = min(
                referral_points, max_referral_for_bet, amount)
            if USE_DATABASE:
                db_adapter.update_user_referral_points(
                    user_id, referral_points - referral_points_used)
            else:
                global_user_data["referral_points"] -= referral_points_used
            amount -= referral_points_used
    
    # Use main score for remaining amount
    if amount > 0:
        if main_score < amount:
            # Restore used points if main score is insufficient
            if USE_DATABASE:
                db_adapter.update_user_bonus_points(
                    user_id, bonus_points + bonus_points_used)
                db_adapter.update_user_referral_points(
                    user_id, referral_points + referral_points_used)
            else:
                global_user_data["bonus_points"] += bonus_points_used
                global_user_data["referral_points"] += referral_points_used
            raise InvalidBetError(
                f"Insufficient main score. Need {amount} more main score ကျပ်.")
        else:
            main_score_used = amount
            # Note: Score deduction will be handled by database update below if
            # USE_DATABASE is True
            if not USE_DATABASE:
                current_player["score"] -= main_score_used
    
        # Restore original bet amount for logging
        original_amount = bonus_points_used + referral_points_used + main_score_used
    
        # Add the bet to the game
        user_id_str = str(user_id)
    
        # If player already bet on this type, add to their existing bet
        if user_id_str in game.bets[bet_type]:
            game.bets[bet_type][user_id_str] += original_amount
        else:
            game.bets[bet_type][user_id_str] = original_amount
    
        # Add player to participants set
        game.participants.add(user_id_str)
    
        # Update player stats
        current_player["total_bets"] += 1
        current_player["last_active"] = datetime.now().isoformat()
    
        # Log the bet
        logger.info(f"Bet placed: user={user_id}, type={bet_type}, amount={original_amount}, "
                    f"bonus_points_used={bonus_points_used}, referral_points_used={referral_points_used}, main_score_used={main_score_used}")
    
        # Construct response message
        source_parts = []
        if bonus_points_used > 0:
            source_parts.append(f"{bonus_points_used} bonus")
        if referral_points_used > 0:
            source_parts.append(f"{referral_points_used} referral")
        if main_score_used > 0:
            source_parts.append(f"{main_score_used} main")
    
        source_msg = f"(Used {', '.join(source_parts)} ကျပ်)" if source_parts else ""
    
        # Update database if using database mode
        if USE_DATABASE:
            try:
                # Update player score in database (deduct bet amount)
                db_adapter.update_player_stats(
                    user_id, chat_id, -main_score_used, False, 0)
    
                # Get fresh player data from database to sync local data
                updated_stats = db_adapter.get_or_create_player_stats(
                    user_id, chat_id, username)
                current_player.update({
                    "score": updated_stats["score"],
                    "total_wins": updated_stats["total_wins"],
                    "total_losses": updated_stats["total_losses"],
                    "total_bets": updated_stats["total_bets"]
                })
    
                # Get fresh global points
                global_user_data["referral_points"] = db_adapter.get_user_referral_points(
                    user_id)
                global_user_data["bonus_points"] = db_adapter.get_user_bonus_points(
                    user_id)
    
                # Store bet record in database
                from database.queries import create_bet, get_active_game, create_game
    
                # Get or create game record in database
                db_game = get_active_game(chat_id)
                if not db_game:
                    db_game = create_game(game.match_id, chat_id)
    
                # Create bet record
                create_bet(
                    db_game['id'],
                    user_id,
                    bet_type,
                    original_amount,
                    referral_points_used)
    
                logger.info(
                    f"Database updated for bet: user={user_id}, game_id={
                        db_game['id']}, amount={original_amount}")
    
            except Exception as db_error:
                logger.error(
                    f"Database error during bet placement for user {user_id}: {db_error}")
                # Fallback: deduct from local data if database update failed
                current_player["score"] -= main_score_used
                logger.info(
                    f"Fallback to local deduction: {main_score_used} for user {user_id}")
    
        # Save data to persist the changes
        save_data_unified(global_data)
    
        bet_message = (
            f"✅ Bet placed: {bet_type} {original_amount} {source_msg}\n"
            f"Your balance: {current_player['score']} main, "
            f"{global_user_data.get('referral_points', 0)} referral, "
            f"{global_user_data.get('bonus_points', 0)} bonus ကျပ်"
        )
        return bet_message
    
    
def payout(
        game: DiceGame,
        chat_data: Dict,
        global_data: Dict,
        chat_id: int) -> Dict:
    """Process payouts for a completed game.

    Args:
        game: The completed DiceGame instance
        chat_data: The chat-specific data dictionary
        global_data: The global data dictionary
        chat_id: The chat ID for database operations

    Returns:
        A dictionary containing game summary information
    """
    if game.state != GAME_STATE_CLOSED or game.result is None:
        logger.error(
            f"Cannot process payout: game state={
                game.state}, result={
                game.result}")
        raise GameStateError(
            "Cannot process payout for a game that is not closed or has no result.")

    # Calculate the sum of the dice
    dice_sum = sum(game.result)

    # Determine the winning bet type
    if dice_sum <= 6:
        winning_bet_type = BET_TYPE_SMALL
        multiplier = game.small_multiplier
    elif dice_sum >= 8:
        winning_bet_type = BET_TYPE_BIG
        multiplier = game.big_multiplier
    else:  # dice_sum == 7
        winning_bet_type = BET_TYPE_LUCKY
        multiplier = game.lucky_multiplier

    # Initialize counters for summary
    total_bets = sum(sum(bets.values()) for bets in game.bets.values())
    total_winners = 0
    total_losers = 0
    total_payout = 0
    winners_list = []
    losers_list = []

    # Collect all participants and calculate their net result
    participant_results = {}

    # Calculate net result for each participant
    for user_id_str in game.participants:
        user_id = int(user_id_str)
        total_bet_amount = 0
        total_winnings = 0
        individual_bets = []

        # Calculate total bets and winnings for this user
        for bet_type, bets in game.bets.items():
            if user_id_str in bets:
                bet_amount = bets[user_id_str]
                total_bet_amount += bet_amount

                # Calculate winnings/loss for this specific bet
                if bet_type == winning_bet_type:
                    bet_winnings = int(bet_amount * multiplier)
                    total_winnings += bet_winnings
                    individual_bets.append({
                        "bet_type": bet_type,
                        "amount": bet_amount,
                        "result": "win",
                        "payout": bet_winnings,
                        "net": bet_winnings - bet_amount
                    })
                else:
                    individual_bets.append({
                        "bet_type": bet_type,
                        "amount": bet_amount,
                        "result": "loss",
                        "payout": 0,
                        "net": -bet_amount
                    })

        # Calculate net result
        # Since bet amounts were already deducted during bet placement,
        # we only need to add winnings for winners
        # For losers, net_result is 0 (they already lost their bet during
        # placement)
        display_net = total_winnings - total_bet_amount
        update_amount = total_winnings

        participant_results[user_id_str] = {
            "user_id": user_id,
            "total_bet_amount": total_bet_amount,
            "total_winnings": total_winnings,
            "net_result": display_net,
            "individual_bets": individual_bets
        }

    # Process each participant's result
    for user_id_str, result in participant_results.items():
        user_id = result["user_id"]
        net_result = result["net_result"]
        total_bet_amount = result["total_bet_amount"]
        total_winnings = result["total_winnings"]

        if USE_DATABASE:
            # Update player stats in database
            is_winner = display_net > 0
            try:
                # Update database first
                db_adapter.update_player_stats(
                    user_id, chat_id, update_amount, is_winner, 1)

                # Get fresh player data from database
                updated_stats = db_adapter.get_or_create_player_stats(
                    user_id, chat_id)

                # Update local chat_data to stay in sync
                if "player_stats" not in chat_data:
                    chat_data["player_stats"] = {}

                chat_data["player_stats"][user_id_str] = {
                    "username": updated_stats["username"],
                    "score": updated_stats["score"],
                    "total_wins": updated_stats["total_wins"],
                    "total_losses": updated_stats["total_losses"],
                    "total_bets": updated_stats["total_bets"],
                    "last_active": updated_stats["last_active"]
                }

                player = chat_data["player_stats"][user_id_str]

                # Note: Bet records are already created during bet placement
                # No need to create them again during payout

            except Exception as db_error:
                logger.error(
                    f"Database error during payout for user {user_id}: {db_error}")
                # Fallback to local data update
                if user_id_str in chat_data.get("player_stats", {}):
                    player = chat_data["player_stats"][user_id_str]
                    player["score"] += update_amount

                    if display_net > 0:
                        player["total_wins"] += 1
                    else:
                        player["total_losses"] += 1
                else:
                    # Create minimal player data if not exists
                    player = {
                        "username": "Unknown",
                        "score": update_amount,
                        "total_wins": 1 if display_net > 0 else 0,
                        "total_losses": 0 if display_net > 0 else 1,
                        "total_bets": 1,
                        "last_active": datetime.now().isoformat()
                    }
                    if "player_stats" not in chat_data:
                        chat_data["player_stats"] = {}
                    chat_data["player_stats"][user_id_str] = player
        # Get user's full name from global data if available
        user_global_data = global_data.get("users", {}).get(user_id_str, {})
        full_name = user_global_data.get("full_name", "")

        # Add to appropriate list based on net result
        individual_bets = result["individual_bets"]
        if display_net > 0:
            winners_list.append({
                "user_id": user_id_str,
                "username": player["username"],
                "bet_amount": total_bet_amount,
                "winnings": total_winnings,
                "net_result": display_net,
                "wallet_balance": player["score"],
                "individual_bets": individual_bets
            })
            total_winners += 1
            total_payout += total_winnings
        elif display_net < 0:
            losers_list.append({
                "user_id": user_id_str,
                "username": player["username"],
                "display_name": full_name or player["username"],
                "bet_amount": total_bet_amount,
                "net_result": display_net,
                "wallet_balance": player["score"],
                "individual_bets": individual_bets
            })
            total_losers += 1
        # If net_result == 0, user breaks even and doesn't appear in winners or
        # losers

    # Update game state to indicate game is completely finished
    game.state = GAME_STATE_OVER

    # Record match in history (limited to last 50 matches)
    if "match_history" not in chat_data:
        chat_data["match_history"] = []

    # Create dice result for display
    dice1, dice2 = game.result
    dice_sum = dice1 + dice2

    match_record = {
        "match_id": game.match_id,
        "timestamp": datetime.now().isoformat(),
        "result": game.result,
        "dice_result": (dice1, dice2),
        "winning_type": winning_bet_type,
        "total_bets": total_bets,
        "total_winners": total_winners,
        "total_losers": total_losers,
        "total_payout": total_payout,
        "total_won": total_payout,
        "total_lost": total_bets - total_payout
    }

    chat_data["match_history"].append(match_record)

    # Keep only the last 50 matches
    if len(chat_data["match_history"]) > 50:
        chat_data["match_history"] = chat_data["match_history"][-50:]

    # Update consecutive idle matches counter
    if total_bets == 0:
        chat_data["consecutive_idle_matches"] = chat_data.get(
            "consecutive_idle_matches", 0) + 1
    else:
        chat_data["consecutive_idle_matches"] = 0

    # Save data
    save_data_unified(global_data)

    # Log the game result
    logger.info(f"Game completed: match_id={game.match_id}, result={game.result}, "
                f"winning_type={winning_bet_type}, total_bets={total_bets}, "
                f"total_payout={total_payout}, winners={total_winners}, losers={total_losers}")

    # Return game summary
    dice1, dice2 = game.result

    # Use simple string representations since actual dice animation is handled
    # by Telegram
    dice1_str = str(dice1)
    dice2_str = str(dice2)

    return {
        "match_id": game.match_id,
        "result": game.result,
        "dice_values": (
            dice1,
            dice2),
        "dice_sum": dice_sum,
        "dice_result": f"{dice1_str} + {dice2_str} = {dice_sum}",
        "winning_type": winning_bet_type,
        "multiplier": multiplier,
        "total_bets": total_bets,
        "total_winners": total_winners,
        "total_losers": total_losers,
        "total_payout": total_payout,
        "winners": winners_list,
        "losers": losers_list,
        "consecutive_idle_matches": chat_data.get(
            "consecutive_idle_matches",
            0)}


def roll_dice(game: DiceGame) -> Tuple[int, int]:
    """Roll two dice and set the result in the game.

    Args:
        game: The current DiceGame instance

    Returns:
        A tuple containing the two dice values
    """
    # Roll two dice
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)

    # Set the result
    game.result = (dice1, dice2)

    logger.info(f"Dice rolled: {dice1}, {dice2} for match_id={game.match_id}")

    return (dice1, dice2)


def close_betting(game: DiceGame) -> None:
    """Close betting for the current game.

    Args:
        game: The current DiceGame instance
    """
    if game.state == GAME_STATE_WAITING:
        game.state = GAME_STATE_CLOSED
        game.closed_at = datetime.now()  # Add timestamp when betting is closed
        logger.info(f"Betting closed for match_id={game.match_id}")
    else:
        logger.warning(
            f"Attempted to close betting for game in state {
                game.state}")


def get_status(game: DiceGame) -> Dict:
    """Get the current status of the game.

    Args:
        game: The current DiceGame instance

    Returns:
        A dictionary containing the current game status
    """
    # Calculate total bets for each type
    big_total = sum(game.bets[BET_TYPE_BIG].values())
    small_total = sum(game.bets[BET_TYPE_SMALL].values())
    lucky_total = sum(game.bets[BET_TYPE_LUCKY].values())

    return {
        "match_id": game.match_id,
        "state": game.state,
        "participants": len(game.participants),
        "big_total": big_total,
        "small_total": small_total,
        "lucky_total": lucky_total,
        "result": game.result,
        "created_at": game.created_at.isoformat()
    }
