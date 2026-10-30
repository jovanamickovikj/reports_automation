"""Settings of the pipeline, read from the .env file in the project root."""
import os
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    portal_url: str          # page that lists the reports
    link_selector: str       # CSS selector that matches the report download links
    auth_mode: str           # "windows" (your Windows login) or "none"
    download_dir: Path       # where downloaded reports are saved
    share_dir: Path          # the share folder: CSV files, Business_korisnici.xlsx, and reports that BI puts by hand
    alarm_time: time         # if the report is not there by this time, the alarm mail is sent
    mail_alarm_to: str       # alarm: the report is missing
    mail_pre_final_to: str   # mail 1: all counted activities, before the postponement
    mail_final_to: str       # mail 2: the numbers after the postponement
    mail_final_cc: str
    mail_bulk_to: str        # mail 3: more than 2500 suspension MSISDNs
    mail_bulk_cc: str
    check_interval_min: int  # only used with --loop
    state_file: Path         # remembers which reports were already downloaded
    daily_state_file: Path   # remembers if today's report was found and if the alarm was sent
    pending_file: Path       # remembers the report that main_ivr.py still has to process
    log_file: Path

    @classmethod
    def load(cls) -> "Settings":
        """Reads the .env file, checks the values and returns the settings."""
        load_dotenv(PROJECT_DIR / ".env")

        auth_mode = os.getenv("AUTH_MODE", "windows").lower()
        if auth_mode not in ("windows", "none"):
            raise SystemExit(f"AUTH_MODE must be 'windows' or 'none', got '{auth_mode}'")

        download_dir = Path(os.getenv("DOWNLOAD_DIR") or "report")
        if not download_dir.is_absolute():
            download_dir = PROJECT_DIR / download_dir

        try:
            alarm_time = datetime.strptime(os.getenv("ALARM_TIME", "13:30"), "%H:%M").time()
        except ValueError:
            raise SystemExit("ALARM_TIME must look like 13:30")

        return cls(
            portal_url=cls._required("PORTAL_URL"),
            link_selector=os.getenv("LINK_SELECTOR", "a[href*=frmofferfile]"),
            auth_mode=auth_mode,
            download_dir=download_dir,
            share_dir=Path(cls._required("SHARE_DIR")),
            alarm_time=alarm_time,
            mail_alarm_to=cls._required("MAIL_ALARM_TO"),
            mail_pre_final_to=cls._required("MAIL_PRE_FINAL_TO"),
            mail_final_to=cls._required("MAIL_FINAL_TO"),
            mail_final_cc=os.getenv("MAIL_FINAL_CC", ""),
            mail_bulk_to=cls._required("MAIL_BULK_TO"),
            mail_bulk_cc=os.getenv("MAIL_BULK_CC", ""),
            check_interval_min=int(os.getenv("CHECK_INTERVAL_MIN", "60")),
            state_file=PROJECT_DIR / "seen_reports.json",
            daily_state_file=PROJECT_DIR / "daily_state.json",
            pending_file=PROJECT_DIR / "pending_ivr.json",
            log_file=PROJECT_DIR / "pipeline.log",
        )

    @staticmethod
    def _required(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise SystemExit(f"{name} is not set. Add it to .env (see .env.example).")
        return value
