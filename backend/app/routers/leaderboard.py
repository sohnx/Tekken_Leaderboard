# app/routers/leaderboard.py
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.services.leaderboard_service import get_leaderboard
from app.websocket import manager
from app.models import AdminLog

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Leaderboard"])


@router.get("/leaderboard")
async def get_full_leaderboard(db: AsyncSession = Depends(get_db)):
    """Get the full leaderboard sorted by score."""
    return await get_leaderboard(db)


@router.get("/leaderboard/top10")
async def get_top10(db: AsyncSession = Depends(get_db)):
    """Get top 10 players."""
    data = await get_leaderboard(db, limit=10)
    data["entries"] = data["entries"][:10]
    return data


@router.websocket("/ws/leaderboard")
async def leaderboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time leaderboard updates.
    
    ✅ FIX #2: Removed `db: AsyncSession = Depends(get_db)` from this endpoint.
    The old version held a DB session open for the entire lifetime of the WebSocket
    connection (could be hours), exhausting the connection pool (capped at 10).
    
    Now we open a short-lived session ONLY for the initial snapshot, release it
    immediately, then run the keep-alive loop without any DB connection held.
    Subsequent updates are pushed by the broadcast system when results are recorded.
    """
    await manager.connect(websocket)
    try:
        # Open a short-lived session just for the initial leaderboard snapshot
        async with AsyncSessionLocal() as db:
            leaderboard = await get_leaderboard(db)
        # Session is closed here — connection returned to pool immediately

        await websocket.send_text(json.dumps({
            "type": "leaderboard_update",
            "data": leaderboard,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, default=str))

        # Keep alive: listen for ping/pong — no DB connection held
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type":"pong"}')

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


@router.get("/admin/logs")
async def get_admin_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Get recent admin action logs."""
    from sqlalchemy import select, desc
    result = await db.execute(
        select(AdminLog).order_by(desc(AdminLog.created_at)).limit(min(limit, 500))
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": l.id,
                "action_type": l.action_type,
                "description": l.description,
                "created_at": l.created_at.isoformat()
            }
            for l in logs
        ]
    }
