"""
Report pipeline - one run: suspensions + IVR files and the mail as a draft.

    python main.py                  check once (schedule this with Windows Task Scheduler)
    python main.py --loop           keep running, check every CHECK_INTERVAL_MIN minutes
    python main.py --process FILE   run only step 2 and 3 on a file that is already downloaded;
                                    the mail is only printed, no draft is opened

Each check downloads only the NEWEST new report. Older new reports are marked as seen and skipped.
This run saves BOTH CSV files (suspensions and IVR) in the dated folder and opens the mail in Outlook
as a draft. The mail is NOT sent: someone checks it and presses Send.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import truststore

from pipeline.LogSetup import LogSetup
from pipeline.ReportRun import ReportRun
from pipeline.Settings import Settings

log = logging.getLogger("pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the newest report from the portal, save the CSV files and prepare the mail.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="run forever, check every CHECK_INTERVAL_MIN")
    mode.add_argument("--process", metavar="FILE", type=Path, help="only run processing + saving on FILE")
    args = parser.parse_args()

    truststore.inject_into_ssl()  # trust the same certificates Windows trusts (company CA)
    settings = Settings.load()
    LogSetup.start_logging(settings.log_file)
    report_run = ReportRun(settings)

    if args.process:
        report_run.process_file_without_mail(args.process)
        return 0

    if not args.loop:
        try:
            report_run.check_once()
        except Exception:
            log.exception("Check failed")
            return 1  # non-zero exit code, so Task Scheduler shows the run as failed
        return 0

    while True:
        try:
            report_run.check_once()
        except Exception:
            log.exception("Check failed, will try again next interval")
        time.sleep(settings.check_interval_min * 60)


if __name__ == "__main__":
    sys.exit(main())
