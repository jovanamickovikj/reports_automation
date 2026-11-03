"""Writes Business_korisnici.xlsx: the business customers whose suspension is 2 business days ahead (all report columns)."""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import BusinessRules

log = logging.getLogger(__name__)

# Columns the program adds for its own calculations; they are not part of the report
HELPER_COLUMNS = ["STEP_DATE", "IS_KEY", "GROUP"]


class BusinessCustomersFile:

    def __init__(self, share_dir: Path):
        self.share_dir = share_dir

    def save(self, business_customers: pd.DataFrame) -> Path:
        """Overwrites the file in the share folder (the file always shows the newest run)."""
        self.share_dir.mkdir(parents=True, exist_ok=True)
        path = self.share_dir / BusinessRules.BUSINESS_CUSTOMERS_FILE_NAME
        # ALL columns of the report, in the original order
        table = business_customers.drop(columns=HELPER_COLUMNS).copy()
        table["BAN_Nr_msisdns"] = pd.to_numeric(table["BAN_Nr_msisdns"], errors="coerce")
        for column in ("COL_NEXT_STEP_DATE", "Account_Act_Date"):
            table[column] = table[column].dt.strftime("%d.%m.%Y")
        try:
            table.to_excel(path, index=False, sheet_name="Business_korisnici")
        except PermissionError:   # most likely the file is open in Excel
            path = path.with_name(f"{path.stem}_{datetime.now():%H%M%S}{path.suffix}")
            log.warning("%s is open in Excel - saving to %s instead. Close Excel to overwrite the original next time.",
                        BusinessRules.BUSINESS_CUSTOMERS_FILE_NAME, path.name)
            table.to_excel(path, index=False, sheet_name="Business_korisnici")
        log.info("Saved: %s (%d BANs)", path, len(table))
        return path
