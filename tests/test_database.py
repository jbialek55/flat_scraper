"""
tests/test_database.py
----------------------
Unit tests for database.py - deduplication (new/price_changed/unchanged),
inactive listing detection, and filters.

Uses an in-memory SQLite database (":memory:") so tests are fast and isolated.
"""

import sqlite3
import pytest

from flat_scraper.db.database import (
    clear_filters,
    get_filters,
    get_known_urls,
    haversine_distance_km,
    listing_matches_filters,
    mark_inactive_listings,
    set_filters,
    sync_listing,
)


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite database with the expected schema."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    cur = connection.cursor()

    cur.execute("""
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY, title TEXT, url TEXT, price REAL, rent REAL,
            area_m2 REAL, rooms INTEGER, floor TEXT, building_floors_num INTEGER,
            free_from TEXT, build_year TEXT, building_type TEXT, building_material TEXT,
            construction_status TEXT, windows_type TEXT, energy_certificate TEXT,
            heating TEXT, equipment_types TEXT, extras_types TEXT, security_types TEXT,
            media_types TEXT, location_path TEXT, street TEXT, latitude REAL,
            longitude REAL, agency_name TEXT, advertiser_type TEXT, created_at TEXT,
            modified_at TEXT, first_seen_at TEXT, last_seen_at TEXT, is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER, price REAL, recorded_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE filters (
            id INTEGER PRIMARY KEY CHECK (id = 1), min_price REAL, max_price REAL,
            min_area REAL, max_area REAL, min_rooms INTEGER, required_extras TEXT,
            center_lat REAL, center_lon REAL, radius_km REAL, location_label TEXT
        )
    """)
    connection.commit()
    yield connection
    connection.close()


def _sample_listing(**overrides) -> dict:
    """Build a minimal valid listing dictionary for tests."""
    listing = {
        "id": 111, "title": "Test apartment", "url": "https://example.com/offer/111",
        "price": 3000.0, "rent": 500.0, "area_m2": 45.0, "rooms": 2, "floor": "floor_1",
        "building_floors_num": 4, "free_from": None, "build_year": None,
        "building_type": None, "building_material": None, "construction_status": None,
        "windows_type": None, "energy_certificate": None, "heating": None,
        "equipment_types": [], "extras_types": ["balcony"], "security_types": [],
        "media_types": [], "location_path": ["Krakow"], "street": None,
        "latitude": None, "longitude": None, "agency_name": None,
        "advertiser_type": "private", "created_at": "2026-01-01T00:00:00Z",
        "modified_at": "2026-01-01T00:00:00Z",
    }
    listing.update(overrides)
    return listing


class TestSyncListing:
    def test_new_listing_returns_new(self, conn):
        status = sync_listing(conn, _sample_listing())
        assert status == "new"

    def test_same_listing_second_time_returns_unchanged(self, conn):
        listing = _sample_listing()
        sync_listing(conn, listing)
        status = sync_listing(conn, listing)
        assert status == "unchanged"

    def test_price_change_returns_price_changed(self, conn):
        listing = _sample_listing(price=3000.0)
        sync_listing(conn, listing)

        listing["price"] = 3200.0
        status = sync_listing(conn, listing)

        assert status == "price_changed"

    def test_price_change_records_history(self, conn):
        listing = _sample_listing(price=3000.0)
        sync_listing(conn, listing)
        listing["price"] = 3200.0
        sync_listing(conn, listing)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM price_history WHERE listing_id = ?", (listing["id"],))
        assert cur.fetchone()["cnt"] == 2


class TestMarkInactive:
    def test_unseen_and_old_listing_marked_inactive(self, conn):
        listing = _sample_listing()
        sync_listing(conn, listing)

        cur = conn.cursor()
        cur.execute("UPDATE listings SET last_seen_at = '2020-01-01T00:00:00' WHERE id = ?", (listing["id"],))
        conn.commit()

        count = mark_inactive_listings(conn, seen_ids=set())
        assert count == 1

    def test_seen_listing_stays_active(self, conn):
        listing = _sample_listing()
        sync_listing(conn, listing)

        count = mark_inactive_listings(conn, seen_ids={listing["id"]})
        assert count == 0


class TestKnownUrls:
    def test_get_known_urls_returns_empty_for_empty_db(self, conn):
        assert get_known_urls(conn) == set()

    def test_get_known_urls_returns_saved_url(self, conn):
        listing = _sample_listing(url="https://example.com/offer/abc")
        sync_listing(conn, listing)

        assert "https://example.com/offer/abc" in get_known_urls(conn)


class TestFilters:
    def test_no_filters_by_default(self, conn):
        assert get_filters(conn) is None

    def test_set_and_get_filter(self, conn):
        set_filters(conn, max_price=4000.0)
        filters = get_filters(conn)
        assert filters["max_price"] == 4000.0

    def test_partial_update_preserves_other_fields(self, conn):
        set_filters(conn, max_price=4000.0)
        set_filters(conn, min_rooms=2)

        filters = get_filters(conn)
        assert filters["max_price"] == 4000.0
        assert filters["min_rooms"] == 2

    def test_clear_filters_removes_all(self, conn):
        set_filters(conn, max_price=4000.0)
        clear_filters(conn)
        assert get_filters(conn) is None


class TestListingMatchesFilters:
    def test_no_filters_matches_all(self):
        listing = _sample_listing()
        assert listing_matches_filters(listing, None) is True

    def test_listing_within_price_range_matches(self):
        listing = _sample_listing(price=3000.0)
        filters = {"min_price": 2000, "max_price": 4000, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": []}
        assert listing_matches_filters(listing, filters) is True

    def test_listing_outside_price_range_rejected(self):
        listing = _sample_listing(price=5000.0)
        filters = {"min_price": None, "max_price": 4000, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": []}
        assert listing_matches_filters(listing, filters) is False

    def test_missing_required_extra_rejected(self):
        listing = _sample_listing(extras_types=["garage"])
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": ["balcony", "lift"]}
        assert listing_matches_filters(listing, filters) is False

    def test_all_required_extras_present_matches(self):
        listing = _sample_listing(extras_types=["garage", "balcony", "lift"])
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": ["balcony", "lift"]}
        assert listing_matches_filters(listing, filters) is True


class TestHaversineDistance:
    def test_same_point_distance_is_zero(self):
        assert haversine_distance_km(50.0617, 19.9373, 50.0617, 19.9373) == pytest.approx(0, abs=0.01)

    def test_known_distance_krakow_warsaw(self):
        krakow = (50.0617, 19.9373)
        warsaw = (52.2297, 21.0122)
        distance = haversine_distance_km(*krakow, *warsaw)
        assert 245 < distance < 260

    def test_short_city_distance(self):
        point_a = (50.0617, 19.9373)
        point_b = (50.0700, 19.9450)
        distance = haversine_distance_km(*point_a, *point_b)
        assert 0.5 < distance < 2.0


class TestLocationFilter:
    def test_unset_location_filter_does_not_restrict(self):
        listing = _sample_listing(latitude=50.0, longitude=20.0)
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": [],
                   "center_lat": None, "center_lon": None, "radius_km": None}
        assert listing_matches_filters(listing, filters) is True

    def test_listing_within_radius_matches(self):
        listing = _sample_listing(latitude=50.0617, longitude=19.9373)
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": [],
                   "center_lat": 50.0617, "center_lon": 19.9373, "radius_km": 1.0}
        assert listing_matches_filters(listing, filters) is True

    def test_listing_outside_radius_rejected(self):
        listing_lat, listing_lon = 52.2297, 21.0122
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": [],
                   "center_lat": 50.0617, "center_lon": 19.9373, "radius_km": 5.0}
        listing = _sample_listing(latitude=listing_lat, longitude=listing_lon)
        assert listing_matches_filters(listing, filters) is False

    def test_listing_without_coordinates_rejected_when_location_filter_active(self):
        listing = _sample_listing(latitude=None, longitude=None)
        filters = {"min_price": None, "max_price": None, "min_area": None,
                   "max_area": None, "min_rooms": None, "required_extras": [],
                   "center_lat": 50.0617, "center_lon": 19.9373, "radius_km": 5.0}
        assert listing_matches_filters(listing, filters) is False
