# app/services/match_service.py
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, Player, PlayerStats, AdminLog
from app.schemas import MatchStart, MatchResult, RematchRequest

logger = logging.getLogger(__name__)


async def _get_or_init_stats(db: AsyncSession, player_id: int) -> PlayerStats:
    """Get player stats or create if missing."""
    result = await db.execute(
        select(PlayerStats).where(PlayerStats.player_id == player_id)
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = PlayerStats(player_id=player_id)
        db.add(stats)
        await db.flush()
    return stats


async def start_match(db: AsyncSession, data: MatchStart) -> Match:
    """Create a pending match (no winner yet)."""

    # Verify both players exist
    for pid in [data.player1_id, data.player2_id]:
        p = await db.execute(select(Player).where(Player.id == pid))
        if not p.scalar_one_or_none():
            raise ValueError(f"Player with ID {pid} not found.")

    # ✅ FIX #4: Use explicit or_() / and_() to guarantee correct SQL precedence.
    # The old `(A & B | C & D)` without or_() could produce wrong SQL depending
    # on SQLAlchemy version and operator binding order.
    active = await db.execute(
        select(Match).where(
            Match.winner_id.is_(None),
            or_(
                and_(Match.player1_id == data.player1_id, Match.player2_id == data.player2_id),
                and_(Match.player1_id == data.player2_id, Match.player2_id == data.player1_id),
            )
        )
    )
    if active.scalar_one_or_none():
        raise ValueError("An unfinished match between these players already exists.")

    match = Match(
        player1_id=data.player1_id,
        player2_id=data.player2_id,
        round_type=data.round_type,
        match_notes=data.match_notes,
        is_rematch=False,
    )
    db.add(match)

    # Fetch player names for logging
    p1 = await db.execute(select(Player).where(Player.id == data.player1_id))
    p2 = await db.execute(select(Player).where(Player.id == data.player2_id))
    p1_obj = p1.scalar_one()
    p2_obj = p2.scalar_one()

    log = AdminLog(
        action_type="MATCH_START",
        description=f"Match started: {p1_obj.tekken_name} vs {p2_obj.tekken_name} [{data.round_type}]"
    )
    db.add(log)

    await db.commit()
    await db.refresh(match)
    return match


async def record_result(db: AsyncSession, data: MatchResult) -> Match:
    """Record match winner and update player stats atomically."""

    result = await db.execute(
        select(Match)
        .options(selectinload(Match.player1), selectinload(Match.player2))
        .where(Match.id == data.match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise ValueError(f"Match ID {data.match_id} not found.")
    if match.winner_id is not None:
        raise ValueError("This match already has a recorded result.")

    # Validate winner
    if data.winner_id not in [match.player1_id, match.player2_id]:
        raise ValueError("Winner must be one of the two players in this match.")

    loser_id = match.player2_id if data.winner_id == match.player1_id else match.player1_id

    # Update match record
    match.winner_id = data.winner_id
    match.loser_id = loser_id
    # ✅ FIX: Use timezone-aware UTC datetime (utcnow() is deprecated in Python 3.12)
    match.played_at = datetime.now(timezone.utc)

    # Update winner stats
    winner_stats = await _get_or_init_stats(db, data.winner_id)
    winner_stats.total_matches += 1
    winner_stats.wins += 1
    winner_stats.current_streak += 1
    if winner_stats.current_streak > winner_stats.highest_streak:
        winner_stats.highest_streak = winner_stats.current_streak
    winner_stats.recalculate()

    # Update loser stats
    loser_stats = await _get_or_init_stats(db, loser_id)
    loser_stats.total_matches += 1
    loser_stats.losses += 1
    loser_stats.current_streak = 0  # Reset streak on loss
    loser_stats.recalculate()

    # Log action
    p1_name = match.player1.tekken_name
    p2_name = match.player2.tekken_name
    winner_name = p1_name if data.winner_id == match.player1_id else p2_name
    log = AdminLog(
        action_type="MATCH_RESULT",
        description=f"Result recorded: {p1_name} vs {p2_name} → Winner: {winner_name}"
    )
    db.add(log)

    await db.commit()
    await db.refresh(match)
    return match


async def create_rematch(db: AsyncSession, data: RematchRequest) -> Match:
    """Create a rematch from an existing finished match."""

    result = await db.execute(
        select(Match)
        .options(selectinload(Match.player1), selectinload(Match.player2))
        .where(Match.id == data.match_id)
    )
    original = result.scalar_one_or_none()
    if not original:
        raise ValueError(f"Match ID {data.match_id} not found.")
    # ✅ FIX: Also check loser_id is set — winner_id alone isn't enough
    if original.winner_id is None or original.loser_id is None:
        raise ValueError("Cannot rematch an unfinished match. Record result first.")

    # Create rematch - swap player positions to give loser first pick
    rematch = Match(
        player1_id=original.loser_id,    # Loser gets first position
        player2_id=original.winner_id,
        is_rematch=True,
        parent_match_id=original.id,
        round_type="rematch",
        match_notes=data.match_notes or f"Rematch of match #{original.id}",
    )
    db.add(rematch)

    p1_name = original.player1.tekken_name
    p2_name = original.player2.tekken_name
    log = AdminLog(
        action_type="REMATCH",
        description=f"Rematch created: {p1_name} vs {p2_name} (Original match #{original.id})"
    )
    db.add(log)

    await db.commit()
    await db.refresh(rematch)
    return rematch


async def undo_last_match(db: AsyncSession) -> dict:
    """
    Undo the last completed match, restoring player stats to previous state.
    Uses a transaction for safety.
    """
    # Find last completed match
    result = await db.execute(
        select(Match)
        .where(Match.winner_id.isnot(None))
        .order_by(desc(Match.played_at))
        .limit(1)
    )
    last_match = result.scalar_one_or_none()
    if not last_match:
        raise ValueError("No completed matches to undo.")

    winner_id = last_match.winner_id
    loser_id = last_match.loser_id

    # Reverse winner stats
    winner_stats = await _get_or_init_stats(db, winner_id)
    winner_stats.total_matches = max(0, winner_stats.total_matches - 1)
    winner_stats.wins = max(0, winner_stats.wins - 1)
    winner_stats.current_streak = max(0, winner_stats.current_streak - 1)
    # NOTE: highest_streak cannot be perfectly restored without full history.
    # We leave it as-is (conservative). For a perfect undo, recalculate from
    # match history — acceptable trade-off for a tournament tool.
    winner_stats.recalculate()

    # Reverse loser stats
    loser_stats = await _get_or_init_stats(db, loser_id)
    loser_stats.total_matches = max(0, loser_stats.total_matches - 1)
    loser_stats.losses = max(0, loser_stats.losses - 1)
    # NOTE: loser's pre-loss streak cannot be restored without history snapshot.
    loser_stats.recalculate()

    match_info = {
        "match_id": last_match.id,
        "player1_id": last_match.player1_id,
        "player2_id": last_match.player2_id,
        "winner_id": winner_id,
    }

    # Remove the match record
    await db.delete(last_match)

    log = AdminLog(
        action_type="UNDO",
        description=f"Undid match #{match_info['match_id']}: winner was player ID {winner_id}"
    )
    db.add(log)

    await db.commit()
    return match_info


async def get_match_history(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Get recent match history with player names."""
    result = await db.execute(
        select(Match)
        .options(
            selectinload(Match.player1),
            selectinload(Match.player2),
            selectinload(Match.winner),
        )
        .order_by(desc(Match.played_at))
        .limit(limit)
    )
    matches = result.scalars().all()

    history = []
    for m in matches:
        history.append({
            "id": m.id,
            "player1_id": m.player1_id,
            "player2_id": m.player2_id,
            "winner_id": m.winner_id,
            "loser_id": m.loser_id,
            "is_rematch": m.is_rematch,
            "parent_match_id": m.parent_match_id,
            "round_type": m.round_type,
            "match_notes": m.match_notes,
            "played_at": m.played_at.isoformat() if m.played_at else None,
            "player1_name": m.player1.tekken_name if m.player1 else None,
            "player2_name": m.player2.tekken_name if m.player2 else None,
            "winner_name": m.winner.tekken_name if m.winner_id and m.winner else None,
            "status": "completed" if m.winner_id else "pending",
        })

    return history
