# app/services/player_service.py

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Player, PlayerStats, AdminLog, RegistrationPayment
from app.schemas import PlayerCreate, PlayerUpdate

logger = logging.getLogger(__name__)


async def create_player(db: AsyncSession, data: PlayerCreate) -> Player:
    """Register a new player and initialize their stats."""

    # Check for duplicate phone
    existing_phone = await db.execute(
        select(Player).where(Player.phone_number == data.phone_number)
    )

    if existing_phone.scalar_one_or_none():
        raise ValueError(
            f"Phone number {data.phone_number} is already registered."
        )

    # Check for duplicate tekken name
    existing_tag = await db.execute(
        select(Player).where(Player.tekken_name == data.tekken_name)
    )

    if existing_tag.scalar_one_or_none():
        raise ValueError(
            f"Tekken name '{data.tekken_name}' is already taken."
        )

    # Create player (exclude amount_paid — it goes to separate table)
    player_data = data.model_dump(exclude={"amount_paid"})
    player = Player(**player_data)
    db.add(player)

    # Get generated ID
    await db.flush()

    # Initialize stats
    stats = PlayerStats(player_id=player.id)
    db.add(stats)

    # Create payment record if paid
    if data.registration_paid and data.amount_paid is not None:
        payment = RegistrationPayment(
            player_id=player.id,
            amount_paid=data.amount_paid,
        )
        db.add(payment)

    # Log registration
    log = AdminLog(
        action_type="REGISTER",
        description=(
            f"Registered player: {player.full_name} "
            f"(Tag: {player.tekken_name}, "
            f"Phone: {player.phone_number})"
        )
    )

    db.add(log)

    await db.commit()
    await db.refresh(player)

    # Reload with stats
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats), selectinload(Player.payment))
        .where(Player.id == player.id)
    )

    return result.scalar_one()


async def get_player(
    db: AsyncSession,
    player_id: int
) -> Optional[Player]:
    """Get a single player with stats."""

    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats), selectinload(Player.payment))
        .where(Player.id == player_id)
    )

    return result.scalar_one_or_none()


async def get_all_players(db: AsyncSession) -> list[Player]:
    """Get all players with their stats."""

    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats), selectinload(Player.payment))
        .order_by(Player.created_at.desc())
    )

    return list(result.scalars().all())


async def update_player(
    db: AsyncSession,
    player_id: int,
    data: PlayerUpdate
) -> Optional[Player]:
    """Update player details."""

    player = await get_player(db, player_id)

    if not player:
        return None

    update_data = data.model_dump(exclude_unset=True)
    amount_paid = update_data.pop("amount_paid", None)  # handle separately

    # Check uniqueness if updating phone number
    if "phone_number" in update_data:

        existing = await db.execute(
            select(Player).where(
                Player.phone_number == update_data["phone_number"],
                Player.id != player_id
            )
        )

        if existing.scalar_one_or_none():
            raise ValueError("Phone number already in use.")

    # Check uniqueness if updating tekken name
    if "tekken_name" in update_data:

        existing = await db.execute(
            select(Player).where(
                Player.tekken_name == update_data["tekken_name"],
                Player.id != player_id
            )
        )

        if existing.scalar_one_or_none():
            raise ValueError("Tekken name already taken.")

    # Track changes for logging
    changes = []

    for field, value in update_data.items():

        old_value = getattr(player, field)

        changes.append(
            f"{field}: '{old_value}' -> '{value}'"
        )

        setattr(player, field, value)

    # Update payment record if amount_paid was provided
    if amount_paid is not None:
        result_pay = await db.execute(
            select(RegistrationPayment).where(RegistrationPayment.player_id == player_id)
        )
        existing_payment = result_pay.scalar_one_or_none()
        if existing_payment:
            existing_payment.amount_paid = amount_paid
        else:
            db.add(RegistrationPayment(player_id=player_id, amount_paid=amount_paid))

    # Log update
    log = AdminLog(
        action_type="UPDATE",
        description=(
            f"Updated player ID {player_id} | "
            + ", ".join(changes)
        )
    )

    db.add(log)

    await db.commit()
    await db.refresh(player)

    # Reload with stats
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.stats), selectinload(Player.payment))
        .where(Player.id == player.id)
    )

    return result.scalar_one()


async def delete_player(
    db: AsyncSession,
    player_id: int
) -> bool:
    """
    Delete a player.

    Prevent deletion if player has existing match records.
    """

    player = await get_player(db, player_id)

    if not player:
        return False

    # Log deletion
    log = AdminLog(
        action_type="DELETE",
        description=(
            f"Deleted player: {player.full_name} "
            f"(Tag: {player.tekken_name})"
        )
    )

    db.add(log)

    try:
        await db.delete(player)
        await db.commit()

    except IntegrityError:

        await db.rollback()

        raise ValueError(
            f"Cannot delete '{player.tekken_name}' — "
            f"they have existing match records. "
            f"Remove their matches first or keep them "
            f"in the system."
        )

    return True