# app/services/leaderboard_service.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Player, PlayerStats


async def get_leaderboard(db: AsyncSession, limit: Optional[int] = None) -> dict:
    """
    Build the ranked leaderboard.
    Scoring: Score = (Wins × 3) - Losses + (CurrentStreak × 2)
    Secondary sort: win_ratio, then total_wins, then name.

    ✅ FIX: Removed duplicate `from typing import Optional` at bottom of file.
    ✅ FIX: Use datetime.now(timezone.utc) instead of deprecated datetime.utcnow().
    ✅ FIX: top10 limit now correctly caps the second "no-stats" loop too.
    """
    query = (
        select(Player, PlayerStats)
        .join(PlayerStats, Player.id == PlayerStats.player_id)
        .where(Player.registration_paid == True)
        .order_by(
            desc(PlayerStats.score),
            desc(PlayerStats.win_ratio),
            desc(PlayerStats.wins),
            Player.tekken_name,
        )
    )
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    rows = result.all()

    entries = []
    for rank, (player, stats) in enumerate(rows, start=1):
        entries.append({
            "rank": rank,
            "player_id": player.id,
            "full_name": player.full_name,
            "tekken_name": player.tekken_name,
            "college_name": player.college_name,
            "wins": stats.wins,
            "losses": stats.losses,
            "win_ratio": round(stats.win_ratio * 100, 1),  # as percentage
            "current_streak": stats.current_streak,
            "highest_streak": stats.highest_streak,
            "total_matches": stats.total_matches,
            "score": stats.score,
        })

    # Also include paid players with missing stats rows at the bottom
    # (edge case: stats row missing due to race condition or manual DB insert)
    all_players_res = await db.execute(
        select(Player)
        .options(selectinload(Player.stats))
        .where(Player.registration_paid == True)
    )
    all_players = all_players_res.scalars().all()
    registered_ids = {e["player_id"] for e in entries}

    for player in all_players:
        # ✅ FIX: Respect the limit in this second loop too
        if limit and len(entries) >= limit:
            break
        if player.id not in registered_ids:
            entries.append({
                "rank": len(entries) + 1,
                "player_id": player.id,
                "full_name": player.full_name,
                "tekken_name": player.tekken_name,
                "college_name": player.college_name,
                "wins": 0,
                "losses": 0,
                "win_ratio": 0.0,
                "current_streak": 0,
                "highest_streak": 0,
                "total_matches": 0,
                "score": 0,
            })

    return {
        "entries": entries,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_players": len(entries),
    }
