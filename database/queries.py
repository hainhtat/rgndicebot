"""Database query functions for the dicebot application."""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from .connection import get_db_session
from .models import User, Chat, PlayerStats, Game, Bet, AdminData
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# User operations
def get_or_create_user(user_id: int, full_name: str, username: Optional[str] = None) -> Dict[str, Any]:
    """Get existing user or create new one."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(
                user_id=user_id,
                full_name=full_name,
                username=username
            )
            session.add(user)
            session.flush()
            logger.info(f"Created new user: {user_id} ({username})")
        else:
            # Update user info if changed
            if user.full_name != full_name or user.username != username:
                user.full_name = full_name
                user.username = username
                user.updated_at = datetime.utcnow()
        
        # Return dictionary to avoid unbound instance issues
        return {
            'user_id': user.user_id,
            'full_name': user.full_name,
            'username': user.username,
            'referral_points': user.referral_points,
            'referred_by': user.referred_by,
            'created_at': user.created_at
        }

def get_user_referral_points(user_id: int) -> int:
    """Get user's referral points."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user.referral_points if user else 0

def update_user_referral_points(user_id: int, points: int) -> bool:
    """Update user's referral points."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.referral_points = points
            user.updated_at = datetime.utcnow()
            return True
        return False


def get_user_bonus_points(user_id: int) -> int:
    """Get user's bonus points."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user.bonus_points if user else 0


def update_user_bonus_points(user_id: int, points: int) -> bool:
    """Update user's bonus points."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.bonus_points = points
            user.updated_at = datetime.utcnow()
            return True
        return False


def get_user_welcome_bonuses(user_id: int) -> dict:
    """Get user's welcome bonuses received per chat."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user.welcome_bonuses_received if user and user.welcome_bonuses_received else {}


def update_user_welcome_bonuses(user_id: int, welcome_bonuses: dict) -> bool:
    """Update user's welcome bonuses received."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.welcome_bonuses_received = welcome_bonuses
            user.updated_at = datetime.utcnow()
            return True
        return False


def mark_welcome_bonus_received(user_id: int, chat_id: int) -> bool:
    """Mark that user has received welcome bonus for a specific chat."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            # Handle JSON field update properly
            welcome_bonuses = user.welcome_bonuses_received or {}
            welcome_bonuses[str(chat_id)] = True
            user.welcome_bonuses_received = welcome_bonuses
            user.updated_at = datetime.utcnow()
            # Force the session to recognize the change
            session.merge(user)
            return True
        return False


def has_received_welcome_bonus(user_id: int, chat_id: int) -> bool:
    """Check if user has already received welcome bonus for a specific chat."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user and user.welcome_bonuses_received:
            return user.welcome_bonuses_received.get(str(chat_id), False)
        return False

def set_user_referrer(user_id: int, referrer_id: int) -> bool:
    """Set user's referrer."""
    with get_db_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.referred_by = referrer_id
            user.updated_at = datetime.utcnow()
            return True
        return False

# Chat operations
def get_or_create_chat(chat_id: int) -> Dict[str, Any]:
    """Get existing chat or create new one."""
    with get_db_session() as session:
        chat = session.query(Chat).filter(Chat.chat_id == chat_id).first()
        if not chat:
            chat = Chat(chat_id=chat_id)
            session.add(chat)
            session.flush()
            logger.info(f"Created new chat: {chat_id}")
        
        # Return dictionary to avoid unbound instance issues
        return {
            'chat_id': chat.chat_id,
            'match_counter': chat.match_counter,
            'created_at': chat.created_at,
            'updated_at': chat.updated_at
        }

def get_chat_match_counter(chat_id: int) -> int:
    """Get current match counter for chat."""
    with get_db_session() as session:
        chat = session.query(Chat).filter(Chat.chat_id == chat_id).first()
        return chat.match_counter if chat else 1

def increment_chat_match_counter(chat_id: int) -> int:
    """Increment and return new match counter."""
    with get_db_session() as session:
        chat = get_or_create_chat(chat_id)
        chat.match_counter += 1
        chat.updated_at = datetime.utcnow()
        session.merge(chat)
        return chat.match_counter

# Player stats operations
def get_or_create_player_stats(user_id: int, chat_id: int) -> Dict[str, Any]:
    """Get existing player stats or create new ones."""
    with get_db_session() as session:
        stats = session.query(PlayerStats).filter(
            PlayerStats.user_id == user_id,
            PlayerStats.chat_id == chat_id
        ).first()
        
        if not stats:
            # Ensure user and chat exist
            get_or_create_user(user_id, "Unknown")  # Will be updated later
            get_or_create_chat(chat_id)
            
            # Get the new user bonus from config
            from config.config_manager import get_config
            config = get_config()
            initial_score = config.get('user', 'new_user_bonus', 0)
            
            stats = PlayerStats(
                user_id=user_id,
                chat_id=chat_id,
                score=initial_score
            )
            session.add(stats)
            session.flush()
            logger.info(f"Created new player stats for user {user_id} in chat {chat_id} with initial score {initial_score}")
        
        # Get user info for username
        user = session.query(User).filter(User.user_id == user_id).first()
        username = user.username if user and user.username else "Unknown"
        
        # Return as dictionary to avoid session issues
        return {
            'user_id': stats.user_id,
            'username': username,
            'score': stats.score,
            'total_wins': stats.total_wins,
            'total_losses': stats.total_losses,
            'total_bets': stats.total_bets,
            'last_active': stats.last_active.isoformat() if stats.last_active else datetime.utcnow().isoformat()
        }

def update_player_stats(user_id: int, chat_id: int, score_change: int, 
                       is_win: bool, bet_count: int = 0) -> bool:
    """Update player statistics.
    
    Args:
        user_id: User ID
        chat_id: Chat ID
        score_change: Change in score (positive for winnings, negative for bets)
        is_win: Whether this is a win (only used for game results, not bets)
        bet_count: Number of bets to add (0 for bet placement, 1 for game result)
    """
    with get_db_session() as session:
        try:
            # Get the actual SQLAlchemy object for updating
            stats = session.query(PlayerStats).filter(
                PlayerStats.user_id == user_id,
                PlayerStats.chat_id == chat_id
            ).first()
            
            if not stats:
                # Create new stats if they don't exist
                get_or_create_player_stats(user_id, chat_id)  # This creates the record
                stats = session.query(PlayerStats).filter(
                    PlayerStats.user_id == user_id,
                    PlayerStats.chat_id == chat_id
                ).first()
            
            if stats:
                stats.score += score_change
                
                # Only update bet counts and win/loss for game results, not bet placement
                if bet_count > 0:
                    stats.total_bets += bet_count
                    if is_win:
                        stats.total_wins += 1
                    else:
                        stats.total_losses += 1
                        
                stats.last_active = datetime.utcnow()
                stats.updated_at = datetime.utcnow()
                session.merge(stats)
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating player stats for user {user_id}: {e}")
            session.rollback()
            return False

def get_player_score(user_id: int, chat_id: int) -> int:
    """Get player's score in a specific chat."""
    with get_db_session() as session:
        stats = session.query(PlayerStats).filter(
            PlayerStats.user_id == user_id,
            PlayerStats.chat_id == chat_id
        ).first()
        return stats.score if stats else 0

def get_chat_leaderboard(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get top players in a chat by score."""
    with get_db_session() as session:
        stats_list = session.query(PlayerStats).join(User).filter(
            PlayerStats.chat_id == chat_id
        ).order_by(desc(PlayerStats.score)).limit(limit).all()
        
        # Convert to dictionaries while session is active
        return [{
            'user_id': stats.user_id,
            'username': stats.user.username if stats.user else 'Unknown',
            'score': stats.score,
            'total_wins': stats.total_wins,
            'total_losses': stats.total_losses,
            'total_bets': stats.total_bets,
            'last_active': stats.last_active
        } for stats in stats_list]

# Game operations
def create_game(match_id: int, chat_id: int) -> Dict[str, Any]:
    """Create a new game."""
    with get_db_session() as session:
        game = Game(
            match_id=match_id,
            chat_id=chat_id
        )
        session.add(game)
        session.flush()
        # Return dictionary to avoid unbound instance issues
        return {
            'id': game.id,
            'match_id': game.match_id,
            'chat_id': game.chat_id,
            'state': game.state,
            'created_at': game.created_at
        }

def get_active_game(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get active game for a chat."""
    with get_db_session() as session:
        game = session.query(Game).filter(
            Game.chat_id == chat_id,
            Game.state.in_(['WAITING', 'CLOSED'])
        ).first()
        
        if game:
            # Return dictionary to avoid unbound instance issues
            return {
                'id': game.id,
                'match_id': game.match_id,
                'chat_id': game.chat_id,
                'state': game.state,
                'created_at': game.created_at,
                'completed_at': game.completed_at,
                'result': game.result,
                'dice_result': game.dice_result,
                'winning_type': game.winning_type
            }
        return None

def update_game_state(game_id: int, state: str) -> bool:
    """Update game state."""
    with get_db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if game:
            game.state = state
            if state == 'OVER':
                game.completed_at = datetime.utcnow()
            return True
        return False

def complete_game(game_id: int, result: List[int], winning_type: str) -> bool:
    """Complete a game with results."""
    with get_db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if game:
            game.state = 'OVER'
            game.result = result
            game.dice_result = result  # For compatibility
            game.winning_type = winning_type
            game.completed_at = datetime.utcnow()
            return True
        return False

def get_recent_games(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent completed games for a chat."""
    with get_db_session() as session:
        games = session.query(Game).filter(
            Game.chat_id == chat_id,
            Game.state == 'OVER'
        ).order_by(desc(Game.completed_at)).limit(limit).all()
        
        # Return list of dictionaries to avoid unbound instance issues
        return [{
            'id': game.id,
            'match_id': game.match_id,
            'chat_id': game.chat_id,
            'state': game.state,
            'created_at': game.created_at,
            'completed_at': game.completed_at,
            'result': game.result,
            'dice_result': game.dice_result,
            'winning_type': game.winning_type
        } for game in games]

# Bet operations
def create_bet(game_id: int, user_id: int, bet_type: str, amount: int, 
               referral_points_used: int = 0) -> Dict[str, Any]:
    """Create a new bet."""
    with get_db_session() as session:
        bet = Bet(
            game_id=game_id,
            user_id=user_id,
            bet_type=bet_type,
            amount=amount,
            referral_points_used=referral_points_used
        )
        session.add(bet)
        session.flush()
        # Return dictionary to avoid unbound instance issues
        return {
            'id': bet.id,
            'game_id': bet.game_id,
            'user_id': bet.user_id,
            'bet_type': bet.bet_type,
            'amount': bet.amount,
            'referral_points_used': bet.referral_points_used,
            'created_at': bet.created_at,
            'payout': bet.payout
        }

def get_game_bets(game_id: int) -> List[Dict[str, Any]]:
    """Get all bets for a game."""
    with get_db_session() as session:
        bets = session.query(Bet).filter(Bet.game_id == game_id).all()
        
        # Return list of dictionaries to avoid unbound instance issues
        return [{
            'id': bet.id,
            'game_id': bet.game_id,
            'user_id': bet.user_id,
            'bet_type': bet.bet_type,
            'amount': bet.amount,
            'referral_points_used': bet.referral_points_used,
            'created_at': bet.created_at,
            'payout': bet.payout
        } for bet in bets]

def update_bet_payout(bet_id: int, payout: int) -> bool:
    """Update bet payout."""
    with get_db_session() as session:
        bet = session.query(Bet).filter(Bet.id == bet_id).first()
        if bet:
            bet.payout = payout
            return True
        return False

# Admin operations
def get_or_create_admin_data(user_id: int, chat_id: int) -> Dict[str, Any]:
    """Get existing admin data or create new."""
    with get_db_session() as session:
        admin_data = session.query(AdminData).filter(
            AdminData.user_id == user_id,
            AdminData.chat_id == chat_id
        ).first()
        
        if not admin_data:
            # Ensure user and chat exist
            get_or_create_user(user_id, "Unknown")
            get_or_create_chat(chat_id)
            
            admin_data = AdminData(
                user_id=user_id,
                chat_id=chat_id
            )
            session.add(admin_data)
            session.flush()
        
        # Return dictionary to avoid unbound instance issues
        return {
            'id': admin_data.id,
            'user_id': admin_data.user_id,
            'chat_id': admin_data.chat_id,
            'points': admin_data.points,
            'last_refill': admin_data.last_refill,
            'created_at': admin_data.created_at,
            'updated_at': admin_data.updated_at
        }

def get_admin_points(user_id: int, chat_id: int) -> int:
    """Get admin points for a specific chat."""
    with get_db_session() as session:
        admin_data = session.query(AdminData).filter(
            AdminData.user_id == user_id,
            AdminData.chat_id == chat_id
        ).first()
        return admin_data.points if admin_data else 0

def update_admin_points(user_id: int, chat_id: int, points: int) -> bool:
    """Update admin points."""
    with get_db_session() as session:
        admin_data = session.query(AdminData).filter(
            AdminData.user_id == user_id,
            AdminData.chat_id == chat_id
        ).first()
        
        if not admin_data:
            # Create new admin data
            get_or_create_user(user_id, "Unknown")
            get_or_create_chat(chat_id)
            admin_data = AdminData(
                user_id=user_id,
                chat_id=chat_id,
                points=points
            )
            session.add(admin_data)
        else:
            admin_data.points = points
            admin_data.updated_at = datetime.utcnow()
            session.merge(admin_data)
        return True

def refill_admin_points(user_id: int, chat_id: int, points: int) -> bool:
    """Refill admin points and update last refill time."""
    with get_db_session() as session:
        admin_data = session.query(AdminData).filter(
            AdminData.user_id == user_id,
            AdminData.chat_id == chat_id
        ).first()
        
        if not admin_data:
            # Create new admin data
            get_or_create_user(user_id, "Unknown")
            get_or_create_chat(chat_id)
            admin_data = AdminData(
                user_id=user_id,
                chat_id=chat_id,
                points=points,
                last_refill=datetime.utcnow()
            )
            session.add(admin_data)
        else:
            admin_data.points += points
            admin_data.last_refill = datetime.utcnow()
            admin_data.updated_at = datetime.utcnow()
            session.merge(admin_data)
        return True

def get_all_admin_data() -> List[Dict[str, Any]]:
    """Get all admin data from database."""
    with get_db_session() as session:
        admin_data_list = session.query(AdminData).options(
            joinedload(AdminData.user),
            joinedload(AdminData.chat)
        ).all()
        
        result = []
        for admin_data in admin_data_list:
            result.append({
                'user_id': admin_data.user_id,
                'chat_id': admin_data.chat_id,
                'username': admin_data.user.username if admin_data.user else f"Admin {admin_data.user_id}",
                'points': admin_data.points,
                'last_refill': admin_data.last_refill,
                'created_at': admin_data.created_at,
                'updated_at': admin_data.updated_at
            })
        
        return result