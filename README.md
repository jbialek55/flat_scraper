# Flat Scraper - Otodom Rental Listings Monitor

Scrapes rental apartment listings from Otodom, stores them in a local SQLite database, detects new listings and price changes, and sends notifications via Discord. Includes a Discord bot for managing filters.

## Project Structure

```text
flat_scraper/
├── src/flat_scraper/
│   ├── config.py                # settings and environment variables
│   ├── logging_config.py        # logging configuration (stdout + file)
│   ├── main.py                  # single scraper run entrypoint
│   ├── scheduler.py             # periodic scraper scheduler
│   ├── db/
│   │   └── database.py          # SQLite, deduplication, price history, filters
│   ├── scraper/
│   │   ├── links.py             # Playwright: collects listing URLs from search pages
│   │   ├── details.py           # httpx: concurrent fetching of listing details
│   │   └── parser.py            # parses __NEXT_DATA__ from listing HTML
│   ├── notifications/
│   │   ├── formatter.py         # Discord message formatting
│   │   └── discord_notifier.py  # Discord DM notifications
│   ├── bot/
│   │   ├── discord_bot.py       # Discord bot for managing filters (!filters, !set, !clear, !help)
│   │   └── geocoding.py         # address geocoding via Nominatim
│   └── analysis/
│       └── export.py            # pandas export + one-hot encoding
├── tests/                       # unit tests (pytest)
├── data/                        # SQLite database and CSV exports
├── logs/                        # log files
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Setup

1. Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN` and `DISCORD_USER_ID`.
2. Customize `SEARCH_URLS` in `src/flat_scraper/config.py`.

## Running Locally (uv)

```bash
uv sync
uv run playwright install chromium

# Single scraper run:
uv run python -m flat_scraper.main

# Periodic scheduler:
uv run python -m flat_scraper.scheduler

# Discord bot for managing filters:
uv run python -m flat_scraper.bot.discord_bot

# Run tests:
uv run pytest -v
```

## Running with Docker

```bash
docker compose up -d --build
```

This starts both services (`scraper` and `discord-bot`) with persistent `./data` and `./logs` volumes.

## Discord Bot Commands

Once `discord-bot` is running, send commands directly to the bot (via DM or in a server channel it has access to) to configure listing filters stored in SQLite:

| Command | Description | Example |
| --- | --- | --- |
| `!filters` | Show currently active filters | `!filters` |
| `!set min_price <amount>` | Set minimum rent price (PLN) | `!set min_price 2000` |
| `!set max_price <amount>` | Set maximum rent price (PLN) | `!set max_price 4000` |
| `!set min_area <m2>` | Set minimum area in m² | `!set min_area 30` |
| `!set max_area <m2>` | Set maximum area in m² | `!set max_area 60` |
| `!set min_rooms <count>` | Set minimum number of rooms | `!set min_rooms 2` |
| `!set extras <list>` | Set required extras (comma-separated) | `!set extras balcony,lift` |
| `!set location <address>` | Geocode an address and set center point | `!set location Rynek Główny, Kraków` |
| `!set radius <km>` | Set search radius in km (requires `location`) | `!set radius 3` |
| `!clear` | Remove all filters (notify on all listings) | `!clear` |
| `!help` | Display the list of available commands | `!help` |

> **Note:** Setting `location` alone does not filter by distance until you also set `radius` with `!set radius <km>`.
