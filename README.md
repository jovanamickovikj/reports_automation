# Reports automation

Downloads the newest "MAZ BAN Open Invoices" report from the portal, calculates the daily counts,
postpones suspensions / IVR above the limits, saves CSV files for ADX and sends an automatic mail.

The work is split into two runs, each started separately by Windows Task Scheduler:

1. `main.py` – downloads and processes the report, saves the **suspensions** files
2. `main_ivr.py` – saves the **IVR** files and sends the mail

## Flow

1. `pipeline/portal.py` – downloads the newest new report into `report/` (run 1)
2. `pipeline/processing.py` – cleans the data, builds the 4 reports (Churn, Suspensions S3, SMS, IVR), decides who is postponed (both runs)
3. `pipeline/saves.py` – writes the ADX CSV files, only if something is postponed (run 1: suspensions, run 2: IVR)
4. `pipeline/send_mail.py` – sends the mail through Outlook (run 2)

`pipeline/state.py` keeps two small state files:

- `seen_reports.json` – the reports that were already downloaded
- `pending_ivr.json` – the report that `main.py` processed and `main_ivr.py` still has to process

## Setup

```
python -m pip install -r requirements.txt
copy .env.example .env        (then fill in .env, including MAIL_TO)
```

## Run

Two entry points. Schedule both in Windows Task Scheduler, the second one after the first
(for example one hour later). The code itself does not wait or sleep between them.

```
python main.py          run 1: download + process, saves the SUSPENSIONS files
python main_ivr.py      run 2: saves the IVR files and sends the mail
```

`main.py` remembers the report in `pending_ivr.json`. `main_ivr.py` processes that same report,
and clears the file only after the IVR files are saved and the mail is sent. If nothing is pending,
`main_ivr.py` logs it and exits with a non-zero code, so Task Scheduler shows the run as failed.
If the mail fails, `pending_ivr.json` stays and `main_ivr.py` can be run again.

Other options:

```
python main.py --loop                         keep running, check every CHECK_INTERVAL_MIN minutes
python main.py --process "report\file.xlsx"   process + save both CSVs for a downloaded file, mail is only printed
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

Each CSV is saved twice in `<OUTPUT_DIR>` (default: Downloads):

- **inside** the folder `<activity date>_odlozuvanje suspenzii/`:
  `MCD_col_mass_chng_suspensions.csv` (run 1) and `MCD_col_mass_chng_ivr.csv` (run 2)
- **outside** the folder, at the same level: `MCD_col_mass_chng.csv`, the name ADX needs for `to_do`.
  Run 1 writes the suspensions file there, run 2 overwrites it with the IVR file.

A file is only saved if something is postponed. If a run has nothing postponed, an older
`MCD_col_mass_chng.csv` is left as it was.

Format: `NS;BAN;BAN_STATUS;DEBTOR_STATUS;STEP;OLD_DATE;NEW_DATE` (no header, `;`, CRLF).
