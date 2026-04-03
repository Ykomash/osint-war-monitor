"""News article endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import NewsArticle

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def list_news(
    limit: int = Query(50, le=200),
    offset: int = 0,
    source: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc())
    if source:
        stmt = stmt.where(NewsArticle.source == source)
    if category:
        stmt = stmt.where(NewsArticle.category == category)
    if date_from:
        stmt = stmt.where(NewsArticle.published_at >= datetime.fromisoformat(date_from))
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    articles = result.scalars().all()
    return [
        {
            "id": a.id,
            "source": a.source,
            "title": a.title,
            "url": a.url,
            "description": a.description,
            "published_at": (a.published_at.isoformat() + "Z") if a.published_at else None,
            "category": a.category,
            "image_url": a.image_url,
        }
        for a in articles
    ]
