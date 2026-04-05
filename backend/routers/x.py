"""X (Twitter) endpoints."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config, XAccount, XPost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/x", tags=["x"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class XAccountCreate(BaseModel):
    username: str
    display_name: Optional[str] = ""


class ScraperCredentials(BaseModel):
    username: str
    password: str
    email: str
    email_password: str


# ── Accounts CRUD ────────────────────────────────────────────────────────────

@router.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(XAccount).order_by(XAccount.added_at.desc()))
    accounts = result.scalars().all()
    return [
        {
            "id": a.id,
            "username": a.username,
            "display_name": a.display_name,
            "x_user_id": a.x_user_id,
            "is_active": a.is_active,
            "added_at": a.added_at.isoformat(),
        }
        for a in accounts
    ]


@router.post("/accounts")
async def add_account(body: XAccountCreate, db: AsyncSession = Depends(get_db)):
    username = body.username.lstrip("@").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    existing = await db.execute(select(XAccount).where(XAccount.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"@{username} is already being monitored")

    account = XAccount(
        username=username,
        display_name=body.display_name or f"@{username}",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return {"id": account.id, "username": account.username, "display_name": account.display_name}


@router.patch("/accounts/{account_id}")
async def toggle_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(XAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.is_active = not account.is_active
    await db.commit()
    return {"is_active": account.is_active}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(XAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    await db.commit()
    return {"ok": True}


# ── Scraper credentials ───────────────────────────────────────────────────────

@router.post("/scraper-account")
async def set_scraper_account(body: ScraperCredentials, db: AsyncSession = Depends(get_db)):
    """Save the Twitter account used for scraping."""
    creds = {
        "username": body.username,
        "password": body.password,
        "email": body.email,
        "email_password": body.email_password,
    }
    existing = await db.execute(select(Config).where(Config.key == "x_scraper_account"))
    row = existing.scalar_one_or_none()
    if row:
        row.value = json.dumps(creds)
    else:
        db.add(Config(key="x_scraper_account", value=json.dumps(creds)))
    await db.commit()

    # Re-login with new creds
    try:
        from services.x_monitor import _get_api, ensure_scraper_logged_in
        api = await _get_api()
        if api:
            await ensure_scraper_logged_in(api)
    except Exception as e:
        logger.warning(f"Scraper re-login after save: {e}")

    return {"ok": True}


@router.get("/scraper-account")
async def get_scraper_account(db: AsyncSession = Depends(get_db)):
    """Return scraper account username (no password)."""
    result = await db.execute(select(Config).where(Config.key == "x_scraper_account"))
    row = result.scalar_one_or_none()
    if not row:
        return {"configured": False}
    creds = json.loads(row.value)
    return {"configured": True, "username": creds.get("username", "")}


# ── Posts ─────────────────────────────────────────────────────────────────────

@router.get("/posts")
async def get_posts(
    account_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    has_media: Optional[bool] = None,
    flagged_only: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import and_

    filters = []
    if account_id:
        filters.append(XPost.account_id == account_id)
    if has_media is not None:
        filters.append(XPost.has_media.is_(has_media))
    if flagged_only:
        filters.append(XPost.is_flagged.is_(True))

    query = (
        select(XPost, XAccount.username, XAccount.display_name)
        .join(XAccount, XPost.account_id == XAccount.id)
        .where(and_(*filters) if filters else True)
        .order_by(desc(XPost.timestamp))
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    posts = []
    for post, username, display_name in rows:
        text = post.text or ""
        if search and search.lower() not in text.lower():
            continue
        posts.append({
            "id": post.id,
            "account_id": post.account_id,
            "username": username,
            "display_name": display_name,
            "tweet_id": post.tweet_id,
            "text": text,
            "timestamp": post.timestamp.isoformat(),
            "has_media": post.has_media,
            "media_urls": json.loads(post.media_urls or "[]"),
            "like_count": post.like_count,
            "retweet_count": post.retweet_count,
            "reply_count": post.reply_count,
            "tweet_url": post.tweet_url,
            "is_flagged": post.is_flagged,
            "matched_keywords": json.loads(post.matched_keywords or "[]"),
        })

    return posts
