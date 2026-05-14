# app/routers/players.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PlayerCreate, PlayerUpdate, PlayerOut, MessageResponse
from app.services import create_player, get_player, get_all_players, update_player, delete_player

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/players", tags=["Players"])


@router.post("/register", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
async def register_player(data: PlayerCreate, db: AsyncSession = Depends(get_db)):
    """Register a new tournament player."""
    try:
        player = await create_player(db, data)
        return player
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error registering player")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[PlayerOut])
async def list_players(db: AsyncSession = Depends(get_db)):
    """Get all registered players with their stats."""
    return await get_all_players(db)


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player_detail(player_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single player by ID."""
    player = await get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.put("/{player_id}", response_model=PlayerOut)
async def update_player_detail(
    player_id: int,
    data: PlayerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update player information."""
    try:
        player = await update_player(db, player_id, data)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return player
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{player_id}", response_model=MessageResponse)
async def delete_player_route(player_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a player from the tournament."""
    try:
        deleted = await delete_player(db, player_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Player not found")
        return MessageResponse(message=f"Player {player_id} deleted successfully.")
    except ValueError as e:
        # ✅ FIX #5 (router side): Surface the IntegrityError as a clean 400
        raise HTTPException(status_code=400, detail=str(e))
