"""Telegram channel monitor using Telethon."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select

from config import MEDIA_DIR, TELEGRAM_API_HASH, TELEGRAM_API_ID, TELEGRAM_SESSION_PATH
from database import async_session
from models import TelegramChannel, TelegramMessage
from services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_client = None
_monitored_channels: Dict[int, int] = {}  # telethon entity id -> db channel id

# Keywords loaded from config
_keywords: list[str] = []


def _find_matching_keywords(text: str) -> list[str]:
    """Simple keyword matching against configured keywords."""
    if not text or not _keywords:
        return []
    text_lower = text.lower()
    return [kw for kw in _keywords if kw.lower() in text_lower]


async def _load_keywords():
    """Load keywords from config DB."""
    global _keywords
    try:
        from models import Config
        async with async_session() as db:
            result = await db.execute(select(Config).where(Config.key == "keywords"))
            config = result.scalar_one_or_none()
            if config:
                _keywords = json.loads(config.value)
    except Exception as e:
        logger.error(f"Failed to load keywords: {e}")


async def _get_client():
    """Lazy-init Telethon client."""
    global _client
    if _client is not None:
        return _client

    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.warning("Telegram API credentials not set, skipping Telegram monitor")
        return None

    try:
        from telethon import TelegramClient
        _client = TelegramClient(
            TELEGRAM_SESSION_PATH,
            int(TELEGRAM_API_ID),
            TELEGRAM_API_HASH,
        )
        await _client.start()
        logger.info("Telegram client connected")
        return _client
    except Exception as e:
        logger.error(f"Failed to start Telegram client: {e}")
        return None


async def _handle_message(event):
    """Process incoming Telegram message."""
    try:
        chat_id = event.chat_id
        if chat_id not in _monitored_channels:
            return

        db_channel_id = _monitored_channels[chat_id]
        text = event.message.text or ""
        has_media = event.message.media is not None

        # Keyword matching
        matched = _find_matching_keywords(text)
        is_flagged = len(matched) > 0

        # Determine media type and download
        media_type = None
        media_file = None

        if has_media:
            os.makedirs(MEDIA_DIR, exist_ok=True)
            msg_id = event.message.id

            if event.message.photo:
                media_type = "photo"
                media_file = f"tg_{db_channel_id}_{msg_id}.jpg"
                filepath = MEDIA_DIR / media_file
                try:
                    await event.message.download_media(file=str(filepath))
                except Exception as e:
                    logger.error(f"Failed to download photo: {e}")
                    media_file = None

            elif event.message.video or event.message.video_note:
                media_type = "video"
                media_file = f"tg_{db_channel_id}_{msg_id}.mp4"
                filepath = MEDIA_DIR / media_file
                try:
                    await event.message.download_media(file=str(filepath))
                except Exception as e:
                    logger.error(f"Failed to download video: {e}")
                    media_file = None

            elif event.message.document:
                mime = getattr(event.message.document, 'mime_type', '') or ''
                if mime.startswith('image/'):
                    media_type = "photo"
                    ext = mime.split('/')[-1].replace('jpeg', 'jpg')
                    media_file = f"tg_{db_channel_id}_{msg_id}.{ext}"
                elif mime.startswith('video/'):
                    media_type = "video"
                    ext = mime.split('/')[-1]
                    media_file = f"tg_{db_channel_id}_{msg_id}.{ext}"

                if media_file:
                    filepath = MEDIA_DIR / media_file
                    try:
                        await event.message.download_media(file=str(filepath))
                    except Exception as e:
                        logger.error(f"Failed to download document: {e}")
                        media_file = None

        async with async_session() as db:
            msg = TelegramMessage(
                channel_id=db_channel_id,
                message_id=event.message.id,
                text=text,
                timestamp=event.message.date or datetime.utcnow(),
                has_media=has_media,
                media_type=media_type,
                media_file=media_file,
                is_flagged=is_flagged,
                matched_keywords=json.dumps(matched, ensure_ascii=False),
            )
            db.add(msg)
            await db.commit()

            # Broadcast message
            await ws_manager.broadcast("new_telegram_message", {
                "id": msg.id,
                "channel_id": db_channel_id,
                "text": text[:500],
                "is_flagged": is_flagged,
                "has_media": has_media,
                "media_type": media_type,
                "media_file": media_file,
                "timestamp": msg.timestamp.isoformat(),
            })

    except Exception as e:
        logger.error(f"Error handling Telegram message: {e}")


async def add_channel(channel_identifier: str) -> Optional[dict]:
    """Add a channel to monitoring. Returns channel info or raises on failure."""
    client = await _get_client()
    if not client:
        return None
    try:
        entity = await client.get_entity(channel_identifier)
        _monitored_channels[entity.id] = -1  # placeholder until DB record created
        return {
            "entity_id": entity.id,
            "title": getattr(entity, "title", channel_identifier),
        }
    except Exception as e:
        logger.error(f"Failed to resolve channel {channel_identifier}: {type(e).__name__}: {e}")
        # Re-raise so the router can return the real error to the frontend
        raise


async def _backfill_channel(client, entity, db_channel_id: int, limit: int = 500):
    """Fetch recent historical messages for a channel and save any not already in DB.
    Media is NOT downloaded during backfill — only noted as pending — to keep it fast.
    """
    try:
        # Get message IDs already in DB for this channel
        async with async_session() as db:
            result = await db.execute(
                select(TelegramMessage.message_id)
                .where(TelegramMessage.channel_id == db_channel_id)
            )
            existing_ids = {row[0] for row in result.all()}

        saved = 0
        batch = []
        async for message in client.iter_messages(entity, limit=limit):
            if not message or message.id in existing_ids:
                continue

            text = message.text or ""
            has_media = message.media is not None
            matched = _find_matching_keywords(text)
            is_flagged = len(matched) > 0

            # Detect media type but do NOT download during backfill (too slow)
            media_type = None
            if has_media:
                if message.photo:
                    media_type = "photo"
                elif message.video or message.video_note:
                    media_type = "video"
                elif message.document:
                    mime = getattr(message.document, 'mime_type', '') or ''
                    if mime.startswith('image/'):
                        media_type = "photo"
                    elif mime.startswith('video/'):
                        media_type = "video"

            batch.append(TelegramMessage(
                channel_id=db_channel_id,
                message_id=message.id,
                text=text,
                timestamp=message.date or datetime.utcnow(),
                has_media=has_media,
                media_type=media_type,
                media_file=None,  # not downloaded yet
                is_flagged=is_flagged,
                matched_keywords=json.dumps(matched, ensure_ascii=False),
            ))

            # Commit in batches of 50 so messages appear progressively
            if len(batch) >= 50:
                async with async_session() as db:
                    db.add_all(batch)
                    await db.commit()
                saved += len(batch)
                batch = []
                await ws_manager.broadcast("new_telegram_message", {"backfill": True})

        # Commit remaining
        if batch:
            async with async_session() as db:
                db.add_all(batch)
                await db.commit()
            saved += len(batch)
            await ws_manager.broadcast("new_telegram_message", {"backfill": True})

        logger.info(f"Backfilled {saved} messages for channel_id={db_channel_id}")
    except Exception as e:
        logger.error(f"Failed to backfill channel {db_channel_id}: {e}")


async def _download_pending_media(client, db_channel_id: int):
    """Download media for backfilled messages that have has_media=True but no file yet."""
    try:
        from sqlalchemy import and_
        async with async_session() as db:
            result = await db.execute(
                select(TelegramMessage)
                .where(and_(
                    TelegramMessage.channel_id == db_channel_id,
                    TelegramMessage.has_media.is_(True),
                    TelegramMessage.media_file.is_(None),
                ))
                .order_by(TelegramMessage.timestamp.desc())
                .limit(60)
            )
            pending = result.scalars().all()

        if not pending:
            return

        logger.info(f"Downloading media for {len(pending)} backfilled msgs in channel {db_channel_id}")
        os.makedirs(MEDIA_DIR, exist_ok=True)

        entity_id = next((eid for eid, cid in _monitored_channels.items() if cid == db_channel_id), None)
        if not entity_id:
            return
        entity = await client.get_entity(entity_id)

        for msg_record in pending:
            try:
                tg_msg = await client.get_messages(entity, ids=msg_record.message_id)
                if not tg_msg or not tg_msg.media:
                    continue

                media_file = None
                if tg_msg.photo:
                    media_file = f"tg_{db_channel_id}_{tg_msg.id}.jpg"
                elif tg_msg.video or tg_msg.video_note:
                    media_file = f"tg_{db_channel_id}_{tg_msg.id}.mp4"
                elif tg_msg.document:
                    mime = getattr(tg_msg.document, 'mime_type', '') or ''
                    if mime.startswith('image/'):
                        ext = mime.split('/')[-1].replace('jpeg', 'jpg')
                        media_file = f"tg_{db_channel_id}_{tg_msg.id}.{ext}"
                    elif mime.startswith('video/'):
                        ext = mime.split('/')[-1]
                        media_file = f"tg_{db_channel_id}_{tg_msg.id}.{ext}"

                if media_file:
                    filepath = MEDIA_DIR / media_file
                    if not filepath.exists():
                        await tg_msg.download_media(file=str(filepath))
                    async with async_session() as db:
                        row = await db.get(TelegramMessage, msg_record.id)
                        if row:
                            row.media_file = media_file
                            await db.commit()

            except Exception as e:
                logger.debug(f"Media download failed for msg {msg_record.message_id}: {e}")

        logger.info(f"Media download done for channel {db_channel_id}")
        await ws_manager.broadcast("new_telegram_message", {"media_updated": True})

    except Exception as e:
        logger.error(f"Media download worker error for channel {db_channel_id}: {e}")


async def poll_new_messages():
    """Poll each channel every 60s for messages newer than the last saved one."""
    await asyncio.sleep(15)  # Let backfill run first
    while True:
        try:
            client = await _get_client()
            if client and _monitored_channels:
                async with async_session() as db:
                    result = await db.execute(
                        select(TelegramChannel).where(TelegramChannel.is_active.is_(True))
                    )
                    active_channels = {ch.id: ch for ch in result.scalars().all()}

                for entity_id, db_channel_id in list(_monitored_channels.items()):
                    if db_channel_id not in active_channels:
                        continue
                    try:
                        # Get the max message_id we already have
                        async with async_session() as db:
                            from sqlalchemy import func
                            row = await db.execute(
                                select(func.max(TelegramMessage.message_id))
                                .where(TelegramMessage.channel_id == db_channel_id)
                            )
                            max_id = row.scalar() or 0

                        entity = await client.get_entity(entity_id)
                        new_msgs = []
                        async for message in client.iter_messages(entity, min_id=max_id, limit=50):
                            if not message or not message.id:
                                continue
                            text = message.text or ""
                            has_media = message.media is not None
                            media_type = None
                            if has_media:
                                if message.photo:
                                    media_type = "photo"
                                elif message.video or message.video_note:
                                    media_type = "video"
                                elif message.document:
                                    mime = getattr(message.document, 'mime_type', '') or ''
                                    if mime.startswith('image/'):
                                        media_type = "photo"
                                    elif mime.startswith('video/'):
                                        media_type = "video"
                            matched = _find_matching_keywords(text)
                            new_msgs.append(TelegramMessage(
                                channel_id=db_channel_id,
                                message_id=message.id,
                                text=text,
                                timestamp=message.date or datetime.utcnow(),
                                has_media=has_media,
                                media_type=media_type,
                                media_file=None,
                                is_flagged=len(matched) > 0,
                                matched_keywords=json.dumps(matched, ensure_ascii=False),
                            ))

                        if new_msgs:
                            async with async_session() as db:
                                db.add_all(new_msgs)
                                await db.commit()
                            logger.info(f"Polled {len(new_msgs)} new msgs for channel {db_channel_id}")
                            await ws_manager.broadcast("new_telegram_message", {"count": len(new_msgs)})

                    except Exception as e:
                        logger.error(f"Poll error for channel {db_channel_id}: {e}")

        except Exception as e:
            logger.error(f"Telegram poll loop error: {e}")

        await asyncio.sleep(60)


async def get_monitor_status() -> dict:
    """Return current monitor status for diagnostics."""
    import os as _os
    session_file = TELEGRAM_SESSION_PATH + ".session"
    session_exists = _os.path.exists(session_file)
    session_size = _os.path.getsize(session_file) if session_exists else 0
    try:
        connected = _client is not None and _client.is_connected()
    except Exception:
        connected = False
    return {
        "client_initialized": _client is not None,
        "connected": connected,
        "session_file_exists": session_exists,
        "session_file_bytes": session_size,
        "monitored_channels_count": len(_monitored_channels),
        "monitored_db_channel_ids": list(_monitored_channels.values()),
        "api_id_set": bool(TELEGRAM_API_ID),
        "api_hash_set": bool(TELEGRAM_API_HASH),
    }


async def run_telegram_monitor():
    """Main loop: connect to Telegram, with auto-reconnect on failure."""
    import asyncio as _asyncio
    await _load_keywords()

    while True:
        try:
            global _client
            _client = None  # reset so _get_client() tries a fresh connect

            client = await _get_client()
            if not client:
                logger.warning("Telegram client unavailable (missing credentials or session). Retrying in 5 min...")
                await asyncio.sleep(300)
                continue

            # Load configured channels from DB
            async with async_session() as db:
                result = await db.execute(
                    select(TelegramChannel).where(TelegramChannel.is_active.is_(True))
                )
                channels = result.scalars().all()

            _monitored_channels.clear()
            for ch in channels:
                try:
                    entity = await client.get_entity(ch.channel_identifier)
                    _monitored_channels[entity.id] = ch.id
                    logger.info(f"Monitoring channel: {ch.display_name} ({ch.channel_identifier})")
                except Exception as e:
                    logger.error(f"Failed to resolve channel {ch.channel_identifier}: {e}")

            logger.info(f"Resolved {len(_monitored_channels)} channels to monitor")

            # Backfill historical messages then download their media
            for entity_id, db_channel_id in list(_monitored_channels.items()):
                try:
                    entity = await client.get_entity(entity_id)
                    await _backfill_channel(client, entity, db_channel_id, limit=500)
                    _asyncio.create_task(
                        _download_pending_media(client, db_channel_id),
                        name=f"media_dl_{db_channel_id}"
                    )
                except Exception as e:
                    logger.error(f"Backfill error for entity {entity_id}: {e}")

            # Register real-time message handler
            from telethon import events
            client.add_event_handler(_handle_message, events.NewMessage())

            # Start the 60-second poll loop as a concurrent task
            _asyncio.create_task(poll_new_messages(), name="telegram_poll")

            logger.info(f"Telegram monitor running, watching {len(_monitored_channels)} channels")
            await client.run_until_disconnected()
            logger.warning("Telegram client disconnected — will reconnect in 30s...")

        except Exception as e:
            logger.error(f"Telegram monitor crashed: {e}", exc_info=True)

        await asyncio.sleep(30)
