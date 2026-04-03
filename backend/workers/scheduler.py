"""Background task scheduler using asyncio."""

import asyncio
import logging
from typing import List

from services.news_aggregator import poll_nyt_api, poll_rss_feeds, poll_ynet_flash
from services.telegram_monitor import run_telegram_monitor
from services.ai_summary import auto_generate_summary

logger = logging.getLogger(__name__)


def start_background_tasks() -> List[asyncio.Task]:
    """Launch all background pollers. Returns list of tasks for cancellation."""
    tasks = [
        asyncio.create_task(poll_rss_feeds(), name="rss_feeds"),
        asyncio.create_task(poll_nyt_api(), name="nyt_api"),
        asyncio.create_task(poll_ynet_flash(), name="ynet_flash"),
        asyncio.create_task(run_telegram_monitor(), name="telegram_monitor"),
        asyncio.create_task(auto_generate_summary(), name="ai_summary"),
    ]
    logger.info(f"Started {len(tasks)} background tasks")
    return tasks
