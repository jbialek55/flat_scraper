"""
tests/test_parser.py
--------------------
Unit tests for parser.py - verifies that parse_offer() extracts fields
correctly from HTML containing __NEXT_DATA__.
"""

import json
import pytest

from flat_scraper.scraper.parser import _to_float, _to_int, extract_next_data, parse_offer


def _make_html(ad_overrides: dict | None = None) -> str:
    """Build minimal valid HTML with __NEXT_DATA__ matching Otodom's structure."""
    base_ad = {
        "id": 12345678,
        "title": "Test 3-room apartment",
        "url": "https://www.otodom.pl/pl/oferta/test-apartment-ID123",
        "createdAt": "2026-01-01T10:00:00Z",
        "modifiedAt": "2026-01-02T10:00:00Z",
        "advertiserType": "business",
        "characteristics": [
            {"key": "price", "value": "3500"},
            {"key": "rent", "value": "600"},
        ],
        "attributes": {
            "m": "55.5",
            "rooms_num": "3",
            "floor_no": "floor_2",
            "building_floors_num": "4",
            "equipment_types": ["furniture", "fridge"],
            "extras_types": ["balcony", "lift"],
            "security_types": ["monitoring"],
            "media_types": ["internet"],
        },
        "location": {
            "address": {"street": {"name": "Testowa"}},
            "coordinates": {"latitude": 50.06, "longitude": 19.94},
            "reverseGeocoding": {
                "locations": [
                    {"name": "malopolskie"},
                    {"name": "Krakow"},
                ]
            },
        },
        "agency": {"name": "Test Agency"},
    }
    if ad_overrides:
        base_ad.update(ad_overrides)

    next_data = {"props": {"pageProps": {"ad": base_ad}}}

    return f'''
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
    </body></html>
    '''


def test_extract_next_data_parses_valid_json():
    html = _make_html()
    data = extract_next_data(html)
    assert data["props"]["pageProps"]["ad"]["id"] == 12345678


def test_extract_next_data_raises_when_missing():
    html = "<html><body>Missing required script</body></html>"
    with pytest.raises(ValueError):
        extract_next_data(html)


def test_parse_offer_extracts_basic_fields():
    html = _make_html()
    result = parse_offer(html)

    assert result["id"] == 12345678
    assert result["title"] == "Test 3-room apartment"
    assert result["price"] == 3500.0
    assert result["rent"] == 600.0
    assert result["area_m2"] == 55.5
    assert result["rooms"] == 3


def test_parse_offer_extracts_feature_lists():
    html = _make_html()
    result = parse_offer(html)

    assert "balcony" in result["extras_types"]
    assert "lift" in result["extras_types"]
    assert "furniture" in result["equipment_types"]


def test_parse_offer_extracts_location():
    html = _make_html()
    result = parse_offer(html)

    assert result["location_path"] == ["malopolskie", "Krakow"]
    assert result["street"] == "Testowa"
    assert result["latitude"] == 50.06


def test_parse_offer_handles_none_agency():
    html = _make_html({"agency": None})
    result = parse_offer(html)

    assert result["agency_name"] is None


def test_parse_offer_handles_none_location():
    html = _make_html({"location": None})
    result = parse_offer(html)

    assert result["location_path"] == []
    assert result["street"] is None
    assert result["latitude"] is None


def test_to_float_converts_safely():
    assert _to_float("61.44") == 61.44
    assert _to_float(None) is None
    assert _to_float("not a number") is None


def test_to_int_converts_safely():
    assert _to_int("4") == 4
    assert _to_int(None) is None
    assert _to_int("not a number") is None
