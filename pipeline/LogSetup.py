"""Sets up the log: every message goes to the log file and to the screen."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LogSetup:

    @staticmethod
    def start_logging(log_file: Path) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[
                # Max 1 MB per file, keeps 3 old files, so the log never grows forever.
                RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
