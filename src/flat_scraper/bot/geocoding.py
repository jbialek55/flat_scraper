"""
geocoding.py
------------
Converts a text address into geographic coordinates using Nominatim (OpenStreetMap).
"""

import httpx

from flat_scraper.logging_config import get_logger

logger = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GEOCODING_USER_AGENT = "flat-scraper-student-project/1.0"


async def geocode_address(address: str) -> dict | None:
    """
    Return {"lat": float, "lon": float, "display_name": str} for the given
    address, or None if no results are found.
    """
    lowered = address.lower()
    query = address if ("poland" in lowered or "polska" in lowered) else f"{address}, Poland"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": GEOCODING_USER_AGENT}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(NOMINATIM_URL, params=params, headers=headers)
        response.raise_for_status()
        results = response.json()

    if not results:
        logger.warning(f"Location not found for address: {address}")
        return None

    result = results[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result["display_name"],
    }


if __name__ == "__main__":
    import asyncio

    async def _test():
        result = await geocode_address("Rynek Główny, Kraków")
        print(result)

    asyncio.run(_test())
