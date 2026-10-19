"""Settings of the pipeline, read from the .env file in the project root."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    portal_url: str          # page that lists the reports
    link_selector: str       # CSS selector that matches the report download links
    auth_mode: str           # "windows" (your Windows login) or "none"
    download_dir: Path       # where downloaded reports are saved
    output_dir: Path         # where the CSV files for ADX are saved
    mail_to: str             # recipient of the automatic mail
    mail_cc: str             # optional, can be empty
    check_interval_min: int  # only used with --loop
    state_file: Path         # remembers which reports were already downloaded
    pending_file: Path       # remembers the report that main_ivr.py still has to process
    log_file: Path

    @classmethod
    def load(cls) -> "Settings":
        """Reads the .env file, checks the values and returns the settings."""
        load_dotenv(PROJECT_DIR / ".env")

        portal_url = os.getenv("PORTAL_URL")
        if not portal_url:
            raise SystemExit("PORTAL_URL is not set. Copy .env.example to .env and fill it in.")

        mail_to = os.getenv("MAIL_TO")
        if not mail_to:
            raise SystemExit("MAIL_TO is not set. Add it to .env (see .env.example).")

        auth_mode = os.getenv("AUTH_MODE", "windows").lower()
        if auth_mode not in ("windows", "none"):
            raise SystemExit(f"AUTH_MODE must be 'windows' or 'none', got '{auth_mode}'")

        download_dir = Path(os.getenv("DOWNLOAD_DIR") or "report")
        if not download_dir.is_absolute():
            download_dir = PROJECT_DIR / download_dir

        output_dir = Path(os.getenv("OUTPUT_DIR") or Path.home() / "Downloads")
        if not output_dir.is_absolute():
            output_dir = PROJECT_DIR / output_dir

        return cls(
            portal_url=portal_url,
            link_selector=os.getenv("LINK_SELECTOR", "a[href*=frmofferfile]"),
            auth_mode=auth_mode,
            download_dir=download_dir,
            output_dir=output_dir,
            mail_to=mail_to,
            mail_cc=os.getenv("MAIL_CC", ""),
            check_interval_min=int(os.getenv("CHECK_INTERVAL_MIN", "60")),
            state_file=PROJECT_DIR / "seen_reports.json",
            pending_file=PROJECT_DIR / "pending_ivr.json",
            log_file=PROJECT_DIR / "pipeline.log",
        )
