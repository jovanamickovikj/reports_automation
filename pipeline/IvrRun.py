"""Run 2 of 2: save the IVR file that run 1 prepared, send mail 2 (final) and, if needed, mail 3 (bulk).

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
        self.file_saver = AdxFileSaver(settings.share_dir)
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
        self.mail_sender.send_final_mail(                               # 4. mail 2: the numbers after the postponement
            pending.activity_date, pending.mail_final_text)
        if pending.bulk_msisdns is not None:                            # mail 3: more than 2500 suspension MSISDNs
            self.mail_sender.send_bulk_mail(pending.activity_date, pending.bulk_msisdns)
        self.state_controller.clear_pending_ivr()                       # only after save + mail worked
        return 0
