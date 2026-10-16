"""Step 2 of the pipeline: calculations on a downloaded report (MAZ BAN Open Invoices).

Four reports: Churn (C), Suspensions (S3), SMS Notification (SM), IVR (M).
Suspensions and IVR also decide which customers are postponed to the next business day
(the most loyal ones = the oldest by Account_Act_Date) when the MSISDN limit is exceeded.

process_report(path) returns the mail text and the postponed customers; saving and mailing
are done by the next steps (saves.py, send_mail.py).

To develop without waiting for new reports:  python main.py --process report/<file>.xlsx
"""
import logging
import re
from collections import namedtuple
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from business_days_calculation import DateCalculator
from . import config

log = logging.getLogger(__name__)

Count = namedtuple("Count", ["bans", "msisdns"])   # number of BANs and the sum of their MSISDNs


@dataclass
class ProcessingResult:
    activity_date: date               # the day the activities are scheduled for
    new_date: date                    # the day the postponed customers move to
    mail_text: str
    suspensions_postponed: pd.DataFrame
    ivr_postponed: pd.DataFrame


# ---------------------------------------------------------------
# Loading
# ---------------------------------------------------------------
def parse_dates(series: pd.Series) -> pd.Series:
    """
    Converts to dates both real Excel dates (read as 2026-10-07 00:00:00) and dates written
    as text (07.10.2026 00:00:00). Invalid dates become NaT.
    """
    text = series.astype(str).str.strip()
    is_iso_format = text.str.match(r"^\d{4}-\d{2}-\d{2}")   # year-month-day: dayfirst must not be applied

    dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    dates[is_iso_format] = pd.to_datetime(text[is_iso_format], format="ISO8601", errors="coerce")
    dates[~is_iso_format] = pd.to_datetime(text[~is_iso_format], dayfirst=True, errors="coerce")
    return dates


def load_report(file_path: Path):
    """
    Returns (clean table, report date, number of removed duplicates).

    Steps: 1) read everything as text  2) report date from the title  3) table with the
           required columns  4) drop duplicate BANs  5) column types and helper columns
    """
    # 1. Read as text; the first row is the title of the report
    if str(file_path).lower().endswith(".csv"):
        raw = pd.read_csv(file_path, header=None, dtype=str, sep=None, engine="python")
    else:
        raw = pd.read_excel(file_path, header=None, dtype=str)

    # 2. Report date from the title, e.g. 'MAZ BAN Open Invoices - 2026-10-06'
    title = " ".join(raw.iloc[:5].fillna("").astype(str).values.ravel())
    year_month_day = re.search(r"(\d{4})-(\d{2})-(\d{2})", title)
    day_month_year = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", title)
    if year_month_day:
        year, month, day = map(int, year_month_day.groups())
        report_date = date(year, month, day)
    elif day_month_year:
        day, month, year = map(int, day_month_year.groups())
        report_date = date(year, month, day)
    else:
        log.warning("No date found in the report title - using today's date.")
        report_date = date.today()

    # 3. Table: the row where 'BAN' stands is the header; keep only the required columns
    rows_with_ban = raw.apply(lambda row: (row.astype(str).str.strip() == "BAN").any(), axis=1)
    if not rows_with_ban.any():
        raise ValueError("Header row with the column 'BAN' not found in the report")
    header_row = raw.index[rows_with_ban][0]
    table = raw.iloc[header_row + 1:].copy()
    table.columns = [str(name).strip() for name in raw.iloc[header_row]]

    missing_columns = [c for c in config.REQUIRED_COLUMNS if c not in table.columns]
    if missing_columns:
        raise ValueError(f"The report is missing columns: {missing_columns}")
    table = table[config.REQUIRED_COLUMNS].dropna(subset=["BAN"]).reset_index(drop=True)

    # 4. Duplicate BANs (the first one is kept)
    is_duplicate = table.duplicated(subset="BAN", keep="first")
    duplicates_removed = int(is_duplicate.sum())
    table = table[~is_duplicate].copy()

    # 5. Column types and helper columns
    table["COL_NEXT_STEP_DATE"] = parse_dates(table["COL_NEXT_STEP_DATE"])
    table["Account_Act_Date"] = parse_dates(table["Account_Act_Date"])
    table["BAN_Nr_msisdns"] = pd.to_numeric(table["BAN_Nr_msisdns"], errors="coerce").fillna(0)
    for column in ["BAN_STATUS", "ACCOUNT_TYPE", "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE"]:
        table[column] = table[column].astype(str).str.strip().str.upper()

    table["STEP_DATE"] = table["COL_NEXT_STEP_DATE"].dt.date          # date without the time
    table["IS_KEY"] = table["ACCOUNT_TYPE"] == config.KEY_ACCOUNT_TYPE
    table["GROUP"] = table["ACCOUNT_TYPE"].apply(
        lambda account_type: (config.GROUP_BUSINESS if account_type in config.BUSINESS_ACCOUNT_TYPES
                              else config.GROUP_RESIDENTIAL)
    )
    return table, report_date, duplicates_removed


# ---------------------------------------------------------------
# The four reports
# ---------------------------------------------------------------
def count_rows(rows: pd.DataFrame) -> Count:
    return Count(bans=len(rows), msisdns=int(rows["BAN_Nr_msisdns"].sum()))


def select_for_postponement(name, candidates, total_msisdns, limit, rows_on_new_date, new_date):
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


def build_churn_report(table, date_):
    """Churn (C): open (O) only, without KEY. It is only counted, never postponed."""
    rows = table[(table["COL_ACTIVITY_CODE"] == config.STEP_CHURN) &
                 (table["STEP_DATE"] == date_) &
                 (table["BAN_STATUS"] == config.STATUS_OPEN) &
                 ~table["IS_KEY"]]
    return {
        "residential": count_rows(rows[rows["GROUP"] == config.GROUP_RESIDENTIAL]),
        "business": count_rows(rows[rows["GROUP"] == config.GROUP_BUSINESS]),
    }


def build_suspensions_report(table, date_, new_date):
    """
    Suspensions (S3): open (O) only, without KEY. The limit applies to the sum of MSISDNs of
    everyone (business + residential), but only residential customers are postponed, oldest first.
    """
    rows = table[(table["COL_ACTIVITY_CODE"] == config.STEP_SUSPENSION) &
                 (table["BAN_STATUS"] == config.STATUS_OPEN) &
                 ~table["IS_KEY"]]
    rows_on_date = rows[rows["STEP_DATE"] == date_]
    rows_on_new_date = rows[rows["STEP_DATE"] == new_date]
    residential = rows_on_date[rows_on_date["GROUP"] == config.GROUP_RESIDENTIAL]
    business = rows_on_date[rows_on_date["GROUP"] == config.GROUP_BUSINESS]

    postponed = select_for_postponement("Suspensions", residential, count_rows(rows_on_date).msisdns,
                                        config.SUSPENSIONS_LIMIT, rows_on_new_date, new_date)
    return {"total": count_rows(rows_on_date), "residential": count_rows(residential),
            "business": count_rows(business), "postponed": postponed}


def build_sms_report(table, date_):
    """SMS Notification (SM): only the number of BANs, no filter. BUS = business types and KEY, PRI = the rest."""
    rows = table[(table["COL_ACTIVITY_CODE"] == config.STEP_SMS) & (table["STEP_DATE"] == date_)]
    is_business = (rows["GROUP"] == config.GROUP_BUSINESS) | rows["IS_KEY"]
    return {"residential_bans": int((~is_business).sum()), "business_bans": int(is_business.sum())}


def build_ivr_report(table, date_, new_date):
    """
    IVR (M): without KEY and without business, only IVR and SUSP.
    IVR and SUSP are counted separately. The limit is for IVR only (it is not added to SUSP);
    only IVR customers are postponed, oldest first.
    """
    rows = table[(table["COL_ACTIVITY_CODE"] == config.STEP_IVR) &
                 ~table["IS_KEY"] &
                 (table["GROUP"] == config.GROUP_RESIDENTIAL) &
                 table["FOLLOW_UP_TYPE"].isin([config.IVR_ACTIVE, config.IVR_SUSPENDED])]
    rows_on_date = rows[rows["STEP_DATE"] == date_]
    active = rows_on_date[rows_on_date["FOLLOW_UP_TYPE"] == config.IVR_ACTIVE]
    suspended = rows_on_date[rows_on_date["FOLLOW_UP_TYPE"] == config.IVR_SUSPENDED]
    active_on_new_date = rows[(rows["STEP_DATE"] == new_date) &
                              (rows["FOLLOW_UP_TYPE"] == config.IVR_ACTIVE)]

    postponed = select_for_postponement("IVR", active, count_rows(active).msisdns,
                                        config.IVR_LIMIT, active_on_new_date, new_date)
    return {"active": count_rows(active), "suspended": count_rows(suspended), "postponed": postponed}


# ---------------------------------------------------------------
# Mail text (wording agreed with the business, Macedonian in Latin letters)
# ---------------------------------------------------------------
def describe_groups(residential, business):
    """'site se PRI' / 'site se BUS' / 'PRI (...), BUS (...)' (empty when there is nobody)."""
    if residential.bans + business.bans == 0:
        return ""
    if business.bans == 0:
        return "site se PRI"
    if residential.bans == 0:
        return "site se BUS"
    return (f"PRI (BAN {residential.bans} / MSISDN {residential.msisdns}), "
            f"BUS (BAN {business.bans} / MSISDN {business.msisdns})")


def describe_postponed(postponed, new_date):
    """Extra text for the mail, only when some customers were postponed."""
    if len(postponed) == 0:
        return ""
    return (f" – odlozeni za {new_date:%d.%m.%Y}: BAN {len(postponed)} / "
            f"MSISDN {int(postponed['BAN_Nr_msisdns'].sum())}")


def build_mail_text(activity_date, new_date, churn, suspensions, sms, ivr):
    """Returns the whole mail as one string. Churn (churn=None) is skipped on days when it is not due."""
    items = []

    if churn is not None:
        bans = churn["residential"].bans + churn["business"].bans
        msisdns = churn["residential"].msisdns + churn["business"].msisdns
        parts = [f"Churn – BAN {bans} / MSISDN {msisdns}",
                 describe_groups(churn["residential"], churn["business"])]
        items.append(" – ".join(part for part in parts if part))

    total = suspensions["total"]
    parts = [f"Za suspenzija – BAN {total.bans} / MSISDN {total.msisdns}",
             describe_groups(suspensions["residential"], suspensions["business"])]
    items.append(" – ".join(part for part in parts if part)
                 + describe_postponed(suspensions["postponed"], new_date))

    sms_total = sms["residential_bans"] + sms["business_bans"]
    items.append(f"SMS Notification – BAN {sms_total} – PRI ({sms['residential_bans']}) BUS ({sms['business_bans']})")

    active, suspended = ivr["active"], ivr["suspended"]
    items.append(
        f"IVR – BAN {active.bans + suspended.bans} / MSISDN {active.msisdns + suspended.msisdns} "
        f"– site se PRI korisnici ({active.bans} ban-a – {active.msisdns} msisdn-a active korisnici i "
        f"{suspended.bans} ban-a – {suspended.msisdns} msisdn-a za suspendirani korisnici)"
        + describe_postponed(ivr["postponed"], new_date)
    )

    lines = [f"Zakazani aktivnosti za {activity_date:%d.%m.%Y} se sledni:", ""]
    lines += [f"{number}. {item}" for number, item in enumerate(items, start=1)]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------
# Entry point of step 2
# ---------------------------------------------------------------
def process_report(path: Path) -> ProcessingResult:
    """
    Reads the downloaded report, calculates the four reports and decides who is postponed.
    Raises an exception if something is wrong: main.py logs it.
    """
    log.info("Processing: %s", path.name)
    calculator = DateCalculator()

    table, report_date, duplicates_removed = load_report(path)
    # Activities are for the next business day; postponed customers go to the one after it
    activity_date = calculator.add_days(report_date, 1, DateCalculator.BUSINESS)
    new_date = calculator.add_days(activity_date, 1, DateCalculator.BUSINESS)
    if calculator.special_days and new_date > max(calculator.special_days):
        log.warning("Special_days.xlsx has no holidays after %s. Update the file - "
                    "the result for %s may be wrong.", max(calculator.special_days), new_date)
    log.info("Report date: %s | activities for: %s | postponing to: %s", report_date, activity_date, new_date)
    log.info("BANs loaded: %d | duplicates removed: %d", len(table), duplicates_removed)

    churn = None
    if activity_date.day in config.CHURN_MAIL_DAYS:
        churn = build_churn_report(table, activity_date)
    suspensions = build_suspensions_report(table, activity_date, new_date)
    sms = build_sms_report(table, activity_date)
    ivr = build_ivr_report(table, activity_date, new_date)

    return ProcessingResult(
        activity_date=activity_date,
        new_date=new_date,
        mail_text=build_mail_text(activity_date, new_date, churn, suspensions, sms, ivr),
        suspensions_postponed=suspensions["postponed"],
        ivr_postponed=ivr["postponed"],
    )