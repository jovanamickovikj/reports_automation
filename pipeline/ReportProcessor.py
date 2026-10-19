"""Step 2 of the pipeline: calculations on a downloaded report (MAZ BAN Open Invoices).

Four reports: Churn (C), Suspensions (S3), SMS Notification (SM), IVR (M).
Suspensions and IVR also decide which customers are postponed to the next business day
(the most loyal ones = the oldest by Account_Act_Date) when the MSISDN limit is exceeded.

process_report(path) returns the mail text and the postponed customers; saving and mailing
are done by the next steps (AdxFileSaver.py, MailSender.py).

To develop without waiting for new reports:  python main.py --process report/<file>.xlsx
"""
import logging
from collections import namedtuple
from pathlib import Path

import pandas as pd

from BusinessDaysCalculator import BusinessDaysCalculator
from . import BusinessRules
from .MailTextBuilder import MailTextBuilder
from .ProcessingResult import ProcessingResult
from .ReportLoader import ReportLoader

log = logging.getLogger(__name__)

Count = namedtuple("Count", ["bans", "msisdns"])   # number of BANs and the sum of their MSISDNs


class ReportProcessor:

    def __init__(self):
        self.report_loader = ReportLoader()
        self.mail_text_builder = MailTextBuilder()

    def process_report(self, path: Path) -> ProcessingResult:
        """
        Reads the downloaded report, calculates the four reports and decides who is postponed.
        Raises an exception if something is wrong: the caller logs it.
        """
        log.info("Processing: %s", path.name)
        calculator = BusinessDaysCalculator()

        table, report_date, duplicates_removed = self.report_loader.load_report(path)
        # Activities are for the next business day; postponed customers go to the one after it
        activity_date = calculator.add_days(report_date, 1, BusinessDaysCalculator.BUSINESS)
        new_date = calculator.add_days(activity_date, 1, BusinessDaysCalculator.BUSINESS)
        if calculator.special_days and new_date > max(calculator.special_days):
            log.warning("Special_days.xlsx has no holidays after %s. Update the file - "
                        "the result for %s may be wrong.", max(calculator.special_days), new_date)
        log.info("Report date: %s | activities for: %s | postponing to: %s", report_date, activity_date, new_date)
        log.info("BANs loaded: %d | duplicates removed: %d", len(table), duplicates_removed)

        churn = None
        if activity_date.day in BusinessRules.CHURN_MAIL_DAYS:
            churn = self.build_churn_report(table, activity_date)
        suspensions = self.build_suspensions_report(table, activity_date, new_date)
        sms = self.build_sms_report(table, activity_date)
        ivr = self.build_ivr_report(table, activity_date, new_date)

        return ProcessingResult(
            activity_date=activity_date,
            new_date=new_date,
            mail_text=self.mail_text_builder.build_mail_text(activity_date, new_date, churn, suspensions, sms, ivr),
            suspensions_postponed=suspensions["postponed"],
            ivr_postponed=ivr["postponed"],
        )

    # ---------------------------------------------------------------
    # The four reports
    # ---------------------------------------------------------------
    def build_churn_report(self, table, date_):
        """Churn (C): open (O) only, without KEY. It is only counted, never postponed."""
        rows = table[(table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_CHURN) &
                     (table["STEP_DATE"] == date_) &
                     (table["BAN_STATUS"] == BusinessRules.STATUS_OPEN) &
                     ~table["IS_KEY"]]
        return {
            "residential": self.count_bans_and_msisdns(rows[rows["GROUP"] == BusinessRules.GROUP_RESIDENTIAL]),
            "business": self.count_bans_and_msisdns(rows[rows["GROUP"] == BusinessRules.GROUP_BUSINESS]),
        }

    def build_suspensions_report(self, table, date_, new_date):
        """
        Suspensions (S3): open (O) only, without KEY. The limit applies to the sum of MSISDNs of
        everyone (business + residential), but only residential customers are postponed, oldest first.
        """
        rows = table[(table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_SUSPENSION) &
                     (table["BAN_STATUS"] == BusinessRules.STATUS_OPEN) &
                     ~table["IS_KEY"]]
        rows_on_date = rows[rows["STEP_DATE"] == date_]
        rows_on_new_date = rows[rows["STEP_DATE"] == new_date]
        residential = rows_on_date[rows_on_date["GROUP"] == BusinessRules.GROUP_RESIDENTIAL]
        business = rows_on_date[rows_on_date["GROUP"] == BusinessRules.GROUP_BUSINESS]

        postponed = self.select_customers_to_postpone(
            "Suspensions", residential, self.count_bans_and_msisdns(rows_on_date).msisdns,
            BusinessRules.SUSPENSIONS_LIMIT, rows_on_new_date, new_date)
        return {"total": self.count_bans_and_msisdns(rows_on_date),
                "residential": self.count_bans_and_msisdns(residential),
                "business": self.count_bans_and_msisdns(business), "postponed": postponed}

    def build_sms_report(self, table, date_):
        """SMS Notification (SM): only the number of BANs, no filter. BUS = business types and KEY, PRI = the rest."""
        rows = table[(table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_SMS) & (table["STEP_DATE"] == date_)]
        is_business = (rows["GROUP"] == BusinessRules.GROUP_BUSINESS) | rows["IS_KEY"]
        return {"residential_bans": int((~is_business).sum()), "business_bans": int(is_business.sum())}

    def build_ivr_report(self, table, date_, new_date):
        """
        IVR (M): without KEY and without business, only IVR and SUSP.
        IVR and SUSP are counted separately. The limit is for IVR only (it is not added to SUSP);
        only IVR customers are postponed, oldest first.
        """
        rows = table[(table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_IVR) &
                     ~table["IS_KEY"] &
                     (table["GROUP"] == BusinessRules.GROUP_RESIDENTIAL) &
                     table["FOLLOW_UP_TYPE"].isin([BusinessRules.IVR_ACTIVE, BusinessRules.IVR_SUSPENDED])]
        rows_on_date = rows[rows["STEP_DATE"] == date_]
        active = rows_on_date[rows_on_date["FOLLOW_UP_TYPE"] == BusinessRules.IVR_ACTIVE]
        suspended = rows_on_date[rows_on_date["FOLLOW_UP_TYPE"] == BusinessRules.IVR_SUSPENDED]
        active_on_new_date = rows[(rows["STEP_DATE"] == new_date) &
                                  (rows["FOLLOW_UP_TYPE"] == BusinessRules.IVR_ACTIVE)]

        postponed = self.select_customers_to_postpone(
            "IVR", active, self.count_bans_and_msisdns(active).msisdns,
            BusinessRules.IVR_LIMIT, active_on_new_date, new_date)
        return {"active": self.count_bans_and_msisdns(active),
                "suspended": self.count_bans_and_msisdns(suspended), "postponed": postponed}

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    @staticmethod
    def count_bans_and_msisdns(rows: pd.DataFrame) -> Count:
        return Count(bans=len(rows), msisdns=int(rows["BAN_Nr_msisdns"].sum()))

    @staticmethod
    def select_customers_to_postpone(name, candidates, total_msisdns, limit, rows_on_new_date, new_date):
        """
        If total_msisdns is above the limit, takes the oldest candidates (Account_Act_Date) until
        the sum of their MSISDNs covers the excess. Warns if the excess cannot be covered, or if
        the postponed customers push the new date above the limit.
        """
        excess = max(0, total_msisdns - limit)
        if excess == 0:
            return candidates.iloc[0:0]

        oldest_first = candidates.sort_values("Account_Act_Date", na_position="last")
        collected_before_this_row = oldest_first["BAN_Nr_msisdns"].cumsum().shift(fill_value=0)
        postponed = oldest_first[collected_before_this_row < excess]
        postponed_msisdns = int(postponed["BAN_Nr_msisdns"].sum())

        if postponed_msisdns < excess:
            log.warning("%s: the excess is %d msisdns but only %d can be postponed.",
                        name, excess, postponed_msisdns)

        already_scheduled = int(rows_on_new_date["BAN_Nr_msisdns"].sum())
        total_on_new_date = already_scheduled + postponed_msisdns
        log.info("%s on %s: already scheduled %d + postponed = %d msisdns (limit %d)",
                 name, new_date, already_scheduled, total_on_new_date, limit)
        if total_on_new_date > limit:
            log.warning("%s: the limit will be exceeded on %s - make a plan to spread them over more days.",
                        name, new_date)
        return postponed
