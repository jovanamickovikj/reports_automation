"""The one run: download the newest report, process it, save both CSV files and prepare the mail.

The mail is NOT sent: it is opened in Outlook as a draft, so that someone can check it and send it.
"""
import logging
from pathlib import Path

from .AdxFileSaver import AdxFileSaver
from .MailSender import MailSender
from .ReportPortal import ReportPortal
from .ReportProcessor import ReportProcessor
from .Settings import Settings
from .StateController import StateController

log = logging.getLogger("pipeline")


class ReportRun:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_controller = StateController(settings)
        self.report_processor = ReportProcessor()
        self.file_saver = AdxFileSaver(settings.output_dir)
        self.mail_sender = MailSender(settings)

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
        """Processes the report, saves the suspensions and IVR CSV files and opens the mail as a draft."""
        try:
            result = self.report_processor.process_report(path)         # 2. processing
            self.file_saver.save_suspensions_files(result)              # 3. save the suspensions CSV
            self.file_saver.save_ivr_files(result)                      # 3. save the IVR CSV
            self.mail_sender.create_draft_mail(                         # 4. open the mail as a draft (not sent)
                result.activity_date, result.mail_text)
        except Exception:
            log.exception("Processing / saving / draft mail failed: %s", path)

    def process_file_without_mail(self, path: Path) -> None:
        """For development (python main.py --process FILE): saves both CSV files, the mail is only printed."""
        result = self.report_processor.process_report(path)
        self.file_saver.save_suspensions_files(result)
        self.file_saver.save_ivr_files(result)
        print("\n===== MAIL (not sent) =====")
        print(result.mail_text)
