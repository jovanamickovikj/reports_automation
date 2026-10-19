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
from logging.handlers import RotatingFileHandler
from pathlib import Path

import truststore

from pipeline.config import Settings, load_settings
from pipeline.portal import download, find_reports, make_session, newest_report
from pipeline.processing import process_report
from pipeline.saves import save_ivr_files, save_suspensions_files
from pipeline.state import load_seen, save_pending, save_seen

log = logging.getLogger("pipeline")


def setup_logging(log_file: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            # Max 1 MB per file, keeps 3 old files, so the log never grows forever.
            RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def check_once(settings: Settings) -> None:
    """Look at the portal once; if there are new reports, download and process only the newest."""
    seen = load_seen(settings.state_file)
    session = make_session(settings)
    reports = find_reports(session, settings)
    new = [url for url in reports if url not in seen]
    log.info("Found %d report link(s), %d new", len(reports), len(new))
    if not new:
        return

    url = newest_report(new)
    try:
        path = download(session, url, settings.download_dir, reports[url])
    except Exception:
        log.exception("Download failed (will retry next check): %s", url)
        return

    # Mark ALL new reports as seen, so the older ones are skipped from now on.
    save_seen(settings.state_file, seen | set(new))
    log.info("Downloaded %s (skipped %d older new report(s))", path.name, len(new) - 1)

    try:
        result = process_report(path)                           # 2. processing
        save_suspensions_files(result, settings.output_dir)     # 3. save the suspensions CSV (IVR comes in main_ivr.py)
        save_pending(settings.pending_file, path)               # tell main_ivr.py which report to use
    except Exception:
        log.exception("Processing / saving failed: %s", path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the newest report from the portal and save the suspensions files.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="run forever, check every CHECK_INTERVAL_MIN")
    mode.add_argument("--process", metavar="FILE", type=Path, help="only run processing + saving on FILE")
    args = parser.parse_args()

    truststore.inject_into_ssl()  # trust the same certificates Windows trusts (company CA)
    settings = load_settings()
    setup_logging(settings.log_file)

    if args.process:
        result = process_report(args.process)
        save_suspensions_files(result, settings.output_dir)
        save_ivr_files(result, settings.output_dir)
        print("\n===== MAIL (not sent) =====")
        print(result.mail_text)
        return 0

    if not args.loop:
        try:
            check_once(settings)
        except Exception:
            log.exception("Check failed")
            return 1  # non-zero exit code, so Task Scheduler shows the run as failed
        return 0

    while True:
        try:
            check_once(settings)
        except Exception:
            log.exception("Check failed, will try again next interval")
        time.sleep(settings.check_interval_min * 60)


if __name__ == "__main__":
    sys.exit(main())