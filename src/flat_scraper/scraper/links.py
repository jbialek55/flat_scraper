"""
links.py
--------
Collects listing URLs from search result pages using Playwright.
"""

import asyncio
import re
from playwright.async_api import async_playwright

from flat_scraper.config import (
    BASE_URL,
    LISTING_PAGE_DELAY_SECONDS,
    MAX_PAGES_PER_SEARCH,
    USER_AGENT,
)
from flat_scraper.logging_config import get_logger

logger = get_logger(__name__)


async def get_listing_urls(
    search_url: str,
    known_urls: set[str] | None = None,
    max_pages: int = MAX_PAGES_PER_SEARCH,
) -> list[str]:
    """
    Iterate through search result pages and collect listing URLs.
    Automatically detects the last page via redirects or missing listing cards.
    """
    known_urls = known_urls or set()
    urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(user_agent=USER_AGENT)

            page_num = 1
            while True:
                if page_num > max_pages:
                    logger.info(f"Reached maximum page limit ({max_pages}) - stopping.")
                    break

                separator = "&" if "?" in search_url else "?"
                url = f"{search_url}{separator}page={page_num}"

                logger.info(f"Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded")

                current_url = page.url
                logger.info(f"Resolved URL after navigation: {current_url}")

                expected_page = f"page={page_num}"
                if expected_page not in current_url:
                    match = re.search(r"page=(\d+)", current_url)
                    if match:
                        actual_page = int(match.group(1))
                        logger.info(
                            f"Redirected from page={page_num} to page={actual_page} - reached last page."
                        )
                    else:
                        logger.info("Redirected to URL without page parameter - reached last page.")
                    break

                try:
                    await page.wait_for_selector('a[data-cy="listing-item-link"]', timeout=5_000)
                except Exception:
                    logger.info(f"Page {page_num}: no listings found - reached last page.")
                    break

                hrefs = await page.eval_on_selector_all(
                    'a[data-cy="listing-item-link"]',
                    "elements => elements.map(el => el.getAttribute('href'))",
                )

                page_urls = [
                    BASE_URL + h for h in hrefs if h and h.startswith("/pl/oferta/")
                ]

                if not page_urls:
                    logger.info(f"Page {page_num}: 0 listings - reached last page.")
                    break

                new_count = 0
                for listing_url in page_urls:
                    if listing_url not in known_urls:
                        new_count += 1
                    urls.add(listing_url)

                logger.info(
                    f"Page {page_num}: +{new_count} new, "
                    f"{len(page_urls) - new_count} known (total collected: {len(urls)})"
                )

                page_num += 1
                await asyncio.sleep(LISTING_PAGE_DELAY_SECONDS)
        finally:
            await browser.close()

    return list(urls)


async def get_all_listing_urls(
    search_urls: list[str],
    known_urls: set[str] | None = None,
) -> list[str]:
    """Collect deduplicated listing URLs across multiple search URLs."""
    all_urls: set[str] = set()
    for search_url in search_urls:
        logger.info(f"Collecting links from: {search_url}")
        urls = await get_listing_urls(search_url, known_urls=known_urls)
        all_urls.update(urls)
    return list(all_urls)


if __name__ == "__main__":
    from flat_scraper.config import SEARCH_URLS

    found = asyncio.run(get_all_listing_urls(SEARCH_URLS))
    logger.info(f"Found {len(found)} unique listings in total.")
