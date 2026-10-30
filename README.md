# Reports automation

Every business day the program finds TODAY'S "MAZ BAN Open Invoices" report, counts the activities for the next
business day, postpones suspensions / IVR above the limits, saves the CSV files for ADX in the share folder and
sends the automatic mails.

Two runs, each started separately by Windows Task Scheduler:

1. `main.py` – finds and processes the report, sends mail 1 (pre-final), saves `Business_korisnici.xlsx` and the **suspensions** CSV
2. `main_ivr.py` – saves the **IVR** CSV, sends mail 2 (final) and, if needed, mail 3 (bulk)

## Flow

1. **Find the report** (`ReportFinder.py`): only a report with today's date counts (Saturday/Sunday reports are ignored on Monday).
   Portal first (`ReportPortal.py`); if it is not there and it is already `ALARM_TIME` (13:30), the share folder is
   checked too (`ShareReportFinder.py`, files `maz_ben_open_invoices_New_<date>`). If it is not found anywhere, the
   alarm mail `ALARM: Nepostaven ben_open file` is sent once per day.
2. **Process** (`ReportProcessor.py`): Churn, Suspensions S3, SMS, IVR; duplicate BANs removed.
3. **Mail 1** `Collection activities dd.mm.yyyy pre-final` – all counted activities, without the postponements.
4. **Business_korisnici.xlsx** – the business customers with S3 two business days after the report date.
5. **CSV files** for the postponed customers → share folder (`AdxFileSaver.py`).
6. **Mail 2** `Collection activities dd.mm.yyyy` – the numbers after the postponements.
7. **Mail 3** `Sledni bulk-ovi na suspenzii ...` – only if there were more than 2500 suspension MSISDNs (before the postponement).

## Rules (all in `pipeline/BusinessRules.py`)

- Business customer = ACCOUNT_TYPE `BUS`, `VBB`, `KEY` **or** COL_PATH_CODE `BB1`, `BB2`, `BB3`. Everyone else is residential (PRI).
- Suspensions limit **3500** MSISDN for business + residential together.
- Above the limit: first PRI customers are postponed (oldest `Account_Act_Date` first). If that is not enough,
  BUS customers are postponed the same way, but only those with `BAN overdue amount` of at most 6000.
- IVR limit 6000 (IVR active only, PRI only), postponed the same way.
- Activity date = next business day after the report date; postponed customers go to the business day after that.

## Setup

```
python -m pip install -r requirements.txt
copy .env.example .env        (then fill in .env: PORTAL_URL, SHARE_DIR and the mail addresses)
```

## Run

```
python main.py          run 1 (schedule every 30-60 minutes; it does nothing once today's report is processed)
python main_ivr.py      run 2 (schedule 30-60 minutes after the report is usually processed)
python main.py --process "report\file.xlsx"   process + save everything for a file, the mails are only printed
```

State files in the project folder: `seen_reports.json` (portal links that are not from today),
`daily_state.json` (today processed? alarm sent?), `pending_ivr.json` (what run 2 still has to send).
If run 2 fails, `pending_ivr.json` stays and `main_ivr.py` can be run again.

## Code structure

```
main.py / main_ivr.py     entry points
BusinessDaysCalculator.py business days (weekends + Special_days.xlsx)
pipeline/
  SuspensionsRun.py       run 1      IvrRun.py          run 2
  ReportFinder.py         today's report: portal, share, alarm
  ReportPortal.py         portal: list, newest, download
  ShareReportFinder.py    share folder lookup + dates in names
  ReportLoader.py         reads the report into a clean table
  ReportProcessor.py      the 4 reports and the postponement
  MailTextBuilder.py      text of mails 1 and 2     MailSender.py   all Outlook mails
  AdxFileSaver.py         CSV files                 BusinessCustomersFile.py   Business_korisnici.xlsx
  StateController.py      the three json state files
  Settings.py / BusinessRules.py / LogSetup.py / ProcessingResult.py / PendingIvr.py
```
