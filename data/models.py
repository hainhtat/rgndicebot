from datetime import datetime
from typing import Dict, List, Optional, Set, Union, Any


class PlayerStats:
    """
    Represents a player's statistics in a specific chat.
    """
    def __init__(self, username: str, score: int = 0, total_wins: int = 0, total_losses: int = 0):
        self.username = username
        self.score = score
        self.total_wins = total_wins
        self.total_losses = total_losses
        self.last_active = datetime.now()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerStats':
        """
        Create a PlayerStats instance from a dictionary.
        """
        player = cls(
            username=data.get('username', 'Unknown'),
            score=data.get('score', 0),
            total_wins=data.get('total_wins', 0),
            total_losses=data.get('total_losses', 0)
        )
        if 'last_active' in data:
            player.last_active = data['last_active']
        return player

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PlayerStats instance to a dictionary.
        """
        return {
            'username': self.username,
            'score': self.score,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'last_active': self.last_active
        }


class GlobalUserData:
    """
    Represents a user's global data across all chats.
    """
    def __init__(self, full_name: str, username: Optional[str] = None, 
                 referral_points: int = 0, referred_by: Optional[int] = None,
                 pending_referrer_id: Optional[int] = None):
        self.full_name = full_name
        self.username = username
        self.referral_points = referral_points
        self.referred_by = referred_by
        self.pending_referrer_id = pending_referrer_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalUserData':
        """
        Create a GlobalUserData instance from a dictionary.
        """
        return cls(
            full_name=data.get('full_name', 'Unknown'),
            username=data.get('username'),
            referral_points=data.get('referral_points', 0),
            referred_by=data.get('referred_by'),
            pending_referrer_id=data.get('pending_referrer_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the GlobalUserData instance to a dictionary.
        """
        return {
            'full_name': self.full_name,
            'username': self.username,
            'referral_points': self.referral_points,
            'referred_by': self.referred_by,
            'pending_referrer_id': self.pending_referrer_id
        }


class AdminData:
    """
    Represents an admin's data with points per chat.
    """
    def __init__(self, username: str):
        self.username = username
        self.chat_points: Dict[str, Dict[str, Any]] = {}

    def get_chat_points(self, chat_id: int) -> Dict[str, Any]:
        """
        Get the admin's points for a specific chat.
        """
        chat_id_str = str(chat_id)
        if chat_id_str not in self.chat_points:
            self.chat_points[chat_id_str] = {
                'points': 0,
                'last_refill': None
            }
        return self.chat_points[chat_id_str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdminData':
        """
        Create an AdminData instance from a dictionary.
        """
        admin = cls(username=data.get('username', 'Unknown Admin'))
        admin.chat_points = data.get('chat_points', {})
        return admin

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the AdminData instance to a dictionary.
        """
        return {
            'username': self.username,
            'chat_points': self.chat_points
        }


class ChatData:
    """
    Represents chat-specific data.
    """
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.player_stats: Dict[str, PlayerStats] = {}
        self.match_counter: int = 1
        self.match_history: List[Dict[str, Any]] = []
        self.group_admins: List[int] = []
        self.consecutive_idle_matches: int = 0
        self.current_game = None

    @classmethod
    def from_dict(cls, chat_id: int, data: Dict[str, Any]) -> 'ChatData':
        """
        Create a ChatData instance from a dictionary.
        """
        chat_data = cls(chat_id)
        chat_data.match_counter = data.get('match_counter', 1)
        chat_data.match_history = data.get('match_history', [])
        chat_data.group_admins = data.get('group_admins', [])
        chat_data.consecutive_idle_matches = data.get('consecutive_idle_matches', 0)
        
        # Convert player_stats dict to PlayerStats objects
        for user_id, stats in data.get('player_stats', {}).items():
            chat_data.player_stats[user_id] = PlayerStats.from_dict(stats)
        
        return chat_data

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ChatData instance to a dictionary.
        """
        # Convert PlayerStats objects to dicts
        player_stats_dict = {}
        for user_id, stats in self.player_stats.items():
            player_stats_dict[user_id] = stats.to_dict()
        
        return {
            'player_stats': player_stats_dict,
            'match_counter': self.match_counter,
            'match_history': self.match_history,
            'group_admins': self.group_admins,
            'consecutive_idle_matches': self.consecutive_idle_matches
        }