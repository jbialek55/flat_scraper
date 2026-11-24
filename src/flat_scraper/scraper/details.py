"""
details.py
----------
Fetches full listing pages via httpx (async + exponential backoff retries)
and parses them using parser.py.
"""

import asyncio
import random
import httpx

from flat_scraper.config import REQUEST_DELAY_SECONDS, USER_AGENT
from flat_scraper.logging_config import get_logger
from flat_scraper.scraper.parser import parse_offer

logger = get_logger(__name__)

MAX_CONCURRENT_REQUESTS = 3
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 5


async def _fetch_one(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
) -> dict | None:
    """Fetch and parse a single listing with retries on 403/429 and network errors."""
    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = parse_offer(response.text)
                logger.info(f"[{index}/{total}] OK: {data['title']}")

                await asyncio.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, 0.5))
                return data

            except httpx.HTTPStatusError as e:
                status = e.response.status_code

                if status in (404, 410):
                    logger.info(f"[{index}/{total}] Inactive (HTTP {status}): {url}")
                    return None

                if status in (403, 429) and attempt < MAX_RETRIES:
                    wait = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"[{index}/{total}] HTTP {status}, retry {attempt}/{MAX_RETRIES} in {wait}s: {url}"
                    )
                    await asyncio.sleep(wait)
                    continue

                logger.error(f"[{index}/{total}] HTTP {status} error (retries exhausted): {url}")
                return None

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"[{index}/{total}] Network error ({e}), retry {attempt}/{MAX_RETRIES} in {wait}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"[{index}/{total}] Network error (retries exhausted): {url}")
                return None

            except Exception as e:
                logger.error(f"[{index}/{total}] Unexpected parsing error ({e}): {url}")
                return None

        return None


async def fetch_offer_details_async(urls: list[str]) -> list[dict]:
    """Fetch and parse details for a list of listing URLs concurrently."""
    headers = {"User-Agent": USER_AGENT}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    total = len(urls)

    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
        tasks = [
            _fetch_one(client, url, semaphore, i, total)
            for i, url in enumerate(urls, start=1)
        ]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


def fetch_offer_details(urls: list[str]) -> list[dict]:
    """Synchronous wrapper for fetch_offer_details_async."""
    return asyncio.run(fetch_offer_details_async(urls))


if __name__ == "__main__":
    test_url = "https://www.otodom.pl/pl/oferta/4-pokojowe-mieszkanie-z-balkonem-i-garazem-kliny-ID4CEfe"
    result = fetch_offer_details([test_url])
    logger.info(result)
