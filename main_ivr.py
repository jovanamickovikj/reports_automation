"""
Report pipeline - run 2 of 2 (IVR + mail).

    python main_ivr.py

Takes the report that main.py processed (remembered in pending_ivr.json), saves the IVR files
and sends the automatic mail. It does not download anything and does not wait: schedule it in
Windows Task Scheduler after main.py.
"""
import logging
import sys

import truststore

from main import setup_logging
from pipeline.config import Settings, load_settings
from pipeline.processing import process_report
from pipeline.saves import save_ivr_files
from pipeline.send_mail import send_mail
from pipeline.state import clear_pending, load_pending

log = logging.getLogger("pipeline")


def run(settings: Settings) -> int:
    report = load_pending(settings.pending_file)
    if report is None:
        log.error("Nothing pending: main.py has not processed a new report yet.")
        return 1
    if not report.exists():
        log.error("Pending report not found: %s", report)
        return 1

    result = process_report(report)                             # same report, same result as in main.py
    save_ivr_files(result, settings.output_dir)                 # 3. save the IVR CSV
    send_mail(                                                  # 4. send the automatic mail
        to=settings.mail_to,
        cc=settings.mail_cc,
        subject=f"Zakazani aktivnosti za {result.activity_date:%d.%m.%Y} se sledni:",
        body=result.mail_text,
    )
    clear_pending(settings.pending_file)                        # only after save + mail worked
    return 0


def main() -> int:
    truststore.inject_into_ssl()
    settings = load_settings()
    setup_logging(settings.log_file)
    try:
        return run(settings)
    except Exception:
        log.exception("IVR run failed")
        return 1  # non-zero exit code, so Task Scheduler shows the run as failed


if __name__ == "__main__":
    sys.exit(main())
