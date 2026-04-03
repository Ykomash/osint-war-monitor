"""News aggregator: polls RSS feeds, NYT API, and Ynet flash news. Only war-related articles."""

import asyncio
import logging
import re
import json as _json
from datetime import datetime
from typing import List

import feedparser
import httpx
from sqlalchemy import select

from config import NYT_API_KEY, NYT_POLL_INTERVAL, RSS_FEEDS, RSS_POLL_INTERVAL
from database import async_session
from models import NewsArticle
from services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

# Keywords to filter war-related articles (must match at least one)
WAR_KEYWORDS_EN = [
    # Organisations / actors / key figures
    "idf", "hamas", "hezbollah", "houthi", "houthis", "irgc",
    "netanyahu", "sinwar", "nasrallah", "khamenei",
    # Countries — almost always conflict context in this dashboard
    "iran", "yemen",
    # Locations tied to conflict
    "gaza", "rafah", "jenin", "west bank",
    "beirut", "southern lebanon",
    "iran nuclear", "iranian",
    "red sea", "bab al-mandeb",
    # Military actions
    "airstrike", "air strike", "missile strike", "rocket fire",
    "drone attack", "drone strike", "ballistic missile",
    "ground operation", "military operation",
    "ceasefire", "hostage", "warplane",
    "iron dome", "david's sling", "arrow missile",
    "casualties", "killed in attack", "killed in strike",
    "troops withdraw", "forces advance",
    # Broader war context — only as part of phrase
    "israel-hamas", "israel-hezbollah", "israel war",
    "war in gaza", "war in lebanon", "conflict in",
    "israeli forces", "israeli military", "israeli army",
    "israeli airstrike", "israeli strike",
    "idf forces", "idf troops", "idf operation",
]
WAR_KEYWORDS_HE = [
    "מלחמה", "צהל", "עזה", "חמאס", "חיזבאללה", "איראן", "טיל", "רקטה",
    "הפסקת אש", "תקיפה", "חייל", "לחימה", "התקפה", "פיגוע", "טרור",
    "חטוף", "שבוי", "כיפת ברזל", "לבנון", "ביירות", "צבא", "נתניהו",
    "ביטחון", "יירוט", "צבע אדום", "פיקוד העורף", "חיל האוויר",
    "מנהרה", "גבול", "עוטף", "פלסטין", "הרוג", "פצוע", "מרגמה",
    "כטבם", "כטמב", "חיזבאללה", "פיקוד", "חזית", "מבצע", "כוחות",
]


def _is_war_related(title: str, description: str) -> bool:
    """Check if article is war/security related."""
    text = (title + " " + description).lower()
    for kw in WAR_KEYWORDS_EN:
        if kw in text:
            return True
    for kw in WAR_KEYWORDS_HE:
        if kw in text:
            return True
    return False


async def _fetch_rss(client: httpx.AsyncClient, source: str, url: str) -> List[dict]:
    """Fetch and parse an RSS feed, filtering for war-related articles only."""
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries:
            title = entry.get("title", "")
            description = entry.get("summary", "")

            # Skip non-war articles
            if not _is_war_related(title, description):
                continue

            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])

            image_url = None
            if hasattr(entry, "media_content") and entry.media_content:
                image_url = entry.media_content[0].get("url")
            elif hasattr(entry, "enclosures") and entry.enclosures:
                image_url = entry.enclosures[0].get("href")

            articles.append({
                "source": source,
                "title": title,
                "url": entry.get("link", ""),
                "description": description,
                "published_at": pub_date,
                "image_url": image_url,
            })
        logger.info(f"RSS {source}: {len(articles)} war-related out of {len(feed.entries)} total")
        return articles
    except Exception as e:
        logger.error(f"Error fetching RSS {source}: {e}")
        return []


async def _fetch_nyt(client: httpx.AsyncClient) -> List[dict]:
    """Fetch articles from NYT Article Search API (already filtered by geo)."""
    if not NYT_API_KEY:
        return []
    try:
        resp = await client.get(
            "https://api.nytimes.com/svc/search/v2/articlesearch.json",
            params={
                "api-key": NYT_API_KEY,
                "fq": 'glocations:("Israel") OR glocations:("Gaza") OR glocations:("Iran") OR glocations:("Lebanon")',
                "sort": "newest",
            },
            timeout=15.0,
        )
        if resp.status_code != 200:
            logger.warning(f"NYT API returned {resp.status_code}")
            return []
        data = resp.json()
        articles = []
        for doc in data.get("response", {}).get("docs", []):
            pub_date = None
            if doc.get("pub_date"):
                try:
                    pub_date = datetime.fromisoformat(doc["pub_date"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            image_url = None
            for media in doc.get("multimedia", []):
                if media.get("subtype") == "xlarge":
                    image_url = f"https://www.nytimes.com/{media['url']}"
                    break
            articles.append({
                "source": "nyt",
                "title": doc.get("headline", {}).get("main", ""),
                "url": doc.get("web_url", ""),
                "description": doc.get("abstract", ""),
                "published_at": pub_date,
                "image_url": image_url,
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching NYT: {e}")
        return []


async def _store_articles(articles: List[dict]):
    """Store new articles in DB and broadcast."""
    if not articles:
        return
    async with async_session() as db:
        stored = 0
        for art in articles:
            if not art.get("url"):
                continue
            # Check duplicate
            existing = await db.execute(
                select(NewsArticle).where(NewsArticle.url == art["url"])
            )
            if existing.scalar_one_or_none():
                continue

            article = NewsArticle(
                source=art["source"],
                title=art["title"],
                url=art["url"],
                description=art["description"],
                published_at=art.get("published_at"),
                category="war",  # all articles are war-related now
                image_url=art.get("image_url"),
            )
            db.add(article)
            stored += 1

        await db.commit()
        if stored:
            logger.info(f"Stored {stored} new war-related articles")
            # One broadcast per batch — prevents request flood on the frontend
            await ws_manager.broadcast("new_article", {"count": stored})


# Ynet flash news RSS feeds (try multiple known feed URLs)
YNET_FLASH_FEEDS = [
    "https://www.ynet.co.il/Integration/StoryRss3.xml",   # breaking/flash category
    "https://www.ynet.co.il/Integration/StoryRss6.xml",   # security/military
    "https://rss.walla.co.il/feed/2689",                   # Walla flash news fallback
]
YNET_FLASH_INTERVAL = 90  # seconds


_FLASH_EXCLUDE_PATTERNS = [
    # Ynet opinion columns: "headline / Author Name"
    re.compile(r' / [^\s]+ [^\s]+$'),
    # Sports — Hebrew
    re.compile(r'(כדורגל|כדורסל|טניס|אולימפי|אצטדיון|שחקן חתם|חתם ב|ליגת העל|מועדון)'),
    # Economy unrelated to war
    re.compile(r'(בורסה|מניות|השקעות|תיק השקעות|קרן נאמנות|תשואה|ריבית|בנק ישראל)'),
]


def _is_flash_worthy(title: str, description: str) -> bool:
    """Stricter war check for flash items — must pass war filter AND not match exclusion patterns."""
    if not _is_war_related(title, description):
        return False
    combined = title + " " + description
    for pat in _FLASH_EXCLUDE_PATTERNS:
        if pat.search(combined):
            return False
    return True


async def _fetch_ynet_flash(client: httpx.AsyncClient) -> List[dict]:
    """Fetch Ynet/Walla flash/breaking news from RSS feeds."""
    seen_urls: set = set()
    articles = []
    for feed_url in YNET_FLASH_FEEDS:
        try:
            resp = await client.get(feed_url, timeout=15.0, follow_redirects=True)
            if resp.status_code != 200:
                continue
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                description = entry.get("summary", "").strip()
                url = entry.get("link", "")
                if not title or not url or url in seen_urls:
                    continue
                if not _is_flash_worthy(title, description):
                    continue
                seen_urls.add(url)

                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])

                articles.append({
                    "source": "ynet_flash",
                    "title": title,
                    "url": url,
                    "description": re.sub(r'<[^>]+>', '', description),
                    "published_at": pub_date,
                    "image_url": None,
                })
        except Exception as e:
            logger.debug(f"Flash feed {feed_url} failed: {e}")

    logger.info(f"Ynet flash: {len(articles)} war-related articles from RSS")
    return articles


async def poll_rss_feeds():
    """Main loop: poll RSS feeds periodically."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                all_articles = []
                for source, url in RSS_FEEDS.items():
                    articles = await _fetch_rss(client, source, url)
                    all_articles.extend(articles)
                await _store_articles(all_articles)
            except Exception as e:
                logger.error(f"RSS poll error: {e}")
            await asyncio.sleep(RSS_POLL_INTERVAL)


async def poll_nyt_api():
    """Main loop: poll NYT API periodically."""
    if not NYT_API_KEY:
        logger.warning("NYT_API_KEY not set, skipping NYT polling")
        return
    async with httpx.AsyncClient() as client:
        while True:
            try:
                articles = await _fetch_nyt(client)
                await _store_articles(articles)
            except Exception as e:
                logger.error(f"NYT poll error: {e}")
            await asyncio.sleep(NYT_POLL_INTERVAL)


async def poll_ynet_flash():
    """Main loop: scrape Ynet breaking news every 90 seconds."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                articles = await _fetch_ynet_flash(client)
                await _store_articles(articles)
            except Exception as e:
                logger.error(f"Ynet flash poll error: {e}")
            await asyncio.sleep(YNET_FLASH_INTERVAL)
