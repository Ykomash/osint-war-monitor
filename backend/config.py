import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
# DATA_DIR can be overridden via env var — Railway sets this to its volume mount path
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
MEDIA_DIR = DATA_DIR / "media"
DB_PATH = DATA_DIR / "osint.db"

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# News
RSS_POLL_INTERVAL = 120  # seconds
RSS_FEEDS = {
    "ynet": "https://www.ynet.co.il/Integration/StoryRss2.xml",
    "cnn": "http://rss.cnn.com/rss/edition_meast.rss",
    "nyt": "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml",
    "bbc": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "toi": "https://www.timesofisrael.com/feed/",
}

NYT_API_KEY = os.getenv("NYT_API_KEY", "")
NYT_POLL_INTERVAL = 600  # seconds

# Telegram
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION_PATH = str(DATA_DIR / "telegram")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SUMMARY_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
