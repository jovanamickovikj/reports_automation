"""
Report pipeline - run 1 of 2 (suspensions).

    python main.py                  check once (schedule this with Windows Task Scheduler)
    python main.py --process        run only step 2 and 3 on the NEWEST file in the report folder
    python main.py --process FILE   the same on a file you name;
                                    saves BOTH suspensions and IVR, the mails are only printed, not sent

Each check looks for TODAY'S report only (portal; after ALARM_TIME also the share folder).
If it is not there by ALARM_TIME, the alarm mail is sent (once). Schedule main.py to run every 30-60 minutes.
When the report is found: pre-final mail, Business_korisnici.xlsx, suspensions CSV to the share folder.
The IVR file and the final / bulk mails are left ready in pending_ivr.json; main_ivr.py (scheduled separately) sends them.
"""
import argparse
import logging
import sys
from pathlib import Path

import truststore

from pipeline.LogSetup import LogSetup
from pipeline.Settings import Settings
from pipeline.SuspensionsRun import SuspensionsRun

log = logging.getLogger("pipeline")


def newest_report_in(folder: Path) -> Path:
    """The most recently changed report file (.xlsx, .xls, .csv) in the folder."""
    files = [f for f in folder.glob("*") if f.suffix.lower() in (".xlsx", ".xls", ".csv") and not f.name.startswith("~$")]
    if not files:
        raise SystemExit(f"No report file in {folder}. Put the report there or give the file: --process FILE")
    newest = max(files, key=lambda f: f.stat().st_mtime)
    log.info("Using the newest file in the report folder: %s", newest.name)
    return newest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the newest report from the portal and save the suspensions files.")
    parser.add_argument("--process", metavar="FILE", type=Path, nargs="?", const=Path(),
                        help="only run processing + saving on FILE (without FILE: the newest file in the report folder)")
    args = parser.parse_args()

    truststore.inject_into_ssl()  # trust the same certificates Windows trusts (company CA)
    settings = Settings.load()
    LogSetup.start_logging(settings.log_file)
    suspensions_run = SuspensionsRun(settings)

    if args.process is not None:
        path = args.process if str(args.process) != "." else newest_report_in(settings.download_dir)
        suspensions_run.process_file_without_mail(path)
        return 0

    try:
        suspensions_run.check_once()
    except Exception:
        log.exception("Check failed")
        return 1  # non-zero exit code, so Task Scheduler shows the run as failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
