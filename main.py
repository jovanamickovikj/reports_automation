"""
Report pipeline - run 1 of 2 (suspensions).

    python main.py                  check once (schedule this with Windows Task Scheduler)
    python main.py --process FILE   run only step 2 and 3 on a file that is already downloaded;
                                    saves BOTH suspensions and IVR, the mail is only printed, not sent

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the newest report from the portal and save the suspensions files.")
    parser.add_argument("--process", metavar="FILE", type=Path, help="only run processing + saving on FILE")
    args = parser.parse_args()

    truststore.inject_into_ssl()  # trust the same certificates Windows trusts (company CA)
    settings = Settings.load()
    LogSetup.start_logging(settings.log_file)
    suspensions_run = SuspensionsRun(settings)

    if args.process:
        suspensions_run.process_file_without_mail(args.process)
        return 0

    try:
        suspensions_run.check_once()
    except Exception:
        log.exception("Check failed")
        return 1  # non-zero exit code, so Task Scheduler shows the run as failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
