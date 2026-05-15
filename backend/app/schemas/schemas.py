# app/schemas/schemas.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Player Schemas ────────────────────────────────────────────────────────────

class PlayerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=7, max_length=20)
    tekken_name: str = Field(..., min_length=2, max_length=50)
    college_name: Optional[str] = Field(None, max_length=150)
    department: Optional[str] = Field(None, max_length=100)
    registration_paid: bool = False
    amount_paid: Optional[float] = Field(None, ge=0)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        cleaned = v.replace(" ", "").replace("-", "").replace("+", "")
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v

    @field_validator("tekken_name")
    @classmethod
    def validate_tekken_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Tekken name must be at least 2 characters")
        return v.strip()


class PlayerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone_number: Optional[str] = Field(None, min_length=7, max_length=20)
    tekken_name: Optional[str] = Field(None, min_length=2, max_length=50)
    college_name: Optional[str] = None
    department: Optional[str] = None
    registration_paid: Optional[bool] = None
    amount_paid: Optional[float] = Field(None, ge=0)


class PlayerStatsOut(BaseModel):
    total_matches: int
    wins: int
    losses: int
    win_ratio: float
    current_streak: int
    highest_streak: int
    score: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    amount_paid: float
    payment_method: Optional[str]
    notes: Optional[str]
    paid_at: datetime

    model_config = {"from_attributes": True}


class PlayerOut(BaseModel):
    id: int
    full_name: str
    phone_number: str
    tekken_name: str
    college_name: Optional[str]
    department: Optional[str]
    registration_paid: bool
    created_at: datetime
    stats: Optional[PlayerStatsOut] = None
    payment: Optional[PaymentOut] = None

    model_config = {"from_attributes": True}


# ─── Match Schemas ─────────────────────────────────────────────────────────────

class MatchStart(BaseModel):
    player1_id: int = Field(..., gt=0)
    player2_id: int = Field(..., gt=0)
    round_type: str = Field(default="regular", max_length=50)
    match_notes: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def players_must_differ(self):
        if self.player1_id == self.player2_id:
            raise ValueError("player1 and player2 must be different players")
        return self


class MatchResult(BaseModel):
    match_id: int = Field(..., gt=0)
    winner_id: int = Field(..., gt=0)


class RematchRequest(BaseModel):
    match_id: int = Field(..., gt=0)
    match_notes: Optional[str] = Field(None, max_length=500)


class MatchOut(BaseModel):
    id: int
    player1_id: int
    player2_id: int
    winner_id: Optional[int]
    loser_id: Optional[int]
    is_rematch: bool
    parent_match_id: Optional[int]
    round_type: str
    match_notes: Optional[str]
    played_at: datetime
    # Enriched fields (joined)
    player1_name: Optional[str] = None
    player2_name: Optional[str] = None
    winner_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Leaderboard Schemas ───────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    player_id: int
    full_name: str
    tekken_name: str
    college_name: Optional[str]
    wins: int
    losses: int
    win_ratio: float
    current_streak: int
    highest_streak: int
    total_matches: int
    score: int

    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    last_updated: datetime
    total_players: int


# ─── Admin Log Schemas ─────────────────────────────────────────────────────────

class AdminLogOut(BaseModel):
    id: int
    action_type: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── WebSocket Message ─────────────────────────────────────────────────────────

class WSLeaderboardMessage(BaseModel):
    type: str = "leaderboard_update"
    data: LeaderboardResponse


# ─── Generic Response ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True