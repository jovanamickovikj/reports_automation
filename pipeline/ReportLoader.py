"""Step 2a of the pipeline: read a downloaded report (MAZ BAN Open Invoices) into a clean table."""
import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

from . import BusinessRules

log = logging.getLogger(__name__)


class ReportLoader:

    def load_report(self, file_path: Path):
        """
        Returns (clean table, report date, number of removed duplicates).

        Steps: 1) read everything as text  2) report date from the title  3) table with the
               required columns  4) drop duplicate BANs  5) column types and helper columns
        """
        raw = self.read_report_as_text(file_path)
        report_date = self.find_report_date(raw)
        table = self.cut_out_table(raw)
        table, duplicates_removed = self.remove_duplicate_bans(table)
        table = self.set_column_types_and_helper_columns(table)
        return table, report_date, duplicates_removed

    # ---------------------------------------------------------------
    # The five steps of load_report
    # ---------------------------------------------------------------
    @staticmethod
    def read_report_as_text(file_path: Path) -> pd.DataFrame:
        """1. Read as text; the first row is the title of the report."""
        if str(file_path).lower().endswith(".csv"):
            return pd.read_csv(file_path, header=None, dtype=str, sep=None, engine="python")
        return pd.read_excel(file_path, header=None, dtype=str)

    @staticmethod
    def find_report_date(raw: pd.DataFrame) -> date:
        """2. Report date from the title, e.g. 'MAZ BAN Open Invoices - 2026-10-06'."""
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
        return report_date

    @staticmethod
    def cut_out_table(raw: pd.DataFrame) -> pd.DataFrame:
        """3. Table: the row where 'BAN' stands is the header; keep only the required columns."""
        rows_with_ban = raw.apply(lambda row: (row.astype(str).str.strip() == "BAN").any(), axis=1)
        if not rows_with_ban.any():
            raise ValueError("Header row with the column 'BAN' not found in the report")
        header_row = raw.index[rows_with_ban][0]
        table = raw.iloc[header_row + 1:].copy()
        table.columns = [str(name).strip() for name in raw.iloc[header_row]]

        missing_columns = [c for c in BusinessRules.REQUIRED_COLUMNS if c not in table.columns]
        if missing_columns:
            raise ValueError(f"The report is missing columns: {missing_columns}")
        return table[BusinessRules.REQUIRED_COLUMNS].dropna(subset=["BAN"]).reset_index(drop=True)

    @staticmethod
    def remove_duplicate_bans(table: pd.DataFrame):
        """4. Duplicate BANs (the first one is kept). Returns (table, number of removed rows)."""
        is_duplicate = table.duplicated(subset="BAN", keep="first")
        duplicates_removed = int(is_duplicate.sum())
        return table[~is_duplicate].copy(), duplicates_removed

    def set_column_types_and_helper_columns(self, table: pd.DataFrame) -> pd.DataFrame:
        """5. Column types and helper columns (STEP_DATE, IS_KEY, GROUP)."""
        table["COL_NEXT_STEP_DATE"] = self.convert_text_to_dates(table["COL_NEXT_STEP_DATE"])
        table["Account_Act_Date"] = self.convert_text_to_dates(table["Account_Act_Date"])
        table["BAN_Nr_msisdns"] = pd.to_numeric(table["BAN_Nr_msisdns"], errors="coerce").fillna(0)
        for column in ["BAN_STATUS", "ACCOUNT_TYPE", "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE"]:
            table[column] = table[column].astype(str).str.strip().str.upper()

        table["STEP_DATE"] = table["COL_NEXT_STEP_DATE"].dt.date          # date without the time
        table["IS_KEY"] = table["ACCOUNT_TYPE"] == BusinessRules.KEY_ACCOUNT_TYPE
        table["GROUP"] = table["ACCOUNT_TYPE"].apply(
            lambda account_type: (BusinessRules.GROUP_BUSINESS
                                  if account_type in BusinessRules.BUSINESS_ACCOUNT_TYPES
                                  else BusinessRules.GROUP_RESIDENTIAL)
        )
        return table

    @staticmethod
    def convert_text_to_dates(series: pd.Series) -> pd.Series:
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
