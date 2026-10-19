"""Step 3 of the pipeline: save the CSV files for the ADX job.

Both files (suspensions and IVR) are saved together in one dated folder:
  <output_dir>/<activity date>_odlozuvanje suspenzii/
"""
import logging
from pathlib import Path

from . import BusinessRules
from .ProcessingResult import ProcessingResult

log = logging.getLogger(__name__)


class AdxFileSaver:

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def save_suspensions_files(self, result: ProcessingResult) -> list[Path]:
        return self._save_one(result, BusinessRules.SUSPENSIONS_CSV_NAME, result.suspensions_postponed)

    def save_ivr_files(self, result: ProcessingResult) -> list[Path]:
        return self._save_one(result, BusinessRules.IVR_CSV_NAME, result.ivr_postponed)

    def _save_one(self, result: ProcessingResult, file_name: str, postponed) -> list[Path]:
        """Saves one CSV in the dated folder. Returns the saved files (empty = nothing postponed)."""
        if len(postponed) == 0:
            log.info("Nothing postponed for %s - no CSV file.", file_name)
            return []
        folder = self.output_dir / f"{result.activity_date:%d.%m.%Y}_odlozuvanje suspenzii"
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / file_name
        self.write_adx_csv(postponed, result.new_date, file_path)
        log.info("Saved: %s (%d BANs)", file_path, len(postponed))
        return [file_path]

    @staticmethod
    def write_adx_csv(postponed, new_date, file_path: Path) -> None:
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
        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            csv_file.write("".join(line + "\r\n" for line in lines))
