# app/models/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Float,
    DateTime, ForeignKey, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False, unique=True)
    tekken_name = Column(String(50), nullable=False, unique=True)
    college_name = Column(String(150), nullable=True)
    department = Column(String(100), nullable=True)
    registration_paid = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    stats = relationship("PlayerStats", back_populates="player", uselist=False, cascade="all, delete-orphan")
    matches_as_p1 = relationship("Match", foreign_keys="Match.player1_id", back_populates="player1")
    matches_as_p2 = relationship("Match", foreign_keys="Match.player2_id", back_populates="player2")
    wins = relationship("Match", foreign_keys="Match.winner_id", back_populates="winner")
    losses = relationship("Match", foreign_keys="Match.loser_id", back_populates="loser")

    __table_args__ = (
        Index("ix_players_tekken_name", "tekken_name"),
        Index("ix_players_phone", "phone_number"),
    )

    def __repr__(self):
        return f"<Player {self.tekken_name}>"


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("players.id", ondelete="RESTRICT"), nullable=False)
    player2_id = Column(Integer, ForeignKey("players.id", ondelete="RESTRICT"), nullable=False)
    winner_id = Column(Integer, ForeignKey("players.id", ondelete="RESTRICT"), nullable=True)
    loser_id = Column(Integer, ForeignKey("players.id", ondelete="RESTRICT"), nullable=True)
    is_rematch = Column(Boolean, default=False, nullable=False)
    parent_match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    round_type = Column(String(50), default="regular", nullable=False)
    match_notes = Column(Text, nullable=True)
    played_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    player1 = relationship("Player", foreign_keys=[player1_id], back_populates="matches_as_p1")
    player2 = relationship("Player", foreign_keys=[player2_id], back_populates="matches_as_p2")
    winner = relationship("Player", foreign_keys=[winner_id], back_populates="wins")
    loser = relationship("Player", foreign_keys=[loser_id], back_populates="losses")
    parent_match = relationship("Match", remote_side=[id], foreign_keys=[parent_match_id])

    __table_args__ = (
        Index("ix_matches_played_at", "played_at"),
        Index("ix_matches_player1", "player1_id"),
        Index("ix_matches_player2", "player2_id"),
    )

    def __repr__(self):
        return f"<Match {self.id}: P{self.player1_id} vs P{self.player2_id}>"


class PlayerStats(Base):
    __tablename__ = "player_stats"

    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    total_matches = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    win_ratio = Column(Float, default=0.0, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    highest_streak = Column(Integer, default=0, nullable=False)
    score = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    player = relationship("Player", back_populates="stats")

    __table_args__ = (
        Index("ix_player_stats_score", "score"),
    )

    def recalculate(self):
        """Recalculate derived stats. Score = (Wins×4) + (Losses×1)"""
        if self.total_matches > 0:
            self.win_ratio = round(self.wins / self.total_matches, 4)
        else:
            self.win_ratio = 0.0
        self.score = (self.wins * 4) + self.losses

    def __repr__(self):
        return f"<PlayerStats player={self.player_id} score={self.score}>"


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_admin_logs_created_at", "created_at"),
        Index("ix_admin_logs_action_type", "action_type"),
    )

    def __repr__(self):
        return f"<AdminLog {self.action_type}: {self.description[:40]}>"