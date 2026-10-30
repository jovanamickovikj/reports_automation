"""What run 1 (SuspensionsRun) leaves ready for run 2 (IvrRun): the IVR file and the final mails."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class PendingIvr:
    report_path: Path             # the report it was calculated from (for information only)
    activity_date: date           # decides the name of the dated folder and the dates in the mails
    mail_final_text: str          # mail 2: the numbers after the postponement
    ivr_csv_text: str | None      # the finished IVR CSV, None = nobody is postponed in IVR
    ivr_bans: int                 # number of BANs in the IVR CSV (only used for the log)
    bulk_msisdns: int | None      # mail 3 is sent with this number; None = no bulk mail (2500 MSISDN or fewer)
