"""Migration script to transfer data from JSON to PostgreSQL."""

import json
import os
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from .connection import init_database, get_db_session
from .models import User, Chat, PlayerStats, Game, Bet, AdminData
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class DataMigration:
    """Handle migration from JSON to PostgreSQL."""
    
    def __init__(self, json_file_path: str = "data.json"):
        self.json_file_path = json_file_path
        self.stats = {
            'users': 0,
            'chats': 0,
            'player_stats': 0,
            'games': 0,
            'bets': 0,
            'admin_data': 0,
            'errors': 0
        }
    
    def load_json_data(self) -> Dict[str, Any]:
        """Load data from JSON file."""
        if not os.path.exists(self.json_file_path):
            logger.warning(f"JSON file not found: {self.json_file_path}")
            return {}
        
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded JSON data from {self.json_file_path}")
                return data
        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            return {}
    
    def migrate_users(self, session, global_user_data: Dict[str, Any]):
        """Migrate global user data."""
        logger.info("Migrating users...")
        
        for user_id_str, user_data in global_user_data.items():
            try:
                user_id = int(user_id_str)
                
                # Check if user already exists
                existing_user = session.query(User).filter(User.user_id == user_id).first()
                if existing_user:
                    continue
                
                user = User(
                    user_id=user_id,
                    full_name=user_data.get('full_name', 'Unknown'),
                    username=user_data.get('username'),
                    referral_points=user_data.get('referral_points', 0),
                    referred_by=user_data.get('referred_by'),
                    pending_referrer_id=user_data.get('pending_referrer_id')
                )
                
                session.add(user)
                self.stats['users'] += 1
                
            except Exception as e:
                logger.error(f"Error migrating user {user_id_str}: {e}")
                self.stats['errors'] += 1
    
    def migrate_chats_and_stats(self, session, all_chat_data: Dict[str, Any]):
        """Migrate chat data and player stats."""
        logger.info("Migrating chats and player stats...")
        
        for chat_id_str, chat_data in all_chat_data.items():
            try:
                chat_id = int(chat_id_str)
                
                # Create or get chat
                existing_chat = session.query(Chat).filter(Chat.chat_id == chat_id).first()
                if not existing_chat:
                    chat = Chat(
                        chat_id=chat_id,
                        match_counter=chat_data.get('match_counter', 1),
                        consecutive_idle_matches=chat_data.get('consecutive_idle_matches', 0),
                        group_admins=chat_data.get('group_admins', [])
                    )
                    session.add(chat)
                    self.stats['chats'] += 1
                
                # Migrate player stats
                player_stats_data = chat_data.get('player_stats', {})
                for user_id_str, stats_data in player_stats_data.items():
                    try:
                        user_id = int(user_id_str)
                        
                        # Check if stats already exist
                        existing_stats = session.query(PlayerStats).filter(
                            PlayerStats.user_id == user_id,
                            PlayerStats.chat_id == chat_id
                        ).first()
                        if existing_stats:
                            continue
                        
                        # Ensure user exists
                        user = session.query(User).filter(User.user_id == user_id).first()
                        if not user:
                            user = User(
                                user_id=user_id,
                                full_name=stats_data.get('username', 'Unknown'),
                                username=stats_data.get('username')
                            )
                            session.add(user)
                            self.stats['users'] += 1
                        
                        # Create player stats
                        player_stats = PlayerStats(
                            user_id=user_id,
                            chat_id=chat_id,
                            score=stats_data.get('score', 0),
                            total_wins=stats_data.get('total_wins', stats_data.get('wins', 0)),
                            total_losses=stats_data.get('total_losses', stats_data.get('losses', 0)),
                            total_bets=stats_data.get('total_bets', 0),
                            last_active=datetime.fromisoformat(stats_data['last_active']) if 'last_active' in stats_data else datetime.utcnow()
                        )
                        
                        session.add(player_stats)
                        self.stats['player_stats'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error migrating player stats for user {user_id_str} in chat {chat_id_str}: {e}")
                        self.stats['errors'] += 1
                
                # Migrate match history to games
                match_history = chat_data.get('match_history', [])
                for match_data in match_history:
                    try:
                        # Check if game already exists
                        existing_game = session.query(Game).filter(
                            Game.match_id == match_data.get('match_id'),
                            Game.chat_id == chat_id
                        ).first()
                        if existing_game:
                            continue
                        
                        game = Game(
                            match_id=match_data.get('match_id'),
                            chat_id=chat_id,
                            state='OVER',
                            result=match_data.get('result', match_data.get('dice_result')),
                            dice_result=match_data.get('dice_result', match_data.get('result')),
                            winning_type=match_data.get('winning_type'),
                            total_bets=match_data.get('total_bets', 0),
                            participants=match_data.get('participants', []),
                            created_at=datetime.fromisoformat(match_data['timestamp']) if 'timestamp' in match_data else datetime.utcnow(),
                            completed_at=datetime.fromisoformat(match_data['timestamp']) if 'timestamp' in match_data else datetime.utcnow()
                        )
                        
                        session.add(game)
                        self.stats['games'] += 1
                        
                        # Migrate bets if available
                        bets_data = match_data.get('bets', {})
                        for bet_type, bet_users in bets_data.items():
                            if isinstance(bet_users, dict):
                                for user_id_str, bet_amount in bet_users.items():
                                    try:
                                        bet = Bet(
                                            game_id=game.id,
                                            user_id=int(user_id_str),
                                            bet_type=bet_type,
                                            amount=bet_amount,
                                            payout=0  # Will be calculated later if needed
                                        )
                                        session.add(bet)
                                        self.stats['bets'] += 1
                                    except Exception as e:
                                        logger.error(f"Error migrating bet: {e}")
                                        self.stats['errors'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error migrating game {match_data.get('match_id', 'unknown')}: {e}")
                        self.stats['errors'] += 1
                
            except Exception as e:
                logger.error(f"Error migrating chat {chat_id_str}: {e}")
                self.stats['errors'] += 1
    
    def migrate_admin_data(self, session, admin_data: Dict[str, Any]):
        """Migrate admin data."""
        logger.info("Migrating admin data...")
        
        for user_id_str, admin_info in admin_data.items():
            try:
                user_id = int(user_id_str)
                chat_points = admin_info.get('chat_points', {})
                
                for chat_id_str, points_data in chat_points.items():
                    try:
                        chat_id = int(chat_id_str)
                        
                        # Check if admin data already exists
                        existing_admin = session.query(AdminData).filter(
                            AdminData.user_id == user_id,
                            AdminData.chat_id == chat_id
                        ).first()
                        if existing_admin:
                            continue
                        
                        admin_data_obj = AdminData(
                            user_id=user_id,
                            chat_id=chat_id,
                            points=points_data.get('points', 0),
                            last_refill=datetime.fromisoformat(points_data['last_refill']) if points_data.get('last_refill') else None
                        )
                        
                        session.add(admin_data_obj)
                        self.stats['admin_data'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error migrating admin data for chat {chat_id_str}: {e}")
                        self.stats['errors'] += 1
                
            except Exception as e:
                logger.error(f"Error migrating admin {user_id_str}: {e}")
                self.stats['errors'] += 1
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        logger.info("Starting data migration from JSON to PostgreSQL...")
        
        # Initialize database
        if not init_database():
            logger.error("Failed to initialize database")
            return False
        
        # Load JSON data
        json_data = self.load_json_data()
        if not json_data:
            logger.warning("No JSON data to migrate")
            return True
        
        try:
            with get_db_session() as session:
                # Migrate in order: users first, then chats, then relationships
                if 'global_user_data' in json_data:
                    self.migrate_users(session, json_data['global_user_data'])
                
                if 'all_chat_data' in json_data:
                    self.migrate_chats_and_stats(session, json_data['all_chat_data'])
                
                if 'admin_data' in json_data:
                    self.migrate_admin_data(session, json_data['admin_data'])
                
                # Commit all changes
                session.commit()
                
                logger.info("Migration completed successfully!")
                logger.info(f"Migration statistics: {self.stats}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error during migration: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            return False
    
    def create_backup(self) -> str:
        """Create a backup of the current JSON file."""
        if not os.path.exists(self.json_file_path):
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.json_file_path}_backup_{timestamp}"
        
        try:
            import shutil
            shutil.copy2(self.json_file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return ""

def run_migration(json_file_path: str = "data.json") -> bool:
    """Convenience function to run migration."""
    migration = DataMigration(json_file_path)
    
    # Create backup first
    backup_path = migration.create_backup()
    if backup_path:
        logger.info(f"Backup created at: {backup_path}")
    
    return migration.run_migration()

if __name__ == "__main__":
    # Run migration if script is executed directly
    success = run_migration()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed. Check logs for details.")