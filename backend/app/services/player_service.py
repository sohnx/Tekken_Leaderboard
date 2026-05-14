# app/services/player_service.py
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Player, PlayerStats, AdminLog
from app.schemas import PlayerCreate, PlayerUpdate

logger = logging.getLogger(__name__)


async def create_player(db: AsyncSession, data: PlayerCreate) -> Player:
    """Register a new player and initialize their stats."""

    # Check for duplicate phone
    existing_phone = await db.execute(
        select(Player).where(Player.phone_number == data.phone_number)
    )
    if existing_phone.scalar_one_or_none():
        raise ValueError(f"Phone number {data.phone_number} is already registered.")

    # Check for duplicate tekken name
    existing_tag = await db.execute(
        select(Player).where(Player.tekken_name == data.tekken_name)
    )
    if existing_tag.scalar_one_or_none():
        raise ValueError(f"Tekken name '{data.tekken_name}' is already taken.")

    # Create player
    player = Player(**data.model_dump())
    db.add(player)
    await db.flush()  # Get the ID

    # Initialize stats
    stats = PlayerStats(player_id=player.id)
    db.add(stats)

    # Log action
    log = AdminLog(
        action_type="REGISTER",
        description=f"Registered player: {player.full_name} (Tag: {player.tekken_name}, Phone: {player.phone_number})"
    )
    db.add(log)

    await db.commit()
    await db.refresh(player)

    # Reload with stats
    result = await db.execute(
        select(Player).options(selectinload(Player.stats)).where(Player.id == player.id)
    )
    return result.scalar_one()


async def get_player(db: AsyncSession, player_id: int) -> Optional[Player]:
    """Get a single player with stats."""
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats))
        .where(Player.id == player_id)
    )
    return result.scalar_one_or_none()


async def get_all_players(db: AsyncSession) -> list[Player]:
    """Get all players with their stats."""
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats))
        .order_by(Player.created_at.desc())
    )
    return list(result.scalars().all())


async def update_player(db: AsyncSession, player_id: int, data: PlayerUpdate) -> Optional[Player]:
    """Update player details."""
    player = await get_player(db, player_id)
    if not player:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Check uniqueness if updating phone or tekken name
    if "phone_number" in update_data:
        existing = await db.execute(
            select(Player).where(
                Player.phone_number == update_data["phone_number"],
                Player.id != player_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Phone number already in use.")

    if "tekken_name" in update_data:
        existing = await db.execute(
            select(Player).where(
                Player.tekken_name == update_data["tekken_name"],
                Player.id != player_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Tekken name already taken.")

    for field, value in update_data.items():
        setattr(player, field, value)

    log = AdminLog(
        action_type="UPDATE",
        description=f"Updated player ID {player_id}: {list(update_data.keys())}"
    )
    db.add(log)

    await db.commit()
    await db.refresh(player)

    result = await db.execute(
        select(Player).options(selectinload(Player.stats)).where(Player.id == player.id)
    )
    return result.scalar_one()


async def delete_player(db: AsyncSession, player_id: int) -> bool:
    """Delete a player.
    
    ✅ FIX #5: Match FKs use ondelete=RESTRICT, so deleting a player who has
    match records raises IntegrityError. We catch it here and surface a clean
    ValueError so the router returns a 400 instead of a 500.
    """
    player = await get_player(db, player_id)
    if not player:
        return False

    log = AdminLog(
        action_type="DELETE",
        description=f"Deleted player: {player.full_name} (Tag: {player.tekken_name})"
    )
    db.add(log)

    try:
        await db.delete(player)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError(
            f"Cannot delete '{player.tekken_name}' — they have existing match records. "
            "Remove their matches first or keep them in the system."
        )
    return True
