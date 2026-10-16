"""Step 3 of the pipeline: save the CSV files for the ADX job."""
import logging
from pathlib import Path

from . import config
from .processing import ProcessingResult

log = logging.getLogger(__name__)


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


def save_csv_files(result: ProcessingResult, output_dir: Path) -> list[Path]:
    """
    Writes one CSV for suspensions and one for IVR into <output_dir>/<activity date>_odlozuvanje suspenzii/,
    only for the ones that have postponed customers. Returns the saved files (empty list = nothing postponed).
    """
    folder = output_dir / f"{result.activity_date:%d.%m.%Y}_odlozuvanje suspenzii"
    saved_files = []
    for file_name, postponed in [(config.SUSPENSIONS_CSV_NAME, result.suspensions_postponed),
                                 (config.IVR_CSV_NAME, result.ivr_postponed)]:
        if len(postponed) == 0:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        write_adx_csv(postponed, result.new_date, folder / file_name)
        print("tuka: ", output_dir)
        saved_files.append(folder / file_name)
        log.info("Saved: %s (%d BANs)", folder / file_name, len(postponed))
    if not saved_files:
        log.info("Nothing postponed - no CSV file.")
    return saved_files