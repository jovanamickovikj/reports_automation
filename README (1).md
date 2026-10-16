# Reports automation

Downloads the newest "MAZ BAN Open Invoices" report from the portal, calculates the daily counts,
postpones suspensions / IVR above the limits, saves CSV files for ADX and sends an automatic mail.

## Flow

1. `pipeline/portal.py` – downloads the newest new report into `report/`
2. `pipeline/processing.py` – cleans the data, builds the 4 reports (Churn, Suspensions S3, SMS, IVR), decides who is postponed
3. `pipeline/saves.py` – writes the ADX CSV files (only if something is postponed)
4. `pipeline/send_mail.py` – sends the mail through Outlook

`pipeline/state.py` remembers the reports that were already downloaded (`seen_reports.json`).

## Setup

```
python -m pip install -r requirements.txt
copy .env.example .env        (then fill in .env, including MAIL_TO)
```

## Run

```
python main.py                          check the portal once (schedule hourly in Task Scheduler)
python main.py --loop                   keep running, check every CHECK_INTERVAL_MIN minutes
python main.py --process "report\file.xlsx"   process + save CSV for a downloaded file, mail is only printed
python diagnose.py "report\file.xlsx"         print what is in the report for the activity date
```

Log: `pipeline.log`.

## Business rules (all in `pipeline/config.py`)

- **Dates:** activity date = next business day after the report date (from the report title);
  postponed customers move to the next business day after the activity date.
  Business days: weekends + `special_days_data/Special_days.xlsx` (keep it updated).
- **Limits (sum of MSISDNs):** Suspensions S3 = 3000, IVR (M) = 6000. Above the limit the oldest
  residential customers (by `Account_Act_Date`) are postponed.
- **Churn (C):** counted only, never postponed; in the mail only when the activity day is 15, 20, 25 or 30.
- **SMS (SM):** only the number of BANs, PRI vs BUS.
- Business types: BUS, VBB, VPN, EPN. KEY accounts are excluded. Duplicate BANs are removed.

## Output

CSV files go to `<OUTPUT_DIR>/<activity date>_odlozuvanje suspenzii/` (default: Downloads):
`MCD_col_mass_chng_suspensions.csv` and `MCD_col_mass_chng_ivr.csv`.
Format: `NS;BAN;BAN_STATUS;DEBTOR_STATUS;STEP;OLD_DATE;NEW_DATE` (no header, `;`, CRLF).
Rename the file to `MCD_col_mass_chng.csv` before putting it into `to_do`.
