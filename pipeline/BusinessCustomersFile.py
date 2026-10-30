"""Writes Business_korisnici.xlsx: the business customers whose suspension is 2 business days ahead."""
import logging
from pathlib import Path

import pandas as pd

from . import BusinessRules

log = logging.getLogger(__name__)

COLUMNS = ["BAN", "BAN_STATUS", "DEBTOR_STATUS", "ACCOUNT_TYPE", BusinessRules.PATH_CODE_COLUMN,
           "BAN_Nr_msisdns", BusinessRules.OVERDUE_COLUMN, "COL_NEXT_STEP_DATE", "Account_Act_Date"]


class BusinessCustomersFile:

    def __init__(self, share_dir: Path):
        self.share_dir = share_dir

    def save(self, business_customers: pd.DataFrame) -> Path:
        """Overwrites the file in the share folder (the file always shows the newest run)."""
        self.share_dir.mkdir(parents=True, exist_ok=True)
        path = self.share_dir / BusinessRules.BUSINESS_CUSTOMERS_FILE_NAME
        table = business_customers[COLUMNS].copy()
        table["BAN_Nr_msisdns"] = pd.to_numeric(table["BAN_Nr_msisdns"], errors="coerce")
        for column in ("COL_NEXT_STEP_DATE", "Account_Act_Date"):
            table[column] = table[column].dt.strftime("%d.%m.%Y")
        table.to_excel(path, index=False, sheet_name="Business_korisnici")
        log.info("Saved: %s (%d BANs)", path, len(table))
        return path
