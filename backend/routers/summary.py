"""AI Summary endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Summary
from services.ai_summary import generate_summary

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
    content = await generate_summary()
    if content is None:
        return {"error": "Failed to generate summary. Check OpenAI API key."}
    return {"status": "ok", "content": content}
