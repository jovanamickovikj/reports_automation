"""What run 1 (SuspensionsRun) leaves ready for run 2 (IvrRun): the finished IVR file and the mail."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class PendingIvr:
    report_path: Path             # the downloaded report it was calculated from (for information only)
    activity_date: date           # decides the name of the dated folder
    mail_text: str                # the mail that run 2 sends
    ivr_csv_text: str | None      # the finished IVR CSV, None = nobody is postponed in IVR
    ivr_bans: int                 # number of BANs in the IVR CSV (only used for the log)
