"""
config.py
---------
Centralized configuration for constants and project settings.
Sensitive values (tokens, IDs) and paths are loaded from environment variables
(or a .env file), with sensible defaults for local paths.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Otodom ---
BASE_URL = "https://www.otodom.pl"

SEARCH_URLS = [
    "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/malopolskie/krakow/krakow/krakow",
]

MAX_PAGES_PER_SEARCH = 90          # maximum search result pages to crawl per run
REQUEST_DELAY_SECONDS = 1.5        # delay between httpx requests (offer details)
LISTING_PAGE_DELAY_SECONDS = 2.0   # delay between search result pages (Playwright)
STOP_AFTER_CONSECUTIVE_KNOWN = 8

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# --- Database and logs ---
DB_PATH = os.environ.get("DB_PATH", "data/listings.db")
LOG_FILE = os.environ.get("LOG_FILE", "logs/scraper.log")

# Hours without being seen in results before marking a listing as inactive
INACTIVE_THRESHOLD_HOURS = 6

# --- Scheduler ---
SCRAPE_INTERVAL_MINUTES = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", "30"))

# --- Discord ---
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID", "")
