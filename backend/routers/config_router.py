"""Config endpoints for admin settings."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigUpdate(BaseModel):
    key: str
    value: str  # JSON-encoded


@router.get("")
async def list_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Config))
    items = result.scalars().all()
    return {c.key: json.loads(c.value) for c in items}


@router.get("/{key}")
async def get_config(key: str, db: AsyncSession = Depends(get_db)):
    config = await db.get(Config, key)
    if not config:
        return {"key": key, "value": None}
    return {"key": key, "value": json.loads(config.value)}


@router.put("")
async def set_config(body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    config = await db.get(Config, body.key)
    if config:
        config.value = body.value
    else:
        config = Config(key=body.key, value=body.value)
        db.add(config)
    await db.commit()
    return {"ok": True}
