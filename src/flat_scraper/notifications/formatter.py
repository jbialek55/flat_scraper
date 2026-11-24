"""
formatter.py
------------
Formats listing data into Discord Markdown notification messages.
"""


def format_listing_message(listing: dict, status: str) -> str:
    """Build a readable Discord notification message from a listing dictionary."""
    emoji = "🆕" if status == "new" else "💰"
    label = "New listing" if status == "new" else "Price changed"

    rooms = listing.get("rooms")
    area = listing.get("area_m2")
    price = listing.get("price")
    rent = listing.get("rent")
    location = ", ".join(listing.get("location_path", [])[-2:])

    lines = [
        f"{emoji} **{label}**",
        f"{listing.get('title', 'No title')}",
        "",
        f"💵 {price} PLN" + (f" + {rent} PLN rent" if rent else ""),
        f"📐 {area} m²" + (f", {rooms} rooms" if rooms else ""),
        f"📍 {location}" if location else "",
        "",
        listing.get("url", ""),
    ]
    return "\n".join(line for line in lines if line)
