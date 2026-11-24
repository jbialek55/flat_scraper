"""
parser.py
---------
Converts raw offer page HTML into a structured Python dictionary.
"""

import json
from parsel import Selector


def extract_next_data(html: str) -> dict:
    """Extract and parse JSON from the <script id="__NEXT_DATA__"> tag."""
    sel = Selector(text=html)
    raw_json = sel.css("#__NEXT_DATA__::text").get()
    if not raw_json:
        raise ValueError("__NEXT_DATA__ not found in HTML - page structure may have changed")
    return json.loads(raw_json)


def parse_offer(html: str) -> dict:
    """Parse an offer HTML page into a flat listing dictionary."""
    data = extract_next_data(html)
    ad = data["props"]["pageProps"]["ad"]

    chars = {c["key"]: c.get("value") for c in ad.get("characteristics", [])}
    attrs = ad.get("attributes") or {}

    location = ad.get("location") or {}
    address = location.get("address") or {}
    street = address.get("street") or {}
    coordinates = location.get("coordinates") or {}
    reverse_geo = location.get("reverseGeocoding") or {}
    locations_list = reverse_geo.get("locations") or []

    agency = ad.get("agency") or {}

    return {
        "id": ad["id"],
        "title": ad["title"],
        "url": ad["url"],
        "created_at": ad["createdAt"],
        "modified_at": ad["modifiedAt"],
        "advertiser_type": ad.get("advertiserType"),
        "price": _to_float(chars.get("price")),
        "rent": _to_float(chars.get("rent")),
        "area_m2": _to_float(attrs.get("m")),
        "rooms": _to_int(attrs.get("rooms_num")),
        "floor": attrs.get("floor_no"),
        "building_floors_num": _to_int(attrs.get("building_floors_num")),
        "free_from": attrs.get("free_from"),
        "build_year": attrs.get("build_year"),
        "building_type": attrs.get("building_type"),
        "building_material": attrs.get("building_material"),
        "construction_status": attrs.get("construction_status"),
        "windows_type": attrs.get("windows_type"),
        "energy_certificate": attrs.get("energy_certificate"),
        "heating": attrs.get("heating"),
        "equipment_types": attrs.get("equipment_types", []),
        "extras_types": attrs.get("extras_types", []),
        "security_types": attrs.get("security_types", []),
        "media_types": attrs.get("media_types", []),
        "location_path": [loc["name"] for loc in locations_list],
        "street": street.get("name"),
        "latitude": coordinates.get("latitude"),
        "longitude": coordinates.get("longitude"),
        "agency_name": agency.get("name"),
    }


def _to_float(value) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int(value) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
