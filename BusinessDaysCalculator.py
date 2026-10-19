from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd


class BusinessDaysCalculator:
    """Adds business or calendar days to a datetime.

    Special days = weekends (Sat/Sun) + holidays loaded from the Excel file.
    Business-day mode skips special days; calendar mode counts every day.
    """

    BUSINESS = "business"
    CALENDAR = "calendar"

    def __init__(self, special_days_file=Path(__file__).parent / "special_days_data" / "Special_days.xlsx",
                 sheet_name="without duplicates",
                 date_column="SPECIAL_DAYS_DATE"):
        self.special_days = self._load_special_days(
            special_days_file, sheet_name, date_column
        )

    @staticmethod
    def _load_special_days(path, sheet_name, date_column):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Special days file not found: {path}")

        df = pd.read_excel(path, sheet_name=sheet_name)
        dates = pd.to_datetime(df[date_column], errors="coerce").dropna()
        return {d.date() for d in dates}

    def _is_special(self, d: date) -> bool:
        return d.weekday() >= 5 or d in self.special_days  # 5=Sat, 6=Sun

    def is_business_day(self, d) -> bool:
        """True if `d` (date or datetime) is neither a weekend nor a holiday."""
        d = d.date() if isinstance(d, datetime) else d
        return not self._is_special(d)

    def previous_business_day(self, d):
        """Return `d` itself if it's a business day, otherwise the closest
        earlier business day (skips weekends and holidays). Preserves
        date/datetime type and time-of-day, same convention as add_days.
        """
        was_date = not isinstance(d, datetime) and isinstance(d, date)
        current = datetime(d.year, d.month, d.day) if was_date else d
        while self._is_special(current.date()):
            current -= timedelta(days=1)
        return current.date() if was_date else current

    def add_days(self, start, days: int, mode: str) -> datetime:
        """Return `start` shifted by `days` business or calendar days.

        :param start: datetime object to start from
        :param days:  number of days to add (negative values go backwards)
        :param mode:  "business" or "calendar"
        """
        was_date = not isinstance(start, datetime) and isinstance(start, date)
        if was_date:
            start = datetime(start.year, start.month, start.day)
        elif not isinstance(start, datetime):
            raise TypeError("start must be a datetime or date object")

        mode = mode.strip().lower()
        if mode in ("b", "biz"):
            mode = self.BUSINESS
        elif mode in ("c", "cal"):
            mode = self.CALENDAR

        if mode == self.CALENDAR:
            result = start + timedelta(days=days)
            return result.date() if was_date else result

        if mode != self.BUSINESS:
            raise ValueError(f"mode must be '{self.BUSINESS}' or '{self.CALENDAR}', got '{mode}'")

        step = 1 if days >= 0 else -1
        remaining = abs(days)
        current = start
        while remaining > 0:
            current += timedelta(days=step)
            if not self._is_special(current.date()):
                remaining -= 1
        return current.date() if was_date else current