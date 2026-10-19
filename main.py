"""
Report pipeline - run 1 of 2 (suspensions).

    python main.py                  check once (schedule this with Windows Task Scheduler)
    python main.py --loop           keep running, check every CHECK_INTERVAL_MIN minutes
    python main.py --process FILE   run only step 2 and 3 on a file that is already downloaded;
                                    saves BOTH suspensions and IVR, the mail is only printed, not sent

Each check downloads only the NEWEST new report. Older new reports are marked as seen and skipped.
This run saves the SUSPENSIONS files and remembers the report in pending_ivr.json.
main_ivr.py (scheduled separately) then saves the IVR files and sends the mail.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import truststore

from pipeline.LogSetup import LogSetup
from pipeline.Settings import Settings
from pipeline.SuspensionsRun import SuspensionsRun

log = logging.getLogger("pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the newest report from the portal and save the suspensions files.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="run forever, check every CHECK_INTERVAL_MIN")
    mode.add_argument("--process", metavar="FILE", type=Path, help="only run processing + saving on FILE")
    args = parser.parse_args()

    truststore.inject_into_ssl()  # trust the same certificates Windows trusts (company CA)
    settings = Settings.load()
    LogSetup.start_logging(settings.log_file)
    suspensions_run = SuspensionsRun(settings)

    if args.process:
        suspensions_run.process_file_without_mail(args.process)
        return 0

    if not args.loop:
        try:
            suspensions_run.check_once()
        except Exception:
            log.exception("Check failed")
            return 1  # non-zero exit code, so Task Scheduler shows the run as failed
        return 0

    while True:
        try:
            suspensions_run.check_once()
        except Exception:
            log.exception("Check failed, will try again next interval")
        time.sleep(settings.check_interval_min * 60)


if __name__ == "__main__":
    sys.exit(main())
