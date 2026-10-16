"""Settings for the pipeline, read from the .env file in the project root, plus the business rules."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------
# Business rules for step 2 (processing). If a rule changes, change it only here.
# ---------------------------------------------------------------
SUSPENSIONS_LIMIT = 1500   # max MSISDNs per day for step S3 (sum of BAN_Nr_msisdns, not the BAN count)
IVR_LIMIT = 10           # max MSISDNs per day for step M (IVR only, it is not added to SUSP)

# Codes in column COL_ACTIVITY_CODE
STEP_CHURN = "C"
STEP_SUSPENSION = "S3"
STEP_SMS = "SM"
STEP_IVR = "M"

# Account types in column ACCOUNT_TYPE: everything that is not business and not KEY is residential
BUSINESS_ACCOUNT_TYPES = {"BUS", "VBB", "VPN", "EPN"}
KEY_ACCOUNT_TYPE = "KEY"            # KEY accounts are left out of the calculations
GROUP_BUSINESS = "BUS"
GROUP_RESIDENTIAL = "PRI"

STATUS_OPEN = "O"                   # BAN_STATUS
IVR_ACTIVE = "IVR"                  # FOLLOW_UP_TYPE - active customers
IVR_SUSPENDED = "SUSP"              # FOLLOW_UP_TYPE - suspended customers

# Churn goes into the mail only when the day of the month of the activity date is one of these
CHURN_MAIL_DAYS = {15, 20, 25, 30}

# Columns that are loaded from the report (all other columns are ignored)
REQUIRED_COLUMNS = [
    "BAN", "BAN_STATUS", "DEBTOR_STATUS", "ACCOUNT_TYPE", "BAN_Nr_msisdns",
    "COL_NEXT_STEP_DATE", "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE", "Account_Act_Date",
]

# ADX needs the name MCD_col_mass_chng.csv; whoever puts the file into to_do renames it
SUSPENSIONS_CSV_NAME = "MCD_col_mass_chng_suspensions.csv"
IVR_CSV_NAME = "MCD_col_mass_chng_ivr.csv"


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
    log_file: Path


def load_settings() -> Settings:
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

    return Settings(
        portal_url=portal_url,
        link_selector=os.getenv("LINK_SELECTOR", "a[href*=frmofferfile]"),
        auth_mode=auth_mode,
        download_dir=download_dir,
        output_dir=output_dir,
        mail_to=mail_to,
        mail_cc=os.getenv("MAIL_CC", ""),
        check_interval_min=int(os.getenv("CHECK_INTERVAL_MIN", "60")),
        state_file=PROJECT_DIR / "seen_reports.json",
        log_file=PROJECT_DIR / "pipeline.log",
    )