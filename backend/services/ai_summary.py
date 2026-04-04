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

BRIEFING_PROMPT = """You are a senior military intelligence analyst preparing a daily briefing for the Israeli Home Front Command. This briefing will be presented to a commander. Be specific, informative, and data-driven.

Structure the briefing EXACTLY as follows — no additional sections:

## Overview
3-4 sentences. State the current threat level, the most significant event in the last 24 hours, and the overall operational tempo. Be direct — this is the executive summary.

## Iran
Cover ALL of the following if there is relevant data:
- Missile/drone launches or tests
- Nuclear program developments (enrichment levels, IAEA reports, facility activity)
- Proxy coordination (orders to Hezbollah, Houthis, Iraqi militias)
- Diplomatic activity or sanctions
- Statements and threats by Iranian leadership
- Military posture changes
Cite specific numbers, locations, and times when available. If no significant activity: "No significant developments."

## Lebanon
Cover ALL of the following if there is relevant data:
- Hezbollah rocket, missile, drone, or anti-tank fire into Israel — numbers, locations, casualties
- IDF operations in Lebanon — locations, objectives, outcomes
- Ceasefire compliance or violations
- Hezbollah force movements, rearmament, or military infrastructure
- Lebanese army or UNIFIL activity
- Civilian displacement or humanitarian situation affecting operational space
Cite specific numbers, locations, and times when available. If no significant activity: "No significant developments."

## Yemen
Cover ALL of the following if there is relevant data:
- Houthi ballistic missile or drone launches — targets, interception outcome
- Red Sea shipping attacks — vessel names, locations, nationalities
- US/coalition strikes on Houthi positions — locations, results
- Houthi declarations and threats
- Strategic impact on Israeli shipping or airspace
Cite specific numbers, locations, and times when available. If no significant activity: "No significant developments."

## What to Expect Next
Based on current intelligence patterns, assess:
- Most likely escalation scenarios in the next 24-72 hours per front (Iran / Lebanon / Yemen)
- Trigger events that could change the threat picture (diplomatic developments, IDF operations, retaliation cycles)
- Which areas of Israel face the highest threat in the near term
- Recommended readiness posture for Home Front Command
- Key unknowns or intelligence gaps that could affect the assessment

RULES:
- Military briefing style: factual, direct, numbered lists where appropriate
- Include specific figures, unit names, and locations when the data provides them
- Flag unverified information with "(unconfirmed)"
- Translate Hebrew content; preserve Hebrew place names and organization names
- Never pad with vague generalities — if data is thin, say so and explain the gap"""


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
        context_parts = []

        if articles:
            context_parts.append("=== NEWS ARTICLES (last 24h) ===")
            for a in articles:
                time_str = a.published_at.strftime("%H:%M") if a.published_at else "??"
                desc = ""
                if a.description:
                    import re as _re
                    desc = " | " + _re.sub(r'<[^>]+>', '', a.description).strip()[:150]
                context_parts.append(f"[{a.source.upper()} {time_str}] {a.title}{desc}")

        if messages:
            context_parts.append("\n=== TELEGRAM INTEL (last 24h) ===")
            for m in messages:
                if not m.text or len(m.text.strip()) < 10:
                    continue
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
                        {"role": "user", "content": f"Generate today's briefing based on this data:\n\n{context}"},
                    ],
                    "max_tokens": 3000,
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
