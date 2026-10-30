"""Looks for the report in the share folder (BI can put it there by hand when the portal does not have it)."""
import logging
import re
import shutil
import time
from datetime import date, datetime
from pathlib import Path

from . import BusinessRules

log = logging.getLogger(__name__)

SECONDS_UNTIL_FILE_IS_FINISHED = 60   # a file changed a moment ago may still be copied by BI


class ShareReportFinder:

    def __init__(self, share_dir: Path, download_dir: Path):
        self.share_dir = share_dir
        self.download_dir = download_dir

    def find_report_for(self, day: date) -> Path | None:
        """
        Returns a copy (in the download folder) of the newest 'maz_ben_open_invoices_New_<date>' file
        for the given day, or None. The date is read from the file name; if the name has no readable
        date, the day the file was last changed is used.
        """
        try:
            candidates = [f for f in self.share_dir.iterdir() if self._is_report_file(f)]
        except OSError as error:
            log.warning("Share folder cannot be read (%s): %s", self.share_dir, error)
            return None

        today_files = [f for f in candidates if self.date_of_file(f) == day]
        if not today_files:
            log.info("No report for %s in the share folder (%d file(s) with the report name)", day, len(candidates))
            return None
        newest = max(today_files, key=lambda f: f.stat().st_mtime)
        if time.time() - newest.stat().st_mtime < SECONDS_UNTIL_FILE_IS_FINISHED:
            log.info("%s was changed less than %d seconds ago - waiting for the next check.",
                     newest.name, SECONDS_UNTIL_FILE_IS_FINISHED)
            return None

        self.download_dir.mkdir(parents=True, exist_ok=True)
        target = self.download_dir / newest.name
        if target.exists():
            target = target.with_name(f"{target.stem}_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}")
        shutil.copyfile(newest, target)   # work on a copy, the file of BI stays untouched
        log.info("Report found in the share folder: %s -> %s", newest, target)
        return target

    @staticmethod
    def _is_report_file(file: Path) -> bool:
        name = file.name.lower()
        return (file.is_file() and not name.startswith("~$")
                and name.startswith(BusinessRules.SHARE_REPORT_PREFIX.lower())
                and name.endswith(BusinessRules.SHARE_REPORT_EXTENSIONS))

    @staticmethod
    def date_of_file(file: Path) -> date:
        """Date from the file name (2026-10-30, 30.10.2026, 30-10-2026, 20261030, 30102026), else the day it was changed."""
        found = ReportDates.find_in_text(file.stem[len(BusinessRules.SHARE_REPORT_PREFIX):])
        return found or datetime.fromtimestamp(file.stat().st_mtime).date()


class ReportDates:
    """Finds a date in a text such as a file name or the text of a download link."""

    PATTERNS = [   # (regex, order of the groups)
        (r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)", "ymd"),
        (r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)", "dmy"),
        (r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", "ymd"),
        (r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", "dmy"),
    ]

    @classmethod
    def find_in_text(cls, text: str) -> date | None:
        for pattern, order in cls.PATTERNS:
            for match in re.finditer(pattern, text):
                a, b, c = map(int, match.groups())
                year, month, day = (a, b, c) if order == "ymd" else (c, b, a)
                try:
                    return date(year, month, day)
                except ValueError:
                    continue
        return None
