"""
database.py
-----------
Database layer: schema initialization, listing synchronization, price history
tracking, inactive listing detection, and user filter management.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

from flat_scraper.config import DB_PATH, INACTIVE_THRESHOLD_HOURS


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory=sqlite3.Row."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist and apply lightweight column migrations."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY,
                title TEXT,
                url TEXT,
                price REAL,
                rent REAL,
                area_m2 REAL,
                rooms INTEGER,
                floor TEXT,
                building_floors_num INTEGER,
                free_from TEXT,
                build_year TEXT,
                building_type TEXT,
                building_material TEXT,
                construction_status TEXT,
                windows_type TEXT,
                energy_certificate TEXT,
                heating TEXT,
                equipment_types TEXT,
                extras_types TEXT,
                security_types TEXT,
                media_types TEXT,
                location_path TEXT,
                street TEXT,
                latitude REAL,
                longitude REAL,
                agency_name TEXT,
                advertiser_type TEXT,
                created_at TEXT,
                modified_at TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER REFERENCES listings(id),
                price REAL,
                recorded_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                min_price REAL,
                max_price REAL,
                min_area REAL,
                max_area REAL,
                min_rooms INTEGER,
                required_extras TEXT,
                center_lat REAL,
                center_lon REAL,
                radius_km REAL,
                location_label TEXT
            )
        """)

        cur.execute("PRAGMA table_info(filters)")
        existing_columns = {row[1] for row in cur.fetchall()}

        new_columns = {
            "center_lat": "REAL",
            "center_lon": "REAL",
            "radius_km": "REAL",
            "location_label": "TEXT",
        }
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                cur.execute(f"ALTER TABLE filters ADD COLUMN {column_name} {column_type}")

        conn.commit()
    finally:
        conn.close()


def sync_listing(conn: sqlite3.Connection, listing: dict) -> str:
    """
    Insert or update a listing and return its status:
      - "new"           -> listing seen for the first time
      - "price_changed" -> known listing with a different price
      - "unchanged"     -> no price change
    """
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute("SELECT price FROM listings WHERE id = ?", (listing["id"],))
    existing = cur.fetchone()

    if existing is None:
        cur.execute("""
            INSERT INTO listings (
                id, title, url, price, rent, area_m2, rooms, floor,
                building_floors_num, free_from, build_year, building_type,
                building_material, construction_status, windows_type,
                energy_certificate, heating, equipment_types, extras_types,
                security_types, media_types, location_path, street,
                latitude, longitude, agency_name, advertiser_type,
                created_at, modified_at, first_seen_at, last_seen_at, is_active
            ) VALUES (
                :id, :title, :url, :price, :rent, :area_m2, :rooms, :floor,
                :building_floors_num, :free_from, :build_year, :building_type,
                :building_material, :construction_status, :windows_type,
                :energy_certificate, :heating, :equipment_types, :extras_types,
                :security_types, :media_types, :location_path, :street,
                :latitude, :longitude, :agency_name, :advertiser_type,
                :created_at, :modified_at, :first_seen_at, :last_seen_at, 1
            )
        """, _prepare_params(listing, first_seen_at=now, last_seen_at=now))

        cur.execute(
            "INSERT INTO price_history (listing_id, price, recorded_at) VALUES (?, ?, ?)",
            (listing["id"], listing["price"], now),
        )
        return "new"

    old_price = existing["price"]
    cur.execute("UPDATE listings SET last_seen_at = ?, is_active = 1 WHERE id = ?", (now, listing["id"]))

    if old_price != listing["price"]:
        cur.execute("UPDATE listings SET price = ? WHERE id = ?", (listing["price"], listing["id"]))
        cur.execute(
            "INSERT INTO price_history (listing_id, price, recorded_at) VALUES (?, ?, ?)",
            (listing["id"], listing["price"], now),
        )
        return "price_changed"

    return "unchanged"


def mark_inactive_listings(conn: sqlite3.Connection, seen_ids: set[int]) -> int:
    """
    Mark active listings as inactive if they were not seen in the current run
    and have exceeded INACTIVE_THRESHOLD_HOURS since last_seen_at.
    """
    cur = conn.cursor()
    threshold = (datetime.now() - timedelta(hours=INACTIVE_THRESHOLD_HOURS)).isoformat()

    if seen_ids:
        placeholders = ",".join("?" * len(seen_ids))
        query = f"""
            UPDATE listings
            SET is_active = 0
            WHERE is_active = 1
            AND id NOT IN ({placeholders})
            AND last_seen_at < ?
        """
        params = list(seen_ids) + [threshold]
    else:
        query = """
            UPDATE listings
            SET is_active = 0
            WHERE is_active = 1
            AND last_seen_at < ?
        """
        params = [threshold]

    cur.execute(query, params)
    return cur.rowcount


def get_filters(conn: sqlite3.Connection) -> dict | None:
    """Return the saved filters dict, or None if no filters are configured."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM filters WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        return None

    result = dict(row)
    result["required_extras"] = json.loads(result["required_extras"] or "[]")
    return result


def set_filters(conn: sqlite3.Connection, **kwargs) -> None:
    """Save or update filters (UPSERT on id=1)."""
    current = get_filters(conn) or {}
    merged = {
        "min_price": kwargs.get("min_price", current.get("min_price")),
        "max_price": kwargs.get("max_price", current.get("max_price")),
        "min_area": kwargs.get("min_area", current.get("min_area")),
        "max_area": kwargs.get("max_area", current.get("max_area")),
        "min_rooms": kwargs.get("min_rooms", current.get("min_rooms")),
        "required_extras": kwargs.get("required_extras", current.get("required_extras", [])),
        "center_lat": kwargs.get("center_lat", current.get("center_lat")),
        "center_lon": kwargs.get("center_lon", current.get("center_lon")),
        "radius_km": kwargs.get("radius_km", current.get("radius_km")),
        "location_label": kwargs.get("location_label", current.get("location_label")),
    }
    merged["required_extras"] = json.dumps(merged["required_extras"], ensure_ascii=False)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO filters (
            id, min_price, max_price, min_area, max_area, min_rooms, required_extras,
            center_lat, center_lon, radius_km, location_label
        )
        VALUES (
            1, :min_price, :max_price, :min_area, :max_area, :min_rooms, :required_extras,
            :center_lat, :center_lon, :radius_km, :location_label
        )
        ON CONFLICT(id) DO UPDATE SET
            min_price = excluded.min_price,
            max_price = excluded.max_price,
            min_area = excluded.min_area,
            max_area = excluded.max_area,
            min_rooms = excluded.min_rooms,
            required_extras = excluded.required_extras,
            center_lat = excluded.center_lat,
            center_lon = excluded.center_lon,
            radius_km = excluded.radius_km,
            location_label = excluded.location_label
    """, merged)
    conn.commit()


def clear_filters(conn: sqlite3.Connection) -> None:
    """Remove all configured filters."""
    cur = conn.cursor()
    cur.execute("DELETE FROM filters WHERE id = 1")
    conn.commit()


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two coordinates."""
    earth_radius_km = 6371.0

    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius_km * c


def listing_matches_filters(listing: dict, filters: dict | None) -> bool:
    """Check whether a listing satisfies the configured filter criteria."""
    if filters is None:
        return True

    price = listing.get("price")
    area = listing.get("area_m2")
    rooms = listing.get("rooms")
    extras = set(listing.get("extras_types") or [])

    if filters.get("min_price") is not None and (price is None or price < filters["min_price"]):
        return False
    if filters.get("max_price") is not None and (price is None or price > filters["max_price"]):
        return False
    if filters.get("min_area") is not None and (area is None or area < filters["min_area"]):
        return False
    if filters.get("max_area") is not None and (area is None or area > filters["max_area"]):
        return False
    if filters.get("min_rooms") is not None and (rooms is None or rooms < filters["min_rooms"]):
        return False

    required = filters.get("required_extras") or []
    if required and not set(required).issubset(extras):
        return False

    center_lat = filters.get("center_lat")
    center_lon = filters.get("center_lon")
    radius_km = filters.get("radius_km")

    if center_lat is not None and center_lon is not None and radius_km is not None:
        listing_lat = listing.get("latitude")
        listing_lon = listing.get("longitude")

        if listing_lat is None or listing_lon is None:
            return False

        if haversine_distance_km(center_lat, center_lon, listing_lat, listing_lon) > radius_km:
            return False

    return True


def get_known_urls(conn: sqlite3.Connection) -> set[str]:
    """Return a set of all listing URLs currently stored in the database."""
    cur = conn.cursor()
    cur.execute("SELECT url FROM listings")
    return {row["url"] for row in cur.fetchall()}


def _prepare_params(listing: dict, first_seen_at: str, last_seen_at: str) -> dict:
    """Serialize Python list fields to JSON strings before SQLite insertion."""
    params = dict(listing)
    for key in ("equipment_types", "extras_types", "security_types", "media_types", "location_path"):
        params[key] = json.dumps(params.get(key) or [], ensure_ascii=False)
    params["first_seen_at"] = first_seen_at
    params["last_seen_at"] = last_seen_at
    return params


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
