"""AI-powered daily briefing summary using OpenAI."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from config import OPENAI_API_KEY, SUMMARY_INTERVAL
from database import async_session
from models import NewsArticle, Summary, TelegramMessage
from services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

BRIEFING_PROMPT = """אתה אנליסט מודיעין בכיר המכין תדרוך יומי לפיקוד העורף הישראלי. התדרוך יוצג לקצין מפקד. היה ספציפי, עובדתי ומבוסס נתונים.

כתוב את כל התדרוך **בעברית בלבד**.

## סקירה כללית
3-4 משפטים. ציין את רמת האיום הנוכחית, האירוע המשמעותי ביותר ב-24 השעות האחרונות והקצב המבצעי הכולל. היה ישיר — זהו הסיכום הניהולי.

## [כותרות דינמיות — לפי הנתונים בלבד]
אל תשתמש בכותרות קבועות מראש. צור סעיפים רק עבור נושאים שיש עליהם נתונים ממשיים ב-24 השעות האחרונות.
דוגמאות לכותרות אפשריות (בחר רק את הרלוונטיים): חמאס, חיזבאללה, תימן / החות'ים, איראן, הגדה המערבית, סוריה, עיראק, מתקפות סייבר, דיפלומטיה, מצב הומניטרי.
אל תמציא סעיפים לנושאים שאין עליהם מידע.

בכל סעיף רלוונטי, כלול לפי הצורך:
- ירי / מתקפות / אירועים — מספרים, מיקומים, נפגעים
- מבצעי צה"ל / תגובות צבאיות
- הצהרות מנהיגות ואיומים
- שינויים במיצוב כוחות
- פיתוחים דיפלומטיים
- פרטים לא מאומתים — סמן "(לא מאומת)"

## תחזית ל-24-72 שעות הקרובות
- תרחישי הסלמה סבירים לכל חזית פעילה
- אירועי טריגר שעשויים לשנות את תמונת האיום
- אזורים בישראל בסיכון גבוה בטווח הקצר
- המלצת מוכנות לפיקוד העורף
- פערי מידע מרכזיים המשפיעים על ההערכה

כללים מחייבים:
- כתוב הכל בעברית — תרגם כל תוכן באנגלית
- שמור על שמות מקומות, שמות ארגונים ושמות פעולות בשפת המקור
- סגנון תדרוך צבאי: עובדתי, ישיר, רשימות ממוספרות לפי הצורך
- כלול נתונים ספציפיים כשהם זמינים
- אם הנתונים דלים, ציין זאת במפורש — אל תמלא בהכללות"""


async def generate_summary() -> Optional[str]:
    """Generate a 24-hour intelligence briefing summary."""
    # Prefer env var, fall back to config DB
    api_key = OPENAI_API_KEY
    if not api_key:
        try:
            from models import Config
            async with async_session() as db:
                result = await db.execute(select(Config).where(Config.key == "openai_api_key"))
                cfg = result.scalar_one_or_none()
                if cfg:
                    import json as _j
                    api_key = _j.loads(cfg.value) if cfg.value.startswith('"') else cfg.value
        except Exception:
            pass

    if not api_key:
        logger.warning("OpenAI API key not set, skipping summary generation")
        return None

    # Strip whitespace/newlines — common copy-paste corruption
    api_key = "".join(api_key.split())
    # Validate it looks like a real key (ASCII only, starts with sk-)
    if not api_key.startswith("sk-") or not api_key.isascii():
        raise RuntimeError(
            f"OpenAI API key looks invalid — contains non-ASCII characters or wrong format. "
            f"Key starts with: '{api_key[:10]}...'. Please generate a fresh key at platform.openai.com/api-keys"
        )

    try:
        # Collect last 24h of data
        since = datetime.utcnow() - timedelta(hours=24)

        async with async_session() as db:
            # Get news articles — include description for richer context
            result = await db.execute(
                select(NewsArticle)
                .where(NewsArticle.published_at >= since)
                .order_by(NewsArticle.published_at.desc())
                .limit(50)
            )
            articles = result.scalars().all()

            # Get telegram messages — prioritise flagged, more messages
            result = await db.execute(
                select(TelegramMessage)
                .where(TelegramMessage.timestamp >= since)
                .order_by(TelegramMessage.is_flagged.desc(), TelegramMessage.timestamp.desc())
                .limit(80)
            )
            messages = result.scalars().all()

        # Build context
        import re as _re

        context_parts = []

        if articles:
            context_parts.append("=== NEWS ARTICLES (last 24h) ===")
            seen_titles: set[str] = set()
            for a in articles:
                # Deduplicate by normalised title (lowercase, strip punctuation)
                norm = _re.sub(r'[^\w\s]', '', (a.title or "").lower()).strip()
                if norm in seen_titles:
                    continue
                seen_titles.add(norm)
                time_str = a.published_at.strftime("%H:%M") if a.published_at else "??"
                desc = ""
                if a.description:
                    desc = " | " + _re.sub(r'<[^>]+>', '', a.description).strip()[:150]
                context_parts.append(f"[{a.source.upper()} {time_str}] {a.title}{desc}")

        if messages:
            context_parts.append("\n=== TELEGRAM INTEL (last 24h) ===")
            seen_texts: set[str] = set()
            for m in messages:
                if not m.text or len(m.text.strip()) < 10:
                    continue
                # Deduplicate by first 80 chars of normalised text
                norm = _re.sub(r'\s+', ' ', m.text.strip().lower())[:80]
                if norm in seen_texts:
                    continue
                seen_texts.add(norm)
                time_str = m.timestamp.strftime("%H:%M") if m.timestamp else "??"
                flag_tag = " [PRIORITY]" if m.is_flagged else ""
                context_parts.append(f"[{time_str}{flag_tag}] {m.text[:300]}")

        if not context_parts:
            return "No data available for the last 24 hours. Awaiting intelligence feeds."

        context = "\n".join(context_parts)

        # Use requests (urllib3) instead of httpx — avoids httpx connection issues on Railway
        import requests as _requests

        def _call_openai_sync() -> str:
            resp = _requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": BRIEFING_PROMPT},
                        {"role": "user", "content": f"צור את תדרוך היום על בסיס הנתונים הבאים:\n\n{context}"},
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.3,
                },
                timeout=90,
            )
            if resp.status_code == 401:
                raise RuntimeError(f"Invalid OpenAI API key (401)")
            if resp.status_code == 429:
                raise RuntimeError(f"OpenAI rate limit or quota exceeded (429)")
            if not resp.ok:
                raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:200]}")
            return resp.json()["choices"][0]["message"]["content"]

        summary_text = await asyncio.to_thread(_call_openai_sync)

        # Save to DB
        async with async_session() as db:
            summary = Summary(
                content=summary_text,
                generated_at=datetime.utcnow(),
                period_hours=24,
            )
            db.add(summary)
            await db.commit()
            await db.refresh(summary)

        await ws_manager.broadcast("new_summary", {
            "id": summary.id,
            "generated_at": summary.generated_at.isoformat(),
        })

        logger.info("AI summary generated successfully")
        return summary_text

    except RuntimeError:
        raise  # already formatted, re-raise as-is
    except Exception as e:
        logger.error(f"Failed to generate AI summary: {e}", exc_info=True)
        raise RuntimeError(str(e)) from e


async def auto_generate_summary():
    """Background loop to auto-generate summaries on interval."""
    while True:
        try:
            await generate_summary()
        except Exception as e:
            logger.error(f"Auto summary error: {e}")
        await asyncio.sleep(SUMMARY_INTERVAL)
