# Reports automation

Checks the internal report portal, downloads the **newest new report** into `report/`, and passes it to `process_report()` for calculations.

**Status:** downloading works. Processing (`pipeline/processing.py`) is still to be written.

## Setup (company Windows PC)

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # then set PORTAL_URL in .env
```

Install packages from the terminal, not through PyCharm's pop-up (older PyCharm versions fail on Python 3.12+).
Login uses your Windows account, so no password is needed.

## Run

| Command | What it does |
|---|---|
| `venv\Scripts\python.exe main.py` | Check once and download the newest new report. **Schedule this hourly.** |
| `venv\Scripts\python.exe main.py --loop` | Keep checking every `CHECK_INTERVAL_MIN` minutes (for testing) |
| `venv\Scripts\python.exe main.py --process report\file.xlsx` | Run only the processing step on one file |

**Hourly:** in Windows Task Scheduler, set the program to `venv\Scripts\pythonw.exe`, the argument to `main.py`, and *Start in* to the project folder. Choose "Run only when user is logged on".

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point. Finds new reports, downloads the newest, processes it |
| `pipeline/config.py` | Reads settings from `.env` |
| `pipeline/portal.py` | Talks to the portal: login, find links, download |
| `pipeline/state.py` | Remembers already-seen reports (`seen_reports.json`) |
| `pipeline/processing.py` | **Next step:** the calculations go here |

Never commit `.env`, `report/`, `seen_reports.json` or `*.log`. They are in `.gitignore`.

## Good to know

- If several new reports appear between checks, only the newest is downloaded. The others are marked as seen and skipped.
- If a download fails, nothing is marked as seen, so it retries on the next check.
- Problems? Check `pipeline.log`.
