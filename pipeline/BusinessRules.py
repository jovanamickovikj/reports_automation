"""The business rules of the report. If a rule changes, change it only here."""

# ---------------------------------------------------------------
# Limits
# ---------------------------------------------------------------
SUSPENSIONS_LIMIT = 3000   # max MSISDNs per day for step S3 (sum of BAN_Nr_msisdns, not the BAN count)
IVR_LIMIT = 6000         # max MSISDNs per day for step M (IVR only, it is not added to SUSP)

# ---------------------------------------------------------------
# Codes in the report
# ---------------------------------------------------------------
# Codes in column COL_ACTIVITY_CODE
STEP_CHURN = "C"
STEP_SUSPENSION = "S3"
STEP_SMS = "SM"
STEP_IVR = "M"

# Account types in column ACCOUNT_TYPE: everything that is not business and not KEY is residential
BUSINESS_ACCOUNT_TYPES = {"BUS", "VBB", "VPN", "EPN"}
KEY_ACCOUNT_TYPE = "KEY"            # KEY accounts are left out of the calculations
GROUP_BUSINESS = "BUS"
GROUP_RESIDENTIAL = "PRI"

STATUS_OPEN = "O"                   # BAN_STATUS
IVR_ACTIVE = "IVR"                  # FOLLOW_UP_TYPE - active customers
IVR_SUSPENDED = "SUSP"              # FOLLOW_UP_TYPE - suspended customers

# Churn goes into the mail only when the day of the month of the activity date is one of these
CHURN_MAIL_DAYS = {15, 20, 25, 30}

# Columns that are loaded from the report (all other columns are ignored)
REQUIRED_COLUMNS = [
    "BAN", "BAN_STATUS", "DEBTOR_STATUS", "ACCOUNT_TYPE", "BAN_Nr_msisdns",
    "COL_NEXT_STEP_DATE", "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE", "Account_Act_Date",
]

# ---------------------------------------------------------------
# Names of the files for ADX
# ---------------------------------------------------------------
# ADX needs the name MCD_col_mass_chng.csv; whoever puts the file into to_do renames it
SUSPENSIONS_CSV_NAME = "MCD_col_mass_chng_suspensions.csv"
IVR_CSV_NAME = "MCD_col_mass_chng_ivr.csv"

# Copy that is saved next to the dated folder (same level). Suspensions saves it first, IVR overwrites it later.
OUTSIDE_CSV_NAME = "MCD_col_mass_chng.csv"
