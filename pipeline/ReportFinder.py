"""Step 1 of the pipeline: find TODAY'S report - on the Report Portal, and after the alarm time also in the share folder.

Rules:
  - only a report with today's date counts; older reports (a Saturday/Sunday report on Monday) are ignored
  - if there are several reports for today, the newest one is used (highest fileid on the portal)
  - nothing found and it is already alarm time (13:30): the alarm mail is sent, once per day
"""
import logging
from datetime import date, datetime
from pathlib import Path

from BusinessDaysCalculator import BusinessDaysCalculator
from .MailSender import MailSender
from .ReportLoader import ReportLoader
from .ReportPortal import ReportPortal
from .Settings import Settings
from .ShareReportFinder import ReportDates, ShareReportFinder
from .StateController import StateController

log = logging.getLogger(__name__)


class ReportFinder:

    def __init__(self, settings: Settings, state_controller: StateController, mail_sender: MailSender):
        self.settings = settings
        self.state_controller = state_controller
        self.mail_sender = mail_sender
        self.share_finder = ShareReportFinder(settings.share_dir, settings.download_dir)

    def find_todays_report(self, now: datetime | None = None) -> Path | None:
        """Returns the path of today's report (downloaded or copied from the share), or None if it is not there yet."""
        now = now or datetime.now()
        today = now.date()
        if not BusinessDaysCalculator().is_business_day(today):
            log.info("%s is not a business day - nothing to do.", today)
            return None

        daily = self.state_controller.load_daily_state(today)
        if daily["processed"]:
            log.info("Today's report is already processed.")
            return None

        path = self.find_on_portal(today)
        after_alarm_time = now.time() >= self.settings.alarm_time
        if path is None and after_alarm_time:
            path = self.share_finder.find_report_for(today)
            if path is None and not daily["alarm_sent"]:
                log.warning("No report for %s by %s - sending the alarm mail.", today, self.settings.alarm_time)
                self.mail_sender.send_alarm_mail(today)
                self.state_controller.save_daily_state(today, processed=False, alarm_sent=True)
        if path is None:
            log.info("Today's report (%s) is not available yet.", today)
        return path

    def find_on_portal(self, today: date) -> Path | None:
        """Downloads the newest unseen report of the portal if it is dated today."""
        portal = ReportPortal(self.settings)
        reports = portal.find_reports()
        seen = self.state_controller.load_seen_reports()
        new = [url for url in reports if url not in seen]
        log.info("Found %d report link(s), %d new", len(reports), len(new))
        if not new:
            return None

        url = portal.pick_newest_report(new)
        # Only the newest report matters. Reports that are not from today are marked as seen and never looked at again.
        link_date = ReportDates.find_in_text(reports[url])
        if link_date is not None and link_date != today:
            log.info("The newest report is dated %s, not %s - ignored.", link_date, today)
            self.state_controller.save_seen_reports(seen | set(new))
            return None

        try:
            path = portal.download_report(url, reports[url])
        except Exception:
            log.exception("Download failed (will retry next check): %s", url)
            return None

        if link_date is None:   # the link has no date: the title of the report decides
            report_date = ReportLoader.find_report_date(ReportLoader.read_report_as_text(path))
            if report_date != today:
                log.info("The newest report (%s) is dated %s, not %s - ignored.", path.name, report_date, today)
                self.state_controller.save_seen_reports(seen | set(new))
                return None
        # Today's report is NOT marked as seen here: it is only done after it was processed successfully
        # (daily_state.json), so a failed run is tried again at the next check.
        log.info("Downloaded %s (skipped %d older new report(s))", path.name, len(new) - 1)
        return path
