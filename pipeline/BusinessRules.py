"""The business rules of the report. If a rule changes, change it only here."""

# ---------------------------------------------------------------
# Limits
# ---------------------------------------------------------------
SUSPENSIONS_LIMIT = 3500   # max MSISDNs per day for step S3: ALL business + residential customers (sum of BAN_Nr_msisdns)
IVR_LIMIT = 6000           # max MSISDNs per day for step M (IVR only, it is not added to SUSP)
BULK_MAIL_MSISDNS = 2500   # more suspension MSISDNs than this (before postponement) -> the "bulk" mail is sent
MAX_OVERDUE_TO_POSTPONE_BUSINESS = 6000   # business customers with a higher BAN overdue amount (den) are never postponed

# ---------------------------------------------------------------
# Codes in the report
# ---------------------------------------------------------------
# Codes in column COL_ACTIVITY_CODE
STEP_CHURN = "C"
STEP_SUSPENSION = "S3"
STEP_SMS = "SM"
STEP_IVR = "M"

# A customer is a business customer if ACCOUNT_TYPE is one of these OR COL_PATH_CODE is one of the path codes.
# Everything else is residential.
BUSINESS_ACCOUNT_TYPES = {"BUS", "VBB", "KEY"}
BUSINESS_PATH_CODES = {"BB1", "BB2", "BB3"}
KEY_ACCOUNT_TYPE = "KEY"
GROUP_BUSINESS = "BUS"
GROUP_RESIDENTIAL = "PRI"

# Suspensions: are KEY customers counted? They are business customers now, so yes (set True for the old rule).
SUSPENSIONS_EXCLUDE_KEY = False

STATUS_OPEN = "O"                   # BAN_STATUS
IVR_ACTIVE = "IVR"                  # FOLLOW_UP_TYPE - active customers
IVR_SUSPENDED = "SUSP"              # FOLLOW_UP_TYPE - suspended customers

# Columns that are loaded from the report (all other columns are ignored). The names are compared without
# upper/lower case and with spaces/dots/underscores treated the same ("BAN OVERDUE AMOUNT" = "BAN_OVERDUE_AMOUNT").
REQUIRED_COLUMNS = [
    "BAN", "BAN_STATUS", "DEBTOR_STATUS", "ACCOUNT_TYPE", "BAN_Nr_msisdns",
    "COL_NEXT_STEP_DATE", "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE", "Account_Act_Date",
]
PATH_CODE_COLUMN = "COL_PATH_CODE"          # optional: without it only ACCOUNT_TYPE decides who is business
OVERDUE_COLUMN = "BAN_OVERDUE_AMOUNT"       # optional: without it no business customer can be postponed
OPTIONAL_COLUMNS = [PATH_CODE_COLUMN, OVERDUE_COLUMN]

# ---------------------------------------------------------------
# The report files
# ---------------------------------------------------------------
# BI can also put the report by hand in the share folder; its name starts like this and continues with the date
SHARE_REPORT_PREFIX = "maz_ben_open_invoices_New_"
SHARE_REPORT_EXTENSIONS = (".xlsx", ".xls", ".csv")

# ---------------------------------------------------------------
# Names of the files that are written to the share folder
# ---------------------------------------------------------------
# ADX needs the name MCD_col_mass_chng.csv; whoever puts the file into to_do renames it
SUSPENSIONS_CSV_NAME = "MCD_col_mass_chng_suspensions.csv"
IVR_CSV_NAME = "MCD_col_mass_chng_ivr.csv"

# Copy that is saved next to the dated folder (same level). Suspensions saves it first, IVR overwrites it later.
OUTSIDE_CSV_NAME = "MCD_col_mass_chng.csv"

# The business customers whose suspension is 2 business days ahead (written by run 1)
BUSINESS_CUSTOMERS_FILE_NAME = "Business_korisnici.xlsx"

# ---------------------------------------------------------------
# Mails
# ---------------------------------------------------------------
ALARM_SUBJECT = "ALARM: Nepostaven ben_open file"
