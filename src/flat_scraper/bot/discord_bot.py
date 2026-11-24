"""
discord_bot.py
--------------
Long-running Discord bot that listens for user commands to manage
listing filters in the SQLite database.
"""

import sqlite3
import discord

from flat_scraper.bot.geocoding import geocode_address
from flat_scraper.config import DISCORD_BOT_TOKEN
from flat_scraper.db.database import (
    clear_filters,
    get_connection,
    get_filters,
    init_db,
    set_filters,
)
from flat_scraper.logging_config import get_logger

logger = get_logger(__name__)

FIELD_MAP = {
    "min_price": "min_price",
    "max_price": "max_price",
    "min_area": "min_area",
    "max_area": "max_area",
    "min_rooms": "min_rooms",
}

HELP_TEXT = (
    "**Available commands:**\n"
    "`!filters` - show current filter settings\n"
    "`!set min_price 2000` - set minimum price\n"
    "`!set max_price 4000` - set maximum price\n"
    "`!set min_area 30` - set minimum area (m²)\n"
    "`!set max_area 60` - set maximum area (m²)\n"
    "`!set min_rooms 2` - set minimum number of rooms\n"
    "`!set extras balcony,lift` - required extras (comma-separated)\n"
    "`!set location <address>` - set center point (e.g. 'Rynek Główny, Kraków')\n"
    "`!set radius 3` - radius in km from the configured location\n"
    "`!clear` - remove all filters"
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


def _format_filters(filters: dict | None) -> str:
    if filters is None:
        return "No filters set - showing all listings."

    lines = ["**Current filters:**"]
    if filters.get("min_price") is not None:
        lines.append(f"  min price: {filters['min_price']} PLN")
    if filters.get("max_price") is not None:
        lines.append(f"  max price: {filters['max_price']} PLN")
    if filters.get("min_area") is not None:
        lines.append(f"  min area: {filters['min_area']} m²")
    if filters.get("max_area") is not None:
        lines.append(f"  max area: {filters['max_area']} m²")
    if filters.get("min_rooms") is not None:
        lines.append(f"  min rooms: {filters['min_rooms']}")
    if filters.get("required_extras"):
        lines.append(f"  required extras: {', '.join(filters['required_extras'])}")
    if filters.get("center_lat") is not None and filters.get("radius_km") is not None:
        label = filters.get("location_label") or f"{filters['center_lat']:.4f}, {filters['center_lon']:.4f}"
        lines.append(f"  location: {label} (radius {filters['radius_km']} km)")
    elif filters.get("center_lat") is not None:
        lines.append("  location set, but NO radius - use `!set radius <km>`")

    if len(lines) == 1:
        return "Filters exist, but are empty - showing all listings."
    return "\n".join(lines)


async def _handle_set_location(message: discord.Message, conn: sqlite3.Connection, raw_value: str) -> None:
    await message.channel.send(f"Searching for location: {raw_value}...")

    try:
        result = await geocode_address(raw_value)
    except Exception as e:
        logger.error(f"Geocoding error for '{raw_value}': {e}")
        await message.channel.send("An error occurred while searching for the location. Please try again.")
        return

    if result is None:
        await message.channel.send(
            f"Could not find location for '{raw_value}'. "
            "Try a more specific address, e.g. 'ul. Floriańska, Kraków'."
        )
        return

    set_filters(
        conn,
        center_lat=result["lat"],
        center_lon=result["lon"],
        location_label=result["display_name"],
    )
    await message.channel.send(
        f"Location set: {result['display_name']}\n"
        f"({result['lat']:.5f}, {result['lon']:.5f})\n"
        "Remember to set a radius: `!set radius <km>` (the location filter "
        "is inactive without a radius)."
    )


async def _handle_set_radius(message: discord.Message, conn: sqlite3.Connection, raw_value: str) -> None:
    current = get_filters(conn)
    if current is None or current.get("center_lat") is None:
        await message.channel.send("Set a location first: `!set location <address>`")
        return

    try:
        value = float(raw_value)
    except ValueError:
        await message.channel.send(f"'{raw_value}' is not a valid number.")
        return

    set_filters(conn, radius_km=value)
    await message.channel.send(f"Radius set: {value} km")


async def _handle_set_command(message: discord.Message, conn: sqlite3.Connection, content: str) -> None:
    parts = content[len("!set "):].split(maxsplit=1)
    if len(parts) != 2:
        await message.channel.send(
            "Usage: `!set <parameter> <value>`\n"
            "Parameters: min_price, max_price, min_area, max_area, "
            "min_rooms, extras, location, radius"
        )
        return

    field, raw_value = parts

    if field == "extras":
        extras = [e.strip() for e in raw_value.split(",") if e.strip()]
        set_filters(conn, required_extras=extras)
        await message.channel.send(f"Required extras set: {', '.join(extras)}")
        return

    if field == "location":
        await _handle_set_location(message, conn, raw_value)
        return

    if field == "radius":
        await _handle_set_radius(message, conn, raw_value)
        return

    if field in FIELD_MAP:
        try:
            value = float(raw_value)
        except ValueError:
            await message.channel.send(f"'{raw_value}' is not a valid number.")
            return

        db_field = FIELD_MAP[field]
        set_filters(conn, **{db_field: value})
        await message.channel.send(f"Set {field} = {value}")
        return

    available = ", ".join(list(FIELD_MAP.keys()) + ["extras", "location", "radius"])
    await message.channel.send(f"Unknown parameter '{field}'. Available: {available}")


@client.event
async def on_ready():
    logger.info(f"Bot logged in as {client.user} - listening for commands.")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    content = message.content.strip()
    conn = get_connection()

    try:
        if content == "!filters":
            filters = get_filters(conn)
            await message.channel.send(_format_filters(filters))
        elif content == "!clear":
            clear_filters(conn)
            await message.channel.send("Filters cleared - showing all listings.")
        elif content.startswith("!set "):
            await _handle_set_command(message, conn, content)
        elif content == "!help":
            await message.channel.send(HELP_TEXT)
    finally:
        conn.close()


def main() -> None:
    init_db()
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("Missing DISCORD_BOT_TOKEN in .env - please set it and try again.")
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
