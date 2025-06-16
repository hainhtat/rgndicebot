import logging
from datetime import datetime
import random

from constants import global_data, INITIAL_PLAYER_SCORE, REFERRAL_BONUS_POINTS
# --- NEW: Import file management functions ---
from file_manager import save_data
# --- REMOVED: Database imports ---
# from database import save_chat_data
# --- END NEW ---

logger = logging.getLogger(__name__)

# Game states
WAITING_FOR_BETS = "WAITING_FOR_BETS"
GAME_CLOSED = "GAME_CLOSED"
GAME_OVER = "GAME_OVER"

class DiceGame:
    def __init__(self, match_id: int, chat_id: int):
        self.match_id = match_id
        self.chat_id = chat_id
        self.state = WAITING_FOR_BETS
        self.bets = {"big": {}, "small": {}, "lucky": {}} # Stores bets: {"type": {user_id: amount}}
        self.participants = set() # Stores user_ids of players who participated in this match
        self.result = None # Stores the dice roll result (sum of two dice)

    def place_bet(self, user_id: int, username: str, bet_type: str, amount: int):
        """
        Processes a player's bet for the current game.
        Prioritizes using referral_points before the main score.
        """
        chat_data = global_data["all_chat_data"].get(self.chat_id)
        if not chat_data:
            logger.error(f"place_bet: Chat data not found for chat_id {self.chat_id}.")
            return False, "❌ ဂိမ်းအချက်အလက်ရှာမတွေ့ပါ။"

        # Ensure user_id is treated as a string when accessing dictionaries
        user_id_str = str(user_id)
        player_stats = chat_data["player_stats"].get(user_id_str)
        global_user_info = global_data["global_user_data"].get(user_id_str) # Get global user data

        if not player_stats:
            # Initialize player stats for a new player in this chat
            player_stats = {
                "username": username,
                "score": INITIAL_PLAYER_SCORE,
                "wins": 0,
                "losses": 0,
                "last_active": datetime.now(),
            }
            chat_data["player_stats"][user_id_str] = player_stats
            logger.info(f"place_bet: Initialized new player {user_id} ({username}) in chat {self.chat_id}.")
        else:
            # Ensure username is up-to-date
            if player_stats.get("username") != username:
                player_stats["username"] = username
            player_stats["last_active"] = datetime.now()

        # Ensure global_user_info exists and has referral_points
        if not global_user_info:
            # This should ideally not happen if get_or_create_global_user_data is called on user interaction
            # but as a fallback, ensure the structure exists.
            global_data["global_user_data"][user_id_str] = {
                "full_name": username, # Fallback name
                "username": username,
                "referral_points": 0,
                "referred_by": None,
                "pending_referrer_id": None
            }
            global_user_info = global_data["global_user_data"][user_id_str] # Update reference

        current_score = player_stats["score"]
        # Use referral points from global_user_data
        current_referral_points = global_user_info.get("referral_points", 0)
        total_available = current_score + current_referral_points

        if amount <= 0:
            return False, "❌ လောင်းကြေးက သုည ဒါမှမဟုတ် အနုတ် မဖြစ်နိုင်ပါဘူး။"
        
        if total_available < amount:
            # Updated error message to reflect combined balance and correct escaping, removed internal *
            return False, (
                f"❌ @{username} ရေ၊ ရမှတ်မလောက်ဘူးရှင့်။\n"
                f"💰 Wallet: {current_score} ကျပ်\n"
                f"🎁 Referral Points: {current_referral_points} ကျပ်\n"
                f"💰 စုစုပေါင်း: {total_available}။ လောင်းတာက {amount} ကျပ်"
            )

        # Deduct from referral points first
        deducted_from_referral = 0
        remaining_bet_amount = amount

        if current_referral_points > 0:
            deducted_from_referral = min(current_referral_points, remaining_bet_amount)
            global_user_info["referral_points"] -= deducted_from_referral # Deduct from global_user_data
            remaining_bet_amount -= deducted_from_referral
            logger.debug(f"Deducted {deducted_from_referral} from referral points for user {user_id}. Remaining bet: {remaining_bet_amount}.")

        # Deduct remaining from main score
        if remaining_bet_amount > 0:
            player_stats["score"] -= remaining_bet_amount
            logger.debug(f"Deducted {remaining_bet_amount} from main score for user {user_id}.")

        # Record the bet
        if bet_type not in self.bets:
            self.bets[bet_type] = {}
        
        self.bets[bet_type][user_id] = self.bets[bet_type].get(user_id, 0) + amount
        self.participants.add(user_id)

        # Save data after every successful bet
        save_data(global_data)

        new_score = player_stats["score"]
        new_referral_points = global_user_info["referral_points"] # Get updated referral points from global_user_info
        
        # Removed internal * as handlers.py will wrap the entire message in bold
        return True, (
            f"✅ @{username} ရေ၊{bet_type.upper()} ကို {amount} ကျပ် လောင်းလိုက်ပြီနော်!\n "
            f"💰 Wallet: {new_score} ကျပ်\n"
            f"🎁 Referral Points: {new_referral_points} ကျပ်"
        )

    def payout(self, chat_id: int):
        """
        Calculates payouts based on the game result and updates player scores.
        Only main score is affected by payouts, referral points are for betting only.
        """
        chat_data = global_data["all_chat_data"].get(chat_id)
        if not chat_data:
            logger.error(f"payout: Chat data not found for chat_id {chat_id}.")
            return "unknown", 0, {}

        player_stats_for_chat = chat_data["player_stats"]

        winning_type = ""
        multiplier = 0
        if self.result < 7:
            winning_type = "small"
            multiplier = 2
        elif self.result > 7:
            winning_type = "big"
            multiplier = 2
        else: # self.result == 7
            winning_type = "lucky"
            multiplier = 5
        
        winning_bets = self.bets.get(winning_type, {})
        individual_payouts = {}

        # Update scores for winning participants
        for user_id, amount_bet in winning_bets.items():
            user_id_str = str(user_id) # Convert to string for dictionary access
            if user_id_str in player_stats_for_chat:
                winnings = amount_bet * multiplier
                # Winnings are added to the main score, not referral points
                player_stats_for_chat[user_id_str]["score"] += winnings 
                player_stats_for_chat[user_id_str]["wins"] += 1
                player_stats_for_chat[user_id_str]["last_active"] = datetime.now()
                individual_payouts[user_id] = winnings
                logger.info(f"payout: User {user_id} won {winnings} in match {self.match_id}. New score: {player_stats_for_chat[user_id_str]['score']}.")
            else:
                logger.warning(f"payout: Winning user {user_id} not found in player_stats_for_chat during payout for match {self.match_id}.")
        
        # Update losses for non-winning participants
        for user_id in self.participants:
            user_id_str = str(user_id) # Convert to string for dictionary access
            if user_id_str not in winning_bets and user_id_str in player_stats_for_chat:
                player_stats_for_chat[user_id_str]["losses"] += 1
                player_stats_for_chat[user_id_str]["last_active"] = datetime.now()
                logger.info(f"payout: User {user_id} lost in match {self.match_id}.")

        # Record match history
        chat_data["match_history"].append({
            "match_id": self.match_id,
            "result": self.result,
            "winner": winning_type,
            "participants": len(self.participants),
            "timestamp": datetime.now() # Store datetime object
        })
        # Keep history list to a manageable size, e.g., last 20 matches
        if len(chat_data["match_history"]) > 20:
            chat_data["match_history"] = chat_data["match_history"][-20:]
        
        # --- NEW: Save all global data after payout and history update ---
        save_data(global_data)
        # --- END NEW ---

        return winning_type, multiplier, individual_payouts
