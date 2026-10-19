# Reports automation

Downloads the newest "MAZ BAN Open Invoices" report from the portal, calculates the daily counts,
postpones suspensions / IVR above the limits, saves the CSV files for ADX and prepares an automatic mail.

This is the **single-run version**: one `main.py` does everything in one go. It saves both CSV files
(suspensions and IVR) and opens the mail in Outlook as a **draft**. The mail is **not sent**: someone
checks it and presses Send.

## Flow

1. `pipeline/ReportPortal.py` – connects to the portal and downloads the newest new report into `report/`
2. `pipeline/ReportProcessor.py` – builds the 4 reports (Churn, Suspensions S3, SMS, IVR) and decides who is postponed.
   It uses `ReportLoader.py` to read the report into a clean table and `MailTextBuilder.py` to write the mail text.
3. `pipeline/AdxFileSaver.py` – writes both ADX CSV files (suspensions and IVR), only if something is postponed
4. `pipeline/MailSender.py` – opens the mail in Outlook as a draft (it is not sent)

`pipeline/StateController.py` keeps one small state file, `seen_reports.json`: the reports that were already downloaded.

## Code structure

Every file holds one class and is named after it. The class methods are named after what they do
(`find_reports`, `download_report`, `save_ivr_files`, ...), and `ReportRun` reads like a checklist.

```
main.py                    entry point (Task Scheduler)
BusinessDaysCalculator.py  adds business days (weekends + Special_days.xlsx holidays)
pipeline/
  ReportRun.py             the run: check the portal, download, process, save both files, open the draft mail
  ReportPortal.py          portal: list the reports, pick the newest, download it
  ReportLoader.py          reads a report file into a clean table (5 small steps)
  ReportProcessor.py       the 4 reports and the postponement of customers above the limits
  MailTextBuilder.py       the text of the mail
  ProcessingResult.py      what processing hands over (dates, mail text, postponed customers)
  AdxFileSaver.py          writes the CSV files for ADX
  MailSender.py            opens the mail in Outlook as a draft
  StateController.py       seen_reports.json
  Settings.py              settings from the .env file
  BusinessRules.py         limits, codes and file names (change a rule only here)
  LogSetup.py              log file and screen output
```

## Setup

```
python -m pip install -r requirements.txt
copy .env.example .env        (then fill in .env, including MAIL_TO)
```

## Run

```
python main.py                                check the portal once (schedule it in Windows Task Scheduler)
python main.py --loop                         keep running, check every CHECK_INTERVAL_MIN minutes
python main.py --process "report\file.xlsx"   process + save both CSVs for a downloaded file, the mail is only printed
```

When a new report is found, `main.py` saves the CSV files and the mail window opens in Outlook.
Check the mail and press Send. Opening the window needs Outlook and a logged-in Windows session
(a Task Scheduler task must be set to "Run only when user is logged on").

Log: `pipeline.log`.

## Business rules (all in `pipeline/BusinessRules.py`)

- **Dates:** activity date = next business day after the report date (from the report title);
  postponed customers move to the next business day after the activity date.
  Business days: weekends + `special_days_data/Special_days.xlsx` (keep it updated).
- **Limits (sum of MSISDNs):** Suspensions S3 = 3000, IVR (M) = 6000. Above the limit the oldest
  residential customers (by `Account_Act_Date`) are postponed.
- **Churn (C):** every BAN with code C on the activity date, any status, KEY included. Counted only,
  never postponed; in the mail only when there is at least one churn BAN for the activity date.
- **SMS (SM):** only the number of BANs, PRI vs BUS.
- Business types: BUS, VBB, VPN, EPN. KEY accounts are excluded (except in Churn). Duplicate BANs are removed.

## Output

Both CSV files are saved together in `<OUTPUT_DIR>` (default: Downloads), in the folder
`<activity date>_odlozuvanje suspenzii/`:

- `MCD_col_mass_chng_suspensions.csv`
- `MCD_col_mass_chng_ivr.csv`

A file is only saved if something is postponed. Rename the file to `MCD_col_mass_chng.csv` before putting it into `to_do`.

Format: `NS;BAN;BAN_STATUS;DEBTOR_STATUS;STEP;OLD_DATE;NEW_DATE` (no header, `;`, CRLF).
