import random
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union

# Import configuration and logging utilities
from config.config_manager import get_config
from utils.logging_utils import get_logger
from utils.error_handler import BotError, GameStateError, InvalidBetError

# Import constants
from config.constants import (
    GAME_STATE_WAITING, GAME_STATE_CLOSED, GAME_STATE_OVER,
    BET_TYPE_BIG, BET_TYPE_SMALL, BET_TYPE_LUCKY,
    DEFAULT_BIG_MULTIPLIER, DEFAULT_SMALL_MULTIPLIER, DEFAULT_LUCKY_MULTIPLIER,
    DEFAULT_MIN_BET, DEFAULT_MAX_BET, DEFAULT_IDLE_GAME_LIMIT
)

# Import from utils
from utils.user_utils import get_or_create_global_user_data
from data.file_manager import save_data

# Get logger for this module
logger = get_logger(__name__)

# Get configuration
config = get_config()

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
        self.big_multiplier = config.get("game", "big_multiplier", DEFAULT_BIG_MULTIPLIER)
        self.small_multiplier = config.get("game", "small_multiplier", DEFAULT_SMALL_MULTIPLIER)
        self.lucky_multiplier = config.get("game", "lucky_multiplier", DEFAULT_LUCKY_MULTIPLIER)
        
        logger.info(f"New game created: match_id={match_id}, chat_id={chat_id}")
        
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


def place_bet(game: DiceGame, user_id: int, username: str, bet_type: str, amount: int, 
              chat_data: Dict, global_data: Dict) -> str:
    """Place a bet for a player in the current game.
    
    Args:
        game: The current DiceGame instance
        user_id: The Telegram user ID of the player
        username: The Telegram username of the player
        bet_type: The type of bet (BIG, SMALL, or LUCKY)
        amount: The amount to bet
        chat_data: The chat-specific data dictionary
        global_data: The global data dictionary
        
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
    if "player_stats" not in chat_data:
        chat_data["player_stats"] = {}
    
    if str(user_id) not in chat_data["player_stats"]:
        chat_data["player_stats"][str(user_id)] = {
            "username": username,
            "score": config.get("user", "new_user_bonus", 0),
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "last_active": datetime.now().isoformat()
        }
    
    # Ensure all required keys exist in player_stats
    player_stats = chat_data["player_stats"][str(user_id)]
    if "total_bets" not in player_stats:
        player_stats["total_bets"] = 0
    if "total_wins" not in player_stats:
        player_stats["total_wins"] = 0
    if "total_losses" not in player_stats:
        player_stats["total_losses"] = 0
    
    player_stats = chat_data["player_stats"][str(user_id)]
    
    # Update username if it has changed
    if player_stats["username"] != username and username:
        player_stats["username"] = username
    
    # Get global user data for referral points
    global_user_data = get_or_create_global_user_data(user_id, username=username)
    
    # Check if player has enough points (including referral points)
    total_available = player_stats["score"] + global_user_data.get("referral_points", 0)
    
    if total_available < amount:
        logger.warning(f"Insufficient funds: {total_available} < {amount} for user {user_id}")
        raise InvalidBetError(f"You don't have enough points. Your balance: {total_available}")
    
    # Determine which source to deduct from first (referral points first)
    referral_points_used = 0
    main_score_used = 0
    
    if global_user_data.get("referral_points", 0) > 0:
        referral_points_used = min(global_user_data["referral_points"], amount)
        global_user_data["referral_points"] -= referral_points_used
    
    # If referral points weren't enough, use main score
    if referral_points_used < amount:
        main_score_used = amount - referral_points_used
        player_stats["score"] -= main_score_used
    
    # Add the bet to the game
    user_id_str = str(user_id)
    
    # If player already bet on this type, add to their existing bet
    if user_id_str in game.bets[bet_type]:
        game.bets[bet_type][user_id_str] += amount
    else:
        game.bets[bet_type][user_id_str] = amount
    
    # Add player to participants set
    game.participants.add(user_id_str)
    
    # Update player stats
    player_stats["total_bets"] += 1
    player_stats["last_active"] = datetime.now().isoformat()
    
    # Log the bet
    logger.info(f"Bet placed: user={user_id}, type={bet_type}, amount={amount}, "
                f"referral_points_used={referral_points_used}, main_score_used={main_score_used}")
    
    # Construct response message
    if referral_points_used > 0 and main_score_used > 0:
        source_msg = f"(Used {referral_points_used} referral points and {main_score_used} main points)"
    elif referral_points_used > 0:
        source_msg = f"(Used {referral_points_used} referral points)"
    else:
        source_msg = ""
    
    return f"✅ Bet placed: {bet_type} {amount} {source_msg}\nYour balance: {player_stats['score']} points"


def payout(game: DiceGame, chat_data: Dict, global_data: Dict) -> Dict:
    """Process payouts for a completed game.
    
    Args:
        game: The completed DiceGame instance
        chat_data: The chat-specific data dictionary
        global_data: The global data dictionary
        
    Returns:
        A dictionary containing game summary information
    """
    if game.state != GAME_STATE_CLOSED or game.result is None:
        logger.error(f"Cannot process payout: game state={game.state}, result={game.result}")
        raise GameStateError("Cannot process payout for a game that is not closed or has no result.")
    
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
    
    # Process winners
    for user_id_str, bet_amount in game.bets[winning_bet_type].items():
        # Calculate winnings
        winnings = int(bet_amount * multiplier)
        
        # Update player stats
        if user_id_str in chat_data["player_stats"]:
            player = chat_data["player_stats"][user_id_str]
            player["score"] += winnings
            player["total_wins"] += 1
            
            # Add to winners list
            winners_list.append({
                "user_id": user_id_str,
                "username": player["username"],
                "bet_amount": bet_amount,
                "winnings": winnings,
                "wallet_balance": player["score"]  # Current wallet balance after winnings
            })
            
            total_winners += 1
            total_payout += winnings
    
    # Process losers (all bets that weren't on the winning type)
    for bet_type, bets in game.bets.items():
        if bet_type != winning_bet_type:
            for user_id_str, bet_amount in bets.items():
                if user_id_str in chat_data["player_stats"]:
                    player = chat_data["player_stats"][user_id_str]
                    player["total_losses"] += 1
                    
                    # Add to losers list
                    # Get user's full name from global data if available
                    user_global_data = global_data.get("users", {}).get(user_id_str, {})
                    full_name = user_global_data.get("full_name", "")
                    
                    losers_list.append({
                        "user_id": user_id_str,
                        "username": player["username"],
                        "display_name": full_name or player["username"],
                        "bet_amount": bet_amount,
                        "wallet_balance": player["score"]  # Current wallet balance after loss
                    })
                    
                    total_losers += 1
    
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
        chat_data["consecutive_idle_matches"] = chat_data.get("consecutive_idle_matches", 0) + 1
    else:
        chat_data["consecutive_idle_matches"] = 0
    
    # Save data
    save_data(global_data)
    
    # Log the game result
    logger.info(f"Game completed: match_id={game.match_id}, result={game.result}, "
                f"winning_type={winning_bet_type}, total_bets={total_bets}, "
                f"total_payout={total_payout}, winners={total_winners}, losers={total_losers}")
    
    # Return game summary
    dice1, dice2 = game.result
    
    # Use simple string representations since actual dice animation is handled by Telegram
    dice1_str = str(dice1)
    dice2_str = str(dice2)
    
    return {
        "match_id": game.match_id,
        "result": game.result,
        "dice_values": (dice1, dice2),
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
        "consecutive_idle_matches": chat_data.get("consecutive_idle_matches", 0)
    }


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
        logger.warning(f"Attempted to close betting for game in state {game.state}")


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