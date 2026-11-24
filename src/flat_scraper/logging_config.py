"""
logging_config.py
-----------------
Centralized logging setup for the entire project.
Logs are written to both stdout and the file configured in config.LOG_FILE.
"""

import logging
import sys
from pathlib import Path

from flat_scraper.config import LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
