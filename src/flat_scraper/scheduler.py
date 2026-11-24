"""
scheduler.py
------------
Runs run_scrape_job() periodically every SCRAPE_INTERVAL_MINUTES minutes.
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from flat_scraper.config import SCRAPE_INTERVAL_MINUTES
from flat_scraper.logging_config import get_logger
from flat_scraper.main import run_scrape_job

logger = get_logger(__name__)


def main() -> None:
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scrape_job,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        next_run_time=None,
    )

    logger.info(f"Scheduler started - running every {SCRAPE_INTERVAL_MINUTES} minutes.")
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
