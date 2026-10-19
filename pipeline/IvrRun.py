"""Run 2 of 2: take the report that SuspensionsRun processed, save the IVR files and send the mail.

It does not download anything and does not wait: schedule it in Windows Task Scheduler after run 1.
"""
import logging

from .AdxFileSaver import AdxFileSaver
from .MailSender import MailSender
from .ReportProcessor import ReportProcessor
from .Settings import Settings
from .StateController import StateController

log = logging.getLogger("pipeline")


class IvrRun:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_controller = StateController(settings)
        self.report_processor = ReportProcessor()
        self.file_saver = AdxFileSaver(settings.output_dir)
        self.mail_sender = MailSender(settings)

    def run(self) -> int:
        """Returns the exit code: 0 = done, 1 = nothing to do or something is wrong (Task Scheduler shows it as failed)."""
        report = self.state_controller.load_pending_report()
        if report is None:
            log.error("Nothing pending: main.py has not processed a new report yet.")
            return 1
        if not report.exists():
            log.error("Pending report not found: %s", report)
            return 1

        result = self.report_processor.process_report(report)           # same report, same result as in run 1
        self.file_saver.save_ivr_files(result)                          # 3. save the IVR CSV
        self.mail_sender.send_report_mail(result)                       # 4. send the automatic mail
        self.state_controller.clear_pending_report()                    # only after save + mail worked
        return 0
