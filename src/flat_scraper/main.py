"""
main.py
-------
Main entrypoint for a single scrape run:
  1. Load known URLs from the database
  2. Collect listing URLs (Playwright)
  3. Fetch and parse listing details concurrently (httpx)
  4. Save to database, detect new/updated prices, filter, and send notifications
"""

import asyncio
from datetime import datetime

from flat_scraper.config import SEARCH_URLS
from flat_scraper.db.database import (
    get_connection,
    get_filters,
    get_known_urls,
    init_db,
    listing_matches_filters,
    mark_inactive_listings,
    sync_listing,
)
from flat_scraper.logging_config import get_logger
from flat_scraper.notifications.discord_notifier import notify_batch
from flat_scraper.scraper.details import fetch_offer_details_async
from flat_scraper.scraper.links import get_all_listing_urls

logger = get_logger(__name__)


async def run_scrape_job_async() -> None:
    """Execute one full pipeline run: scrape -> database -> notifications."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting scrape run: {start_time.isoformat()}")
    logger.info("=" * 60)

    init_db()

    conn = get_connection()
    try:
        known_urls = get_known_urls(conn)
    finally:
        conn.close()
    logger.info(f"Known listings in database: {len(known_urls)}")

    logger.info("[1/4] Collecting listing URLs...")
    urls = await get_all_listing_urls(SEARCH_URLS, known_urls=known_urls)
    logger.info(f"Found {len(urls)} unique listings to check.")

    logger.info("[2/4] Fetching listing details (concurrently)...")
    listings = await fetch_offer_details_async(urls)
    logger.info(f"Successfully parsed {len(listings)} listings.")

    logger.info("[3/4] Saving to database and detecting changes...")
    conn = get_connection()
    seen_ids: set[int] = set()
    to_notify: list[tuple[dict, str]] = []
    new_count = 0
    changed_count = 0

    try:
        filters = get_filters(conn)

        for listing in listings:
            status = sync_listing(conn, listing)
            seen_ids.add(listing["id"])

            if status in ("new", "price_changed") and listing_matches_filters(listing, filters):
                to_notify.append((listing, status))

            if status == "new":
                new_count += 1
                logger.info(f"New listing: {listing['title']}")
            elif status == "price_changed":
                changed_count += 1
                logger.info(f"Price changed: {listing['title']}")

        inactive_count = mark_inactive_listings(conn, seen_ids)
        if inactive_count:
            logger.info(f"Marked {inactive_count} listings as inactive.")

        conn.commit()
    finally:
        conn.close()

    logger.info(f"[4/4] Sending notifications ({len(to_notify)} queued)...")
    if to_notify:
        await notify_batch(to_notify)
    else:
        logger.info("No matching updates - nothing to send.")

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"Finished run in {duration:.0f}s. "
        f"New: {new_count}, price changes: {changed_count}, inactive: {inactive_count}."
    )


def run_scrape_job() -> None:
    """Synchronous wrapper with top-level error handling for the scheduler."""
    try:
        asyncio.run(run_scrape_job_async())
    except Exception:
        logger.exception("Scrape run failed - will retry on the next scheduled cycle.")


if __name__ == "__main__":
    run_scrape_job()
