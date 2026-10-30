"""Step 2 of the pipeline: calculations on a downloaded report (MAZ BAN Open Invoices).

Four reports: Churn (C), Suspensions (S3), SMS Notification (SM), IVR (M).
Suspensions and IVR also decide which customers are postponed to the next business day
(the oldest by Account_Act_Date) when the MSISDN limit is exceeded.

process_report(path) returns the two mail texts and the postponed customers; saving and mailing
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

        # Churn goes into the mail only when there is at least one churn BAN for the activity date
        churn = self.build_churn_report(table, activity_date)
        if churn["residential"].bans + churn["business"].bans == 0:
            churn = None
        suspensions = self.build_suspensions_report(table, activity_date, new_date)
        sms = self.build_sms_report(table, activity_date)
        ivr = self.build_ivr_report(table, activity_date, new_date)

        build = self.mail_text_builder.build_mail_text
        return ProcessingResult(
            report_date=report_date,
            activity_date=activity_date,
            new_date=new_date,
            mail_pre_final_text=build(activity_date, churn, suspensions["before"], sms, ivr["before"]),
            mail_final_text=build(activity_date, churn, suspensions["after"], sms, ivr["after"]),
            suspensions_msisdns_before=suspensions["before"]["total"].msisdns,
            suspensions_msisdns_after=suspensions["after"]["total"].msisdns,
            suspensions_postponed=suspensions["postponed"],
            ivr_postponed=ivr["postponed"],
            business_customers=self.build_business_customers(table, new_date),
        )

    # ---------------------------------------------------------------
    # The four reports
    # ---------------------------------------------------------------
    def build_churn_report(self, table, date_):
        """Churn (C): every BAN with code C on the activity date (any status, KEY included).
        It is only counted, never postponed."""
        rows_with_churn_code = table[table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_CHURN]
        rows = rows_with_churn_code[rows_with_churn_code["STEP_DATE"] == date_]
        log.info("Churn on %s: %d BAN(s) (the report has %d BAN(s) with code %s on all dates)",
                 date_, len(rows), len(rows_with_churn_code), BusinessRules.STEP_CHURN)
        if len(rows) == 0:
            log.warning("Churn: no BAN with code %s on %s. Activity codes found in the report: %s",
                        BusinessRules.STEP_CHURN, date_, sorted(table["COL_ACTIVITY_CODE"].unique()))
        return {
            "residential": self.count_bans_and_msisdns(rows[rows["GROUP"] == BusinessRules.GROUP_RESIDENTIAL]),
            "business": self.count_bans_and_msisdns(rows[rows["GROUP"] == BusinessRules.GROUP_BUSINESS]),
        }

    def build_suspensions_report(self, table, date_, new_date):
        """
        Suspensions (S3), open (O) only. The limit covers ALL business + residential MSISDNs.
        Above the limit: first residential (PRI) customers are postponed, oldest first; if that is not
        enough, business (BUS) customers, oldest first, but only those with an overdue amount of at most
        MAX_OVERDUE_TO_POSTPONE_BUSINESS.
        Returns the counts "before" and "after" the postponement and the postponed rows.
        """
        rows = table[(table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_SUSPENSION) &
                     (table["BAN_STATUS"] == BusinessRules.STATUS_OPEN)]
        if BusinessRules.SUSPENSIONS_EXCLUDE_KEY:
            rows = rows[~rows["IS_KEY"]]
        rows_on_date = rows[rows["STEP_DATE"] == date_]
        rows_on_new_date = rows[rows["STEP_DATE"] == new_date]
        residential = rows_on_date[rows_on_date["GROUP"] == BusinessRules.GROUP_RESIDENTIAL]
        business = rows_on_date[rows_on_date["GROUP"] == BusinessRules.GROUP_BUSINESS]

        total_msisdns = int(rows_on_date["BAN_Nr_msisdns"].sum())
        limit = BusinessRules.SUSPENSIONS_LIMIT
        excess = max(0, total_msisdns - limit)
        log.info("Suspensions on %s: PRI %d BAN / %d MSISDN | BUS %d BAN / %d MSISDN | total %d | limit %d",
                 date_, *self.count_bans_and_msisdns(residential), *self.count_bans_and_msisdns(business),
                 total_msisdns, limit)

        postponed_residential = self.pick_oldest_to_cover(residential, excess)
        excess_left = excess - int(postponed_residential["BAN_Nr_msisdns"].sum())
        eligible_business = business[business[BusinessRules.OVERDUE_COLUMN] <=
                                     BusinessRules.MAX_OVERDUE_TO_POSTPONE_BUSINESS]   # NaN = not eligible
        postponed_business = self.pick_oldest_to_cover(eligible_business, excess_left)
        if excess_left > 0:
            log.info("Suspensions: %d BUS customer(s) must be postponed (%d MSISDN eligible with overdue <= %d)",
                     len(postponed_business), int(eligible_business["BAN_Nr_msisdns"].sum()),
                     BusinessRules.MAX_OVERDUE_TO_POSTPONE_BUSINESS)
        postponed = pd.concat([postponed_residential, postponed_business])

        postponed_msisdns = int(postponed["BAN_Nr_msisdns"].sum())
        if postponed_msisdns < excess:
            log.warning("Suspensions: the excess is %d msisdns but only %d can be postponed - the limit %d "
                        "stays exceeded.", excess, postponed_msisdns, limit)
        self.check_new_date("Suspensions", rows_on_new_date, postponed_msisdns, limit, new_date)

        def view(residential_rows, business_rows):
            r, b = self.count_bans_and_msisdns(residential_rows), self.count_bans_and_msisdns(business_rows)
            return {"total": Count(r.bans + b.bans, r.msisdns + b.msisdns), "residential": r, "business": b}

        return {"before": view(residential, business),
                "after": view(residential.drop(postponed_residential.index),
                              business.drop(postponed_business.index)),
                "postponed": postponed}

    def build_business_customers(self, table, new_date):
        """The business customers whose suspension (S3, open) is on new_date = 2 business days after the report date."""
        rows = table[(table["GROUP"] == BusinessRules.GROUP_BUSINESS) &
                     (table["COL_ACTIVITY_CODE"] == BusinessRules.STEP_SUSPENSION) &
                     (table["BAN_STATUS"] == BusinessRules.STATUS_OPEN) &
                     (table["STEP_DATE"] == new_date)]
        log.info("Business customers with suspension on %s: %d BAN(s)", new_date, len(rows))
        return rows

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
        Returns the counts "before" and "after" the postponement and the postponed rows.
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

        excess = max(0, self.count_bans_and_msisdns(active).msisdns - BusinessRules.IVR_LIMIT)
        postponed = self.pick_oldest_to_cover(active, excess)
        if excess > 0:
            self.check_new_date("IVR", active_on_new_date, int(postponed["BAN_Nr_msisdns"].sum()),
                                BusinessRules.IVR_LIMIT, new_date)
        suspended_counts = self.count_bans_and_msisdns(suspended)
        return {"before": {"active": self.count_bans_and_msisdns(active), "suspended": suspended_counts},
                "after": {"active": self.count_bans_and_msisdns(active.drop(postponed.index)),
                          "suspended": suspended_counts},
                "postponed": postponed}

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    @staticmethod
    def count_bans_and_msisdns(rows: pd.DataFrame) -> Count:
        return Count(bans=len(rows), msisdns=int(rows["BAN_Nr_msisdns"].sum()))

    @staticmethod
    def pick_oldest_to_cover(candidates: pd.DataFrame, excess: int) -> pd.DataFrame:
        """Takes whole BANs, oldest first (Account_Act_Date), until their MSISDNs cover the excess."""
        if excess <= 0 or len(candidates) == 0:
            return candidates.iloc[0:0]
        oldest_first = candidates.sort_values("Account_Act_Date", na_position="last", kind="stable")
        collected_before_this_row = oldest_first["BAN_Nr_msisdns"].cumsum().shift(fill_value=0)
        return oldest_first[collected_before_this_row < excess]

    @staticmethod
    def check_new_date(name, rows_on_new_date, postponed_msisdns, limit, new_date) -> None:
        """Warns if the postponed customers push the new date above the limit."""
        already_scheduled = int(rows_on_new_date["BAN_Nr_msisdns"].sum())
        total_on_new_date = already_scheduled + postponed_msisdns
        log.info("%s on %s: already scheduled %d + postponed %d = %d msisdns (limit %d)",
                 name, new_date, already_scheduled, postponed_msisdns, total_on_new_date, limit)
        if total_on_new_date > limit:
            log.warning("%s: the limit will be exceeded on %s - make a plan to spread them over more days.",
                        name, new_date)
