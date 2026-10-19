"""Run 1 of 2: download the newest report, process it and save the SUSPENSIONS files.

The IVR file is calculated here too, but it is only saved (and the mail is only sent) by the second run
(IvrRun.py), which is scheduled separately.
"""
import logging
from pathlib import Path

from .AdxFileSaver import AdxFileSaver
from .PendingIvr import PendingIvr
from .ReportPortal import ReportPortal
from .ReportProcessor import ReportProcessor
from .Settings import Settings
from .StateController import StateController

log = logging.getLogger("pipeline")


class SuspensionsRun:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_controller = StateController(settings)
        self.report_processor = ReportProcessor()
        self.file_saver = AdxFileSaver(settings.output_dir)

    def check_once(self) -> None:
        """Look at the portal once; if there are new reports, download and process only the newest."""
        seen = self.state_controller.load_seen_reports()
        portal = ReportPortal(self.settings)
        reports = portal.find_reports()
        new = [url for url in reports if url not in seen]
        log.info("Found %d report link(s), %d new", len(reports), len(new))
        if not new:
            return

        url = portal.pick_newest_report(new)
        try:
            path = portal.download_report(url, reports[url])
        except Exception:
            log.exception("Download failed (will retry next check): %s", url)
            return

        # Mark ALL new reports as seen, so the older ones are skipped from now on.
        self.state_controller.save_seen_reports(seen | set(new))
        log.info("Downloaded %s (skipped %d older new report(s))", path.name, len(new) - 1)

        self.process_downloaded_report(path)

    def process_downloaded_report(self, path: Path) -> None:
        """Processes the report, saves the suspensions CSV and leaves the finished IVR file and mail for the IVR run."""
        try:
            result = self.report_processor.process_report(path)         # 2. processing
            self.file_saver.save_suspensions_files(result)              # 3. save the suspensions CSV (IVR is saved by IvrRun)
            self.state_controller.save_pending_ivr(PendingIvr(          # leave the IVR file and the mail ready for IvrRun
                report_path=path,
                activity_date=result.activity_date,
                mail_text=result.mail_text,
                ivr_csv_text=self.file_saver.build_ivr_csv_text(result),
                ivr_bans=len(result.ivr_postponed),
            ))
        except Exception:
            log.exception("Processing / saving failed: %s", path)

    def process_file_without_mail(self, path: Path) -> None:
        """For development (python main.py --process FILE): saves BOTH CSV files, the mail is only printed."""
        result = self.report_processor.process_report(path)
        self.file_saver.save_suspensions_files(result)
        self.file_saver.save_ivr_files(result)
        print("\n===== MAIL (not sent) =====")
        print(result.mail_text)
