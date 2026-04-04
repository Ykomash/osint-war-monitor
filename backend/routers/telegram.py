"""Telegram endpoints: messages, channel management, media serving."""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from config import MEDIA_DIR
from database import get_db
from models import TelegramChannel, TelegramMessage

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class ChannelCreate(BaseModel):
    channel_identifier: str  # e.g. "@redalertisrael" or invite link
    display_name: str = ""


@router.get("/status")
async def telegram_status():
    """Diagnostic: Telegram monitor connection state."""
    from services.telegram_monitor import get_monitor_status
    return await get_monitor_status()


@router.get("/messages")
async def list_messages(
    limit: int = Query(50, le=200),
    offset: int = 0,
    channel_id: Optional[int] = None,
    flagged_only: bool = False,
    search: Optional[str] = None,
    has_media: Optional[bool] = None,
    hour_from: Optional[int] = Query(None, ge=0, le=23),
    hour_to: Optional[int] = Query(None, ge=0, le=23),
    minute_from: Optional[int] = Query(None, ge=0, le=59),
    minute_to: Optional[int] = Query(None, ge=0, le=59),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TelegramMessage).order_by(TelegramMessage.timestamp.desc())
    if channel_id:
        stmt = stmt.where(TelegramMessage.channel_id == channel_id)
    if flagged_only:
        stmt = stmt.where(TelegramMessage.is_flagged.is_(True))
    if search:
        stmt = stmt.where(TelegramMessage.text.ilike(f"%{search}%"))
    if has_media is True:
        stmt = stmt.where(TelegramMessage.has_media.is_(True))
    elif has_media is False:
        stmt = stmt.where(TelegramMessage.has_media.is_(False))
    if hour_from is not None:
        stmt = stmt.where(func.strftime("%H", TelegramMessage.timestamp).cast(Integer) >= hour_from)
    if hour_to is not None:
        stmt = stmt.where(func.strftime("%H", TelegramMessage.timestamp).cast(Integer) <= hour_to)
    if minute_from is not None:
        stmt = stmt.where(func.strftime("%M", TelegramMessage.timestamp).cast(Integer) >= minute_from)
    if minute_to is not None:
        stmt = stmt.where(func.strftime("%M", TelegramMessage.timestamp).cast(Integer) <= minute_to)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Get channel names for display
    channel_ids = {m.channel_id for m in messages}
    channels_map = {}
    if channel_ids:
        ch_result = await db.execute(
            select(TelegramChannel).where(TelegramChannel.id.in_(channel_ids))
        )
        for ch in ch_result.scalars().all():
            channels_map[ch.id] = ch.display_name or ch.channel_identifier

    return [
        {
            "id": m.id,
            "channel_id": m.channel_id,
            "channel_name": channels_map.get(m.channel_id, "Unknown"),
            "message_id": m.message_id,
            "text": m.text,
            "timestamp": (m.timestamp.isoformat() + "Z") if m.timestamp else None,
            "has_media": m.has_media,
            "media_type": m.media_type,
            "media_file": m.media_file,
            "is_flagged": m.is_flagged,
            "matched_keywords": json.loads(m.matched_keywords),
        }
        for m in messages
    ]


@router.get("/media/{filename}")
async def get_media(filename: str):
    """Serve a media file (image or video) from the media directory."""
    filepath = MEDIA_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Media file not found")
    # Security: ensure the resolved path is within MEDIA_DIR
    if not filepath.resolve().is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(403, "Access denied")
    return FileResponse(str(filepath))


@router.get("/channels")
async def list_channels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TelegramChannel))
    channels = result.scalars().all()
    return [
        {
            "id": c.id,
            "channel_identifier": c.channel_identifier,
            "display_name": c.display_name,
            "is_active": c.is_active,
            "added_at": c.added_at.isoformat() if c.added_at else None,
        }
        for c in channels
    ]


@router.post("/channels")
async def create_channel(body: ChannelCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    existing = await db.execute(
        select(TelegramChannel).where(
            TelegramChannel.channel_identifier == body.channel_identifier
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Channel already exists")

    # Fail fast if Telegram client isn't up
    from services.telegram_monitor import add_channel, _client
    if _client is None:
        raise HTTPException(503, "Telegram client not connected. Check TELEGRAM_API_ID / TELEGRAM_API_HASH / session.")

    # Try to resolve via Telethon — return the real error if it fails
    try:
        info = await add_channel(body.channel_identifier)
    except Exception as e:
        raise HTTPException(400, f"Telegram error for '{body.channel_identifier}': {type(e).__name__}: {e}")
    if not info:
        raise HTTPException(400, f"Could not resolve '{body.channel_identifier}'.")

    channel = TelegramChannel(
        channel_identifier=body.channel_identifier,
        display_name=body.display_name or info["title"],
        is_active=True,
    )
    db.add(channel)
    await db.commit()

    # Update the monitor's channel mapping and trigger backfill
    import asyncio
    from services.telegram_monitor import _monitored_channels, _get_client, _backfill_channel, _download_pending_media
    _monitored_channels[info["entity_id"]] = channel.id

    async def _do_backfill():
        try:
            client = await _get_client()
            if client:
                entity = await client.get_entity(info["entity_id"])
                await _backfill_channel(client, entity, channel.id, limit=500)
                # Download media for backfilled messages (runs after backfill completes)
                await _download_pending_media(client, channel.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Backfill error for new channel: {e}")

    asyncio.create_task(_do_backfill())

    return {"id": channel.id, "display_name": channel.display_name}


@router.patch("/channels/{channel_id}")
async def toggle_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    channel = await db.get(TelegramChannel, channel_id)
    if not channel:
        raise HTTPException(404, "Channel not found")
    channel.is_active = not channel.is_active
    await db.commit()
    return {"id": channel.id, "is_active": channel.is_active}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    channel = await db.get(TelegramChannel, channel_id)
    if not channel:
        raise HTTPException(404, "Channel not found")
    await db.delete(channel)
    await db.commit()
    return {"ok": True}
