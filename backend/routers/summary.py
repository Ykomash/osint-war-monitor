"""AI Summary endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Summary
from services.ai_summary import generate_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("")
async def get_latest_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Summary).order_by(Summary.generated_at.desc()).limit(1)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        return {"content": None, "generated_at": None}
    return {
        "id": summary.id,
        "content": summary.content,
        "generated_at": summary.generated_at.isoformat() + "Z",
        "period_hours": summary.period_hours,
    }


@router.post("/generate")
async def trigger_summary():
    try:
        content = await generate_summary()
        return {"status": "ok", "content": content}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Summary generation error: {error_msg}")
        return {"error": error_msg or "Failed to generate summary. Check OpenAI API key and account credits."}
