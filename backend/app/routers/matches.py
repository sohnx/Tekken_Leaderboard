# app/routers/matches.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import MatchStart, MatchResult, RematchRequest, MessageResponse
from app.services import start_match, record_result, create_rematch, undo_last_match, get_match_history
from app.services.leaderboard_service import get_leaderboard
from app.websocket import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/matches", tags=["Matches"])


@router.post("/start")
async def start_new_match(data: MatchStart, db: AsyncSession = Depends(get_db)):
    """Start a new match between two players."""
    try:
        match = await start_match(db, data)
        # Notify connected clients — non-fatal if WS fails
        try:
            await manager.broadcast_match_event("match_started", {
                "match_id": match.id,
                "player1_id": match.player1_id,
                "player2_id": match.player2_id,
                "round_type": match.round_type,
            })
        except Exception:
            logger.warning("WebSocket broadcast failed after starting match — match was still created")
        return {"message": "Match started", "match_id": match.id, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Error starting match")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/result")
async def record_match_result(data: MatchResult, db: AsyncSession = Depends(get_db)):
    """Record the result of a match and update stats + leaderboard."""
    try:
        match = await record_result(db, data)

        # Broadcast updated leaderboard — non-fatal if WS fails
        try:
            leaderboard = await get_leaderboard(db)
            await manager.broadcast_leaderboard(leaderboard)
            await manager.broadcast_match_event("match_result", {
                "match_id": match.id,
                "winner_id": match.winner_id,
                "loser_id": match.loser_id,
            })
        except Exception:
            logger.warning("WebSocket broadcast failed after recording result — result was still saved")

        return {"message": "Result recorded", "match_id": match.id, "winner_id": match.winner_id, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Error recording result")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/rematch")
async def rematch(data: RematchRequest, db: AsyncSession = Depends(get_db)):
    """Create a rematch from an existing match."""
    try:
        match = await create_rematch(db, data)
        await manager.broadcast_match_event("rematch_started", {
            "match_id": match.id,
            "parent_match_id": match.parent_match_id,
            "player1_id": match.player1_id,
            "player2_id": match.player2_id,
        })
        return {"message": "Rematch created", "match_id": match.id, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/undo-last")
async def undo_last(db: AsyncSession = Depends(get_db)):
    """Undo the last completed match and restore stats."""
    try:
        info = await undo_last_match(db)

        # Broadcast updated leaderboard after undo — non-fatal if WS fails
        try:
            leaderboard = await get_leaderboard(db)
            await manager.broadcast_leaderboard(leaderboard)
            await manager.broadcast_match_event("match_undone", info)
        except Exception:
            logger.warning("WebSocket broadcast failed after undo — undo was still applied")

        return {"message": "Last match undone successfully", "undone_match": info, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Error undoing match")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
async def match_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent match history."""
    history = await get_match_history(db, limit=min(limit, 200))
    return {"matches": history, "count": len(history)}