"""Run 2 of 2: save the IVR file that run 1 prepared and send the mail.

Nothing is calculated here and nothing is downloaded: SuspensionsRun already calculated the IVR file and
the mail text and left them in pending_ivr.json. It does not wait: schedule it in Windows Task Scheduler after run 1.
"""
import logging

from .AdxFileSaver import AdxFileSaver
from .MailSender import MailSender
from .Settings import Settings
from .StateController import StateController

log = logging.getLogger("pipeline")


class IvrRun:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_controller = StateController(settings)
        self.file_saver = AdxFileSaver(settings.output_dir)
        self.mail_sender = MailSender(settings)

    def run(self) -> int:
        """Returns the exit code: 0 = done, 1 = nothing to do or something is wrong (Task Scheduler shows it as failed)."""
        pending = self.state_controller.load_pending_ivr()
        if pending is None:
            log.error("Nothing pending: main.py has not processed a new report yet.")
            return 1

        log.info("IVR run for the report: %s", pending.report_path.name)
        self.file_saver.save_staged_ivr_file(                           # 3. save the IVR CSV (already calculated)
            pending.activity_date, pending.ivr_csv_text, pending.ivr_bans)
        self.mail_sender.send_report_mail(                              # 4. send the automatic mail
            pending.activity_date, pending.mail_text)
        self.state_controller.clear_pending_ivr()                       # only after save + mail worked
        return 0
