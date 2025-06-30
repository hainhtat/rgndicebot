"""SQLAlchemy models for the dicebot database."""

from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .connection import Base

class User(Base):
    """Global user data across all chats."""
    __tablename__ = 'users'
    
    user_id = Column(BigInteger, primary_key=True)
    full_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    referral_points = Column(Integer, default=0)
    referred_by = Column(BigInteger, ForeignKey('users.user_id'), nullable=True)
    pending_referrer_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    referrer = relationship("User", remote_side=[user_id], backref="referred_users")
    player_stats = relationship("PlayerStats", back_populates="user", cascade="all, delete-orphan")
    bets = relationship("Bet", back_populates="user", cascade="all, delete-orphan")
    admin_data = relationship("AdminData", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}', full_name='{self.full_name}')>"

class Chat(Base):
    """Chat-specific data."""
    __tablename__ = 'chats'
    
    chat_id = Column(BigInteger, primary_key=True)
    match_counter = Column(Integer, default=1)
    consecutive_idle_matches = Column(Integer, default=0)
    group_admins = Column(JSON, default=list)  # Store list of admin user IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    player_stats = relationship("PlayerStats", back_populates="chat", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="chat", cascade="all, delete-orphan")
    admin_data = relationship("AdminData", back_populates="chat", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Chat(chat_id={self.chat_id}, match_counter={self.match_counter})>"

class PlayerStats(Base):
    """Player statistics for a specific chat."""
    __tablename__ = 'player_stats'
    
    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id'), primary_key=True)
    score = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    total_losses = Column(Integer, default=0)
    total_bets = Column(Integer, default=0)
    last_active = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="player_stats")
    chat = relationship("Chat", back_populates="player_stats")
    
    def __repr__(self):
        return f"<PlayerStats(user_id={self.user_id}, chat_id={self.chat_id}, score={self.score})>"

class Game(Base):
    """Game/match data."""
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, nullable=False)  # Match ID within the chat
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id'), nullable=False)
    state = Column(String(20), default='WAITING')  # WAITING, CLOSED, OVER
    result = Column(JSON, nullable=True)  # Dice results [int, int]
    dice_result = Column(JSON, nullable=True)  # Same as result for compatibility
    winning_type = Column(String(20), nullable=True)  # BIG, SMALL, LUCKY
    total_bets = Column(Integer, default=0)
    participants = Column(JSON, default=list)  # List of participant user IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat = relationship("Chat", back_populates="games")
    bets = relationship("Bet", back_populates="game", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Game(id={self.id}, match_id={self.match_id}, chat_id={self.chat_id}, state='{self.state}')>"

class Bet(Base):
    """Individual bet data."""
    __tablename__ = 'bets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    bet_type = Column(String(20), nullable=False)  # BIG, SMALL, LUCKY
    amount = Column(Integer, nullable=False)
    referral_points_used = Column(Integer, default=0)
    payout = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("Game", back_populates="bets")
    user = relationship("User", back_populates="bets")
    
    def __repr__(self):
        return f"<Bet(id={self.id}, user_id={self.user_id}, bet_type='{self.bet_type}', amount={self.amount})>"

class AdminData(Base):
    """Admin points data for specific chats."""
    __tablename__ = 'admin_data'
    
    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id'), primary_key=True)
    points = Column(Integer, default=0)
    last_refill = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="admin_data")
    chat = relationship("Chat", back_populates="admin_data")
    
    def __repr__(self):
        return f"<AdminData(user_id={self.user_id}, chat_id={self.chat_id}, points={self.points})>"

class DailyLoss(Base):
    """Daily loss tracking for cashback calculations."""
    __tablename__ = 'daily_losses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    chat_id = Column(String, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD format
    total_loss = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LogEntry(Base):
    """Application log entries stored in database."""
    __tablename__ = 'log_entries'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(10), nullable=False)  # INFO, WARNING, ERROR, etc.
    logger_name = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    module = Column(String(50))
    function = Column(String(50))
    line_number = Column(Integer)
    exception_info = Column(Text)  # Stack trace if available
    extra_data = Column(JSON)  # Additional context data
    created_at = Column(DateTime, default=datetime.utcnow)