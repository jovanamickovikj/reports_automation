"""Step 3 of the pipeline: save the CSV files for the ADX job (in the share folder).

Every file is saved twice:
  - inside  <share_dir>/<activity date>_odlozuvanje suspenzii/   (keeps its own name)
  - outside <share_dir>/MCD_col_mass_chng.csv                     (same level as the folder, gets overwritten)
"""
import logging
import shutil
from datetime import date
from pathlib import Path

from . import BusinessRules
from .ProcessingResult import ProcessingResult

log = logging.getLogger(__name__)


class AdxFileSaver:

    def __init__(self, share_dir: Path):
        self.share_dir = share_dir

    # ---- run 1: suspensions are saved right away ----
    def save_suspensions_files(self, result: ProcessingResult) -> list[Path]:
        return self._save_one(result, BusinessRules.SUSPENSIONS_CSV_NAME, result.suspensions_postponed)

    # ---- IVR: run 1 prepares the text, run 2 saves it ----
    def build_ivr_csv_text(self, result: ProcessingResult) -> str | None:
        """The finished IVR CSV as text, or None when nobody is postponed in IVR."""
        if len(result.ivr_postponed) == 0:
            return None
        return self.build_adx_csv_text(result.ivr_postponed, result.new_date)

    def save_staged_ivr_file(self, activity_date: date, ivr_csv_text: str | None, ivr_bans: int) -> list[Path]:
        """Run 2: saves the IVR CSV that run 1 prepared (in the dated folder and outside it)."""
        if ivr_csv_text is None:
            log.info("Nothing postponed for %s - no CSV file.", BusinessRules.IVR_CSV_NAME)
            return []
        return self._save_csv_text(activity_date, BusinessRules.IVR_CSV_NAME, ivr_csv_text, ivr_bans)

    def save_ivr_files(self, result: ProcessingResult) -> list[Path]:
        """Calculates and saves the IVR CSV in one go (only used by main.py --process)."""
        return self._save_one(result, BusinessRules.IVR_CSV_NAME, result.ivr_postponed)

    # ---- helpers ----
    def _save_one(self, result: ProcessingResult, file_name: str, postponed) -> list[Path]:
        """Saves one CSV in the dated folder and a copy outside it. Returns the saved files (empty = nothing postponed)."""
        if len(postponed) == 0:
            log.info("Nothing postponed for %s - no CSV file.", file_name)
            return []
        csv_text = self.build_adx_csv_text(postponed, result.new_date)
        return self._save_csv_text(result.activity_date, file_name, csv_text, len(postponed))

    def _save_csv_text(self, activity_date: date, file_name: str, csv_text: str, ban_count: int) -> list[Path]:
        folder = self.share_dir / f"{activity_date:%d.%m.%Y}_odlozuvanje suspenzii"
        folder.mkdir(parents=True, exist_ok=True)
        inside = folder / file_name
        outside = self.share_dir / BusinessRules.OUTSIDE_CSV_NAME
        with open(inside, "w", newline="", encoding="utf-8") as csv_file:
            csv_file.write(csv_text)
        shutil.copyfile(inside, outside)
        log.info("Saved: %s and %s (%d BANs)", inside, outside, ban_count)
        return [inside, outside]

    @staticmethod
    def build_adx_csv_text(postponed, new_date) -> str:
        """
        Format:  NS;BAN;BAN_STATUS;DEBTOR_STATUS;STEP;OLD_DATE;NEW_DATE
        Example: NS;529414748;O;C;S3;20240603;20240604
        No header, ';' as separator, CRLF line endings, dates as yyyymmdd.
        """
        lines = []
        for _, row in postponed.iterrows():
            lines.append(";".join([
                "NS",
                str(row["BAN"]).strip(),
                str(row["BAN_STATUS"]).strip(),
                str(row["DEBTOR_STATUS"]).strip(),
                str(row["COL_ACTIVITY_CODE"]).strip(),
                row["COL_NEXT_STEP_DATE"].strftime("%Y%m%d"),
                new_date.strftime("%Y%m%d"),
            ]))
        return "".join(line + "\r\n" for line in lines)
