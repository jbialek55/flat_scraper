"""
discord_notifier.py
-------------------
Sends new listing and price change notifications as Discord DMs via REST API.
"""

import asyncio
import httpx

from flat_scraper.config import DISCORD_BOT_TOKEN, DISCORD_USER_ID
from flat_scraper.logging_config import get_logger
from flat_scraper.notifications.formatter import format_listing_message

logger = get_logger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


async def _get_dm_channel_id(client: httpx.AsyncClient) -> str:
    """Open or retrieve an existing DM channel with the configured user."""
    response = await client.post(
        f"{DISCORD_API_BASE}/users/@me/channels",
        json={"recipient_id": DISCORD_USER_ID},
    )
    response.raise_for_status()
    return response.json()["id"]


async def notify_listing(listing: dict, status: str) -> None:
    """Send a single listing notification as a Discord DM."""
    if not DISCORD_BOT_TOKEN or not DISCORD_USER_ID:
        logger.warning("Skipped notification - DISCORD_BOT_TOKEN/DISCORD_USER_ID not configured")
        return

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    text = format_listing_message(listing, status)

    async with httpx.AsyncClient(headers=headers, timeout=15) as client:
        channel_id = await _get_dm_channel_id(client)
        response = await client.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            json={"content": text},
        )
        response.raise_for_status()


async def notify_batch(listings_with_status: list[tuple[dict, str]]) -> None:
    """Send notifications sequentially with a rate-limit delay."""
    for listing, status in listings_with_status:
        try:
            await notify_listing(listing, status)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Discord send error ({e.response.status_code}): {listing.get('title')}"
            )
        await asyncio.sleep(1.0)


if __name__ == "__main__":
    test_listing = {
        "title": "Test 2-room apartment",
        "price": 3500,
        "rent": 600,
        "area_m2": 45,
        "rooms": 2,
        "location_path": ["malopolskie", "Krakow", "Kliny"],
        "url": "https://www.otodom.pl/pl/oferta/example-listing",
    }
    asyncio.run(notify_listing(test_listing, "new"))
