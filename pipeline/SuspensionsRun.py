"""Run 1 of 2: find today's report, process it, mail 1 (pre-final), Business_korisnici.xlsx and the SUSPENSIONS file.

The IVR file, mail 2 (final) and mail 3 (bulk) are done by the second run (IvrRun.py), which is scheduled separately.
Order in this run:  1) pre-final mail  2) Business_korisnici.xlsx  3) suspensions CSV to the share  4) leave the rest pending
"""
import logging
from pathlib import Path

from . import BusinessRules
from .AdxFileSaver import AdxFileSaver
from .BusinessCustomersFile import BusinessCustomersFile
from .MailSender import MailSender
from .PendingIvr import PendingIvr
from .ProcessingResult import ProcessingResult
from .ReportFinder import ReportFinder
from .ReportProcessor import ReportProcessor
from .Settings import Settings
from .StateController import StateController

log = logging.getLogger("pipeline")


class SuspensionsRun:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_controller = StateController(settings)
        self.mail_sender = MailSender(settings)
        self.report_finder = ReportFinder(settings, self.state_controller, self.mail_sender)
        self.report_processor = ReportProcessor()
        self.file_saver = AdxFileSaver(settings.share_dir)
        self.business_customers_file = BusinessCustomersFile(settings.share_dir)

    def check_once(self) -> None:
        """Looks for today's report once; if it is there, processes it."""
        path = self.report_finder.find_todays_report()
        if path is not None:
            self.process_downloaded_report(path)

    def process_downloaded_report(self, path: Path) -> None:
        """Processes the report and does the steps of run 1. Today is marked as done only if all of them worked."""
        try:
            result = self.report_processor.process_report(path)                             # 2. processing
            self.mail_sender.send_pre_final_mail(result.activity_date, result.mail_pre_final_text)   # mail 1
            self.business_customers_file.save(result.business_customers)                   # Business_korisnici.xlsx
            self.file_saver.save_suspensions_files(result)                                 # 3. suspensions CSV
            self.state_controller.save_pending_ivr(self.build_pending(path, result))       # the rest is for run 2
            daily = self.state_controller.load_daily_state(result.report_date)
            self.state_controller.save_daily_state(result.report_date, processed=True, alarm_sent=daily["alarm_sent"])
        except Exception:
            log.exception("Processing / saving failed: %s", path)

    def build_pending(self, path: Path, result: ProcessingResult) -> PendingIvr:
        # More than 2500 suspension MSISDNs BEFORE the postponement -> the bulk mail is sent (with the final number)
        send_bulk = result.suspensions_msisdns_before > BusinessRules.BULK_MAIL_MSISDNS
        return PendingIvr(
            report_path=path,
            activity_date=result.activity_date,
            mail_final_text=result.mail_final_text,
            ivr_csv_text=self.file_saver.build_ivr_csv_text(result),
            ivr_bans=len(result.ivr_postponed),
            bulk_msisdns=result.suspensions_msisdns_after if send_bulk else None,
        )

    def process_file_without_mail(self, path: Path) -> None:
        """For development (python main.py --process FILE): saves everything, the mails are only printed."""
        result = self.report_processor.process_report(path)
        self.business_customers_file.save(result.business_customers)
        self.file_saver.save_suspensions_files(result)
        self.file_saver.save_ivr_files(result)
        print("\n===== MAIL 1: pre-final (not sent) =====")
        print(result.mail_pre_final_text)
        print("===== MAIL 2: final (not sent) =====")
        print(result.mail_final_text)
        if result.suspensions_msisdns_before > BusinessRules.BULK_MAIL_MSISDNS:
            print(f"===== MAIL 3: bulk would be sent (about {result.suspensions_msisdns_after} MSISDN) =====")
