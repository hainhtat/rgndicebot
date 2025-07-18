"""Database adapter that can switch between JSON and PostgreSQL."""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date, timedelta
from sqlalchemy.exc import SQLAlchemyError
from config.settings import USE_DATABASE
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class DatabaseAdapter:
    """Unified adapter for database operations."""
    
    def __init__(self):
        """Initialize the adapter."""
        self.use_database = USE_DATABASE
        
        if self.use_database:
            # Import database queries module
            from . import queries
            self.db_queries = queries
        else:
            # JSON file manager was removed during migration
            # This fallback should not be used in production
            self.load_data = lambda: {}
            self.save_data = lambda data: None
    
    # User operations
    def get_user_referral_points(self, user_id: int) -> int:
        """Get user's referral points."""
        if self.use_database:
            points = self.db_queries.get_user_referral_points(user_id)
            logger.debug(f"Retrieved referral points for user {user_id}: {points}")
            return points
        else:
            data = self.load_data()
            user_data = data.get('global_user_data', {}).get(str(user_id), {})
            return user_data.get('referral_points', 0)
    
    def update_user_referral_points(self, user_id: int, points: int) -> bool:
        """Update user's referral points."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user_id: {user_id}")
            return False
        if not isinstance(points, int) or points < 0:
            logger.error(f"Invalid points: {points}")
            return False
        if self.use_database:
            success = self.db_queries.update_user_referral_points(user_id, points)
            if success:
                logger.info(f"Updated referral points for user {user_id} to {points}")
            else:
                logger.error(f"Failed to update referral points for user {user_id}")
            return success
        else:
            data = self.load_data()
            if 'global_user_data' not in data:
                data['global_user_data'] = {}
            if str(user_id) not in data['global_user_data']:
                data['global_user_data'][str(user_id)] = {}
            data['global_user_data'][str(user_id)]['referral_points'] = points
            self.save_data(data)
            return True
    
    def set_user_referrer(self, user_id: int, referrer_id: int) -> bool:
        """Set user's referrer."""
        if self.use_database:
            return self.db_queries.set_user_referrer(user_id, referrer_id)
        else:
            data = self.load_data()
            if 'global_user_data' not in data:
                data['global_user_data'] = {}
            if str(user_id) not in data['global_user_data']:
                data['global_user_data'][str(user_id)] = {}
            data['global_user_data'][str(user_id)]['referred_by'] = referrer_id
            self.save_data(data)
            return True
    
    def get_user_bonus_points(self, user_id: int) -> int:
        """Get user's bonus points."""
        if self.use_database:
            return self.db_queries.get_user_bonus_points(user_id)
        else:
            data = self.load_data()
            user_data = data.get('global_user_data', {}).get(str(user_id), {})
            return user_data.get('bonus_points', 0)
    
    def update_user_bonus_points(self, user_id: int, points: int) -> bool:
        """Update user's bonus points."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user_id: {user_id}")
            return False
        if not isinstance(points, int) or points < 0:
            logger.error(f"Invalid points: {points}")
            return False
        if self.use_database:
            success = self.db_queries.update_user_bonus_points(user_id, points)
            if success:
                logger.info(f"Updated bonus points for user {user_id} to {points}")
            else:
                logger.error(f"Failed to update bonus points for user {user_id}")
            return success
        else:
            data = self.load_data()
            if 'global_user_data' not in data:
                data['global_user_data'] = {}
            if str(user_id) not in data['global_user_data']:
                data['global_user_data'][str(user_id)] = {}
            data['global_user_data'][str(user_id)]['bonus_points'] = points
            self.save_data(data)
            return True
    
    def get_user_welcome_bonuses(self, user_id: int) -> dict:
        """Get user's welcome bonuses received per chat."""
        if self.use_database:
            return self.db_queries.get_user_welcome_bonuses(user_id)
        else:
            data = self.load_data()
            user_data = data.get('global_user_data', {}).get(str(user_id), {})
            return user_data.get('welcome_bonuses_received', {})
    
    def mark_welcome_bonus_received(self, user_id: int, chat_id: int) -> bool:
        """Mark that user has received welcome bonus for a specific chat."""
        if self.use_database:
            return self.db_queries.mark_welcome_bonus_received(user_id, chat_id)
        else:
            data = self.load_data()
            if 'global_user_data' not in data:
                data['global_user_data'] = {}
            if str(user_id) not in data['global_user_data']:
                data['global_user_data'][str(user_id)] = {}
            if 'welcome_bonuses_received' not in data['global_user_data'][str(user_id)]:
                data['global_user_data'][str(user_id)]['welcome_bonuses_received'] = {}
            data['global_user_data'][str(user_id)]['welcome_bonuses_received'][str(chat_id)] = True
            self.save_data(data)
            return True
    
    def has_received_welcome_bonus(self, user_id: int, chat_id: int) -> bool:
        """Check if user has already received welcome bonus for a specific chat."""
        if self.use_database:
            return self.db_queries.has_received_welcome_bonus(user_id, chat_id)
        else:
            data = self.load_data()
            user_data = data.get('global_user_data', {}).get(str(user_id), {})
            welcome_bonuses = user_data.get('welcome_bonuses_received', {})
            return welcome_bonuses.get(str(chat_id), False)
    
    # Player stats operations
    def get_player_score(self, user_id: int, chat_id: int) -> int:
        """Get player's current score."""
        if self.use_database:
            return self.db_queries.get_player_score(user_id, chat_id)
        else:
            data = self.load_data()
            chat_data = data.get('all_chat_data', {}).get(str(chat_id), {})
            player_stats = chat_data.get('player_stats', {}).get(str(user_id), {})
            return player_stats.get('score', 0)
    
    def get_or_create_player_stats(self, user_id: int, chat_id: int, username: str = "Unknown") -> Dict[str, Any]:
        """Get existing player stats or create new ones."""
        if self.use_database:
            try:
                from .queries import get_or_create_player_stats
                stats_dict = get_or_create_player_stats(user_id, chat_id)
                # Update username if provided and different
                if username != "Unknown" and stats_dict.get('username') in [None, "Unknown"]:
                    stats_dict['username'] = username
                return stats_dict
            except Exception as e:
                logger.error(f"Error getting/creating player stats: {e}")
                # Fallback to default values
                from config.config_manager import get_config
                config = get_config()
                return {
                    'user_id': user_id,
                    'username': username,
                    'score': config.get('user', 'new_user_bonus', 0),
                    'total_wins': 0,
                    'total_losses': 0,
                    'total_bets': 0,
                    'last_active': datetime.now().isoformat()
                }
        else:
            data = self.load_data()
            if 'all_chat_data' not in data:
                data['all_chat_data'] = {}
            if str(chat_id) not in data['all_chat_data']:
                data['all_chat_data'][str(chat_id)] = {
                    'player_stats': {},
                    'match_counter': 1,
                    'match_history': [],
                    'group_admins': [],
                    'consecutive_idle_matches': 0
                }
            
            chat_data = data['all_chat_data'][str(chat_id)]
            if 'player_stats' not in chat_data:
                chat_data['player_stats'] = {}
            
            if str(user_id) not in chat_data['player_stats']:
                from config.config_manager import get_config
                config = get_config()
                chat_data['player_stats'][str(user_id)] = {
                    'username': username,
                    'score': config.get('user', 'new_user_bonus', 0),
                    'total_wins': 0,
                    'total_losses': 0,
                    'total_bets': 0,
                    'last_active': datetime.now().isoformat()
                }
                self.save_data(data)
            
            return chat_data['player_stats'][str(user_id)]
    
    def update_player_stats(self, user_id: int, chat_id: int, score_change: int, 
                           is_win: bool, bet_count: int = 0) -> bool:
        """Update player statistics."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user_id: {user_id}")
            return False
        if not isinstance(chat_id, int):
            logger.error(f"Invalid chat_id: {chat_id}")
            return False
        if not isinstance(score_change, int):
            logger.error(f"Invalid score_change: {score_change}")
            return False
        if not isinstance(is_win, bool):
            logger.error(f"Invalid is_win: {is_win}")
            return False
        if not isinstance(bet_count, int) or bet_count < 0:
            logger.error(f"Invalid bet_count: {bet_count}")
            return False
        if self.use_database:
            try:
                success = self.db_queries.update_player_stats(user_id, chat_id, score_change, is_win, bet_count)
                if success:
                    logger.info(f"Updated player stats for user {user_id} in chat {chat_id}")
                else:
                    logger.error(f"Failed to update player stats for user {user_id} in chat {chat_id}")
                return success
            except Exception as e:
                logger.error(f"Database adapter error updating player stats: {e}")
                return False
        else:
            data = self.load_data()
            
            # Ensure chat data exists
            if 'all_chat_data' not in data:
                data['all_chat_data'] = {}
            if str(chat_id) not in data['all_chat_data']:
                data['all_chat_data'][str(chat_id)] = {
                    'player_stats': {},
                    'match_counter': 1,
                    'match_history': [],
                    'group_admins': [],
                    'consecutive_idle_matches': 0
                }
            
            chat_data = data['all_chat_data'][str(chat_id)]
            if 'player_stats' not in chat_data:
                chat_data['player_stats'] = {}
            
            # Ensure player stats exist
            if str(user_id) not in chat_data['player_stats']:
                chat_data['player_stats'][str(user_id)] = {
                    'username': 'Unknown',
                    'score': 0,
                    'total_wins': 0,
                    'total_losses': 0,
                    'total_bets': 0,
                    'last_active': datetime.now().isoformat()
                }
            
            player_stats = chat_data['player_stats'][str(user_id)]
            player_stats['score'] += score_change
            player_stats['total_bets'] += 1
            if is_win:
                player_stats['total_wins'] += 1
            else:
                player_stats['total_losses'] += 1
            player_stats['last_active'] = datetime.now().isoformat()
            
            self.save_data(data)
            return True
    
    def get_chat_leaderboard(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top players in a chat by score."""
        if self.use_database:
            # get_chat_leaderboard now returns dictionaries directly
            return self.db_queries.get_chat_leaderboard(chat_id, limit)
        else:
            data = self.load_data()
            chat_data = data.get('all_chat_data', {}).get(str(chat_id), {})
            player_stats = chat_data.get('player_stats', {})
            
            # Convert to list and sort by score
            stats_list = []
            for user_id_str, stats in player_stats.items():
                stats_dict = stats.copy()
                stats_dict['user_id'] = int(user_id_str)
                stats_list.append(stats_dict)
            
            stats_list.sort(key=lambda x: x.get('score', 0), reverse=True)
            return stats_list[:limit]
    
    # Chat operations
    def get_chat_match_counter(self, chat_id: int) -> int:
        """Get current match counter for chat."""
        if self.use_database:
            return self.db_queries.get_chat_match_counter(chat_id)
        else:
            data = self.load_data()
            chat_data = data.get('all_chat_data', {}).get(str(chat_id), {})
            return chat_data.get('match_counter', 1)
    
    def increment_chat_match_counter(self, chat_id: int) -> int:
        """Increment and return new match counter."""
        if self.use_database:
            return self.db_queries.increment_chat_match_counter(chat_id)
        else:
            data = self.load_data()
            if 'all_chat_data' not in data:
                data['all_chat_data'] = {}
            if str(chat_id) not in data['all_chat_data']:
                data['all_chat_data'][str(chat_id)] = {'match_counter': 1}
            
            data['all_chat_data'][str(chat_id)]['match_counter'] += 1
            new_counter = data['all_chat_data'][str(chat_id)]['match_counter']
            self.save_data(data)
            return new_counter
    
    # Admin operations
    def get_admin_points(self, user_id: int, chat_id: int) -> int:
        """Get admin points for a specific chat."""
        if self.use_database:
            return self.db_queries.get_admin_points(user_id, chat_id)
        else:
            data = self.load_data()
            admin_data = data.get('admin_data', {}).get(str(user_id), {})
            chat_points = admin_data.get('chat_points', {}).get(str(chat_id), {})
            return chat_points.get('points', 0)
    
    def update_admin_points(self, user_id: int, chat_id: int, points: int) -> bool:
        """Update admin points."""
        if self.use_database:
            return self.db_queries.update_admin_points(user_id, chat_id, points)
        else:
            data = self.load_data()
            if 'admin_data' not in data:
                data['admin_data'] = {}
            if str(user_id) not in data['admin_data']:
                data['admin_data'][str(user_id)] = {'chat_points': {}}
            if str(chat_id) not in data['admin_data'][str(user_id)]['chat_points']:
                data['admin_data'][str(user_id)]['chat_points'][str(chat_id)] = {}
            
            data['admin_data'][str(user_id)]['chat_points'][str(chat_id)]['points'] = points
            self.save_data(data)
            return True
    
    def refill_admin_points(self, user_id: int, chat_id: int, points: int) -> bool:
        """Refill admin points and update last refill time."""
        if self.use_database:
            return self.db_queries.refill_admin_points(user_id, chat_id, points)
        else:
            current_points = self.get_admin_points(user_id, chat_id)
            new_points = current_points + points
            
            data = self.load_data()
            if 'admin_data' not in data:
                data['admin_data'] = {}
            if str(user_id) not in data['admin_data']:
                data['admin_data'][str(user_id)] = {'chat_points': {}}
            if str(chat_id) not in data['admin_data'][str(user_id)]['chat_points']:
                data['admin_data'][str(user_id)]['chat_points'][str(chat_id)] = {}
            
            chat_points = data['admin_data'][str(user_id)]['chat_points'][str(chat_id)]
            chat_points['points'] = new_points
            chat_points['last_refill'] = datetime.now().isoformat()
            
            self.save_data(data)
            return True
    
    # Game operations (simplified for now)
    def add_match_to_history(self, chat_id: int, match_data: Dict[str, Any]) -> bool:
        """Add match to history."""
        if self.use_database:
            # For database, we'll create a Game record
            try:
                game = self.db_queries.create_game(match_data['match_id'], chat_id)
                if 'result' in match_data:
                    self.db_queries.complete_game(
                        game.id, 
                        match_data['result'], 
                        match_data.get('winning_type', '')
                    )
                return True
            except Exception as e:
                logger.error(f"Error adding match to database: {e}")
                return False
        else:
            data = self.load_data()
            if 'all_chat_data' not in data:
                data['all_chat_data'] = {}
            if str(chat_id) not in data['all_chat_data']:
                data['all_chat_data'][str(chat_id)] = {'match_history': []}
            if 'match_history' not in data['all_chat_data'][str(chat_id)]:
                data['all_chat_data'][str(chat_id)]['match_history'] = []
            
            data['all_chat_data'][str(chat_id)]['match_history'].append(match_data)
            self.save_data(data)
            return True
    
    def get_recent_matches(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent matches for a chat."""
        if self.use_database:
            games = self.db_queries.get_recent_games(chat_id, limit)
            return [{
                'match_id': game.match_id,
                'timestamp': game.completed_at.isoformat() if game.completed_at else game.created_at.isoformat(),
                'result': game.result,
                'dice_result': game.dice_result,
                'winning_type': game.winning_type,
                'total_bets': game.total_bets
            } for game in games]
        else:
            data = self.load_data()
            chat_data = data.get('all_chat_data', {}).get(str(chat_id), {})
            match_history = chat_data.get('match_history', [])
            return match_history[-limit:] if match_history else []

    def get_daily_losses(self, user_id: str, chat_id: str = None) -> Dict[str, Any]:
        """Get daily losses for a user."""
        if self.use_database:
            try:
                from .connection import get_db_session as get_session
                from .queries import get_daily_losses
                
                with get_session() as session:
                    losses = get_daily_losses(session, user_id, chat_id)
                    return {loss.date: loss.total_loss for loss in losses}
            except Exception as e:
                logger.error(f"Error getting daily losses: {e}")
                return {}
        else:
            # JSON fallback
            data = self.load_data()
            daily_losses = data.get("daily_losses", {})
            if chat_id:
                return daily_losses.get(chat_id, {}).get(user_id, {})
            else:
                # Return all losses for user across all chats
                user_losses = {}
                for chat_losses in daily_losses.values():
                    if user_id in chat_losses:
                        user_losses.update(chat_losses[user_id])
                return user_losses
    
    # Logging operations
    def add_log_entry(self, log_data: Dict[str, Any]) -> bool:
        """Add a log entry to the database."""
        if self.use_database:
            try:
                from .connection import get_db_session as get_session
                from .models import LogEntry
                
                with get_session() as session:
                    log_entry = LogEntry(
                        timestamp=datetime.fromisoformat(log_data.get('timestamp', datetime.now().isoformat())),
                        level=log_data.get('level', 'INFO'),
                        logger_name=log_data.get('logger', 'unknown'),
                        message=log_data.get('message', ''),
                        module=log_data.get('module'),
                        function=log_data.get('function'),
                        line_number=log_data.get('line'),
                        exception_info=log_data.get('exception'),
                        extra_data=log_data.get('extra')
                    )
                    session.add(log_entry)
                    session.commit()
                    return True
            except Exception as e:
                logger.error(f"Error adding log entry: {e}")
                return False
        else:
            # JSON fallback - just return True as logs go to file
            return True
    
    def get_log_entries(self, limit: int = 100, level: str = None, 
                       start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get log entries from the database."""
        if self.use_database:
            try:
                from .connection import get_db_session as get_session
                from .models import LogEntry
                from sqlalchemy import desc
                
                with get_session() as session:
                    query = session.query(LogEntry)
                    
                    if level:
                        query = query.filter(LogEntry.level == level)
                    if start_date:
                        query = query.filter(LogEntry.timestamp >= start_date)
                    if end_date:
                        query = query.filter(LogEntry.timestamp <= end_date)
                    
                    logs = query.order_by(desc(LogEntry.timestamp)).limit(limit).all()
                    
                    return [{
                        'id': log.id,
                        'timestamp': log.timestamp.isoformat(),
                        'level': log.level,
                        'logger': log.logger_name,
                        'message': log.message,
                        'module': log.module,
                        'function': log.function,
                        'line': log.line_number,
                        'exception': log.exception_info,
                        'extra': log.extra_data
                    } for log in logs]
            except Exception as e:
                logger.error(f"Error getting log entries: {e}")
                return []
        else:
            # JSON fallback - return empty list
            return []
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> bool:
        """Clean up old log entries from the database to prevent it from growing too large.
        
        Args:
            days_to_keep: Number of days of logs to keep (default: 30)
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        if self.use_database:
            try:
                from .connection import get_db_session as get_session
                from .models import LogEntry
                from sqlalchemy import func
                
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                
                with get_session() as session:
                    # Count logs to be deleted
                    count_query = session.query(func.count(LogEntry.id)).filter(
                        LogEntry.timestamp < cutoff_date
                    )
                    logs_to_delete = count_query.scalar()
                    
                    if logs_to_delete > 0:
                        # Delete old logs
                        delete_query = session.query(LogEntry).filter(
                            LogEntry.timestamp < cutoff_date
                        )
                        delete_query.delete()
                        session.commit()
                        
                        logger.info(f"Cleaned up {logs_to_delete} old log entries (older than {days_to_keep} days)")
                    else:
                        logger.debug(f"No old log entries to clean up (keeping {days_to_keep} days)")
                    
                    return True
            except Exception as e:
                logger.error(f"Error cleaning up old logs: {e}")
                return False
        else:
            # JSON fallback - no cleanup needed
            return True

# Global adapter instance
db_adapter = DatabaseAdapter()