"""X (Twitter) monitor using twscrape."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from config import DATA_DIR
from database import async_session
from models import Config, XAccount, XPost
from services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_ACCOUNTS_DB = str(DATA_DIR / "twscrape_accounts.db")
_api = None  # twscrape API singleton


def _load_keywords_sync(keywords_json: str) -> list[str]:
    try:
        return json.loads(keywords_json) if keywords_json else []
    except Exception:
        return []


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text or not keywords:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


async def _get_api():
    """Lazy-init twscrape API. Returns None if twscrape not installed or no creds."""
    global _api
    if _api is not None:
        return _api
    try:
        from twscrape import API  # type: ignore
        _api = API(_ACCOUNTS_DB)
        return _api
    except ImportError:
        logger.error("twscrape not installed — run: pip install twscrape")
        return None
    except Exception as e:
        logger.error(f"Failed to init twscrape API: {e}")
        return None


async def _get_scraper_creds() -> dict | None:
    """Load the scraper account credentials from Config DB."""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Config).where(Config.key == "x_scraper_account")
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            creds = json.loads(row.value)
            if all(k in creds for k in ("username", "password", "email", "email_password")):
                return creds
    except Exception as e:
        logger.error(f"Failed to load X scraper creds: {e}")
    return None


async def _get_keywords() -> list[str]:
    try:
        async with async_session() as db:
            result = await db.execute(select(Config).where(Config.key == "keywords"))
            row = result.scalar_one_or_none()
            return json.loads(row.value) if row else []
    except Exception:
        return []


async def ensure_scraper_logged_in(api) -> bool:
    """Add/refresh the scraper account credentials and log in."""
    creds = await _get_scraper_creds()
    if not creds:
        logger.warning("No X scraper account configured. Go to Admin → X Scraper Account.")
        return False
    try:
        await api.pool.add_account(
            creds["username"],
            creds["password"],
            creds["email"],
            creds["email_password"],
        )
        await api.pool.login_all()
        logger.info(f"X scraper account '{creds['username']}' ready")
        return True
    except Exception as e:
        logger.error(f"X scraper login failed: {e}")
        return False


async def fetch_posts_for_account(api, account: XAccount, keywords: list[str]) -> int:
    """Fetch latest tweets for one account and save new ones. Returns count saved."""
    try:
        # Resolve user_id if we don't have it yet
        if not account.x_user_id:
            user = await api.user_by_login(account.username)
            if not user:
                logger.warning(f"Could not resolve X user: @{account.username}")
                return 0
            async with async_session() as db:
                row = await db.get(XAccount, account.id)
                if row:
                    row.x_user_id = str(user.id)
                    if not row.display_name:
                        row.display_name = user.displayname or account.username
                    await db.commit()
            account.x_user_id = str(user.id)

        # Get existing tweet IDs
        async with async_session() as db:
            result = await db.execute(
                select(XPost.tweet_id).where(XPost.account_id == account.id)
            )
            existing_ids = {row[0] for row in result.all()}

        saved = 0
        new_posts = []

        async for tweet in api.user_tweets(int(account.x_user_id), limit=40):
            tid = str(tweet.id)
            if tid in existing_ids:
                continue

            text = tweet.rawContent or ""
            matched = _find_keywords(text, keywords)

            # Collect media URLs (photos/videos)
            media_urls = []
            if tweet.media:
                if hasattr(tweet.media, "photos") and tweet.media.photos:
                    media_urls += [p.url for p in tweet.media.photos if p.url]
                if hasattr(tweet.media, "videos") and tweet.media.videos:
                    for v in tweet.media.videos:
                        variants = getattr(v, "variants", [])
                        if variants:
                            best = max(variants, key=lambda x: getattr(x, "bitrate", 0) or 0)
                            if getattr(best, "url", None):
                                media_urls.append(best.url)

            ts = tweet.date
            if ts and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)

            new_posts.append(XPost(
                account_id=account.id,
                tweet_id=tid,
                text=text,
                timestamp=ts or datetime.utcnow(),
                has_media=bool(media_urls),
                media_urls=json.dumps(media_urls),
                like_count=getattr(tweet, "likeCount", 0) or 0,
                retweet_count=getattr(tweet, "retweetCount", 0) or 0,
                reply_count=getattr(tweet, "replyCount", 0) or 0,
                tweet_url=getattr(tweet, "url", "") or f"https://x.com/i/web/status/{tid}",
                is_flagged=len(matched) > 0,
                matched_keywords=json.dumps(matched, ensure_ascii=False),
            ))

        if new_posts:
            async with async_session() as db:
                db.add_all(new_posts)
                await db.commit()
            saved = len(new_posts)
            await ws_manager.broadcast("new_x_post", {"count": saved, "account": account.username})
            logger.info(f"Saved {saved} new tweets from @{account.username}")

        return saved

    except Exception as e:
        logger.error(f"Error fetching tweets for @{account.username}: {e}")
        return 0


async def run_x_monitor():
    """Main loop: poll all active X accounts every 15 minutes."""
    await asyncio.sleep(30)  # Let other services start first

    api = await _get_api()
    if not api:
        logger.warning("twscrape unavailable — X monitor disabled")
        return

    logged_in = await ensure_scraper_logged_in(api)
    if not logged_in:
        # Retry every 5 minutes until creds are configured
        while True:
            await asyncio.sleep(300)
            logged_in = await ensure_scraper_logged_in(api)
            if logged_in:
                break

    logger.info("X monitor started")

    while True:
        try:
            keywords = await _get_keywords()

            async with async_session() as db:
                result = await db.execute(
                    select(XAccount).where(XAccount.is_active.is_(True))
                )
                accounts = result.scalars().all()

            if not accounts:
                logger.debug("No X accounts configured, sleeping...")
            else:
                for account in accounts:
                    await fetch_posts_for_account(api, account, keywords)
                    await asyncio.sleep(3)  # small delay between accounts

        except Exception as e:
            logger.error(f"X monitor loop error: {e}", exc_info=True)

        await asyncio.sleep(900)  # poll every 15 minutes
