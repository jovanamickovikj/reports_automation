"""Offline test: synthetic report, fake Outlook, temp share folder.   python tests/test_pipeline.py"""
import sys, types, os, tempfile, shutil, json
from datetime import date, datetime, time as dtime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
fake = types.ModuleType("win32com"); fake.client = types.ModuleType("win32com.client")
sent = []
class FakeMail:
    def Send(self): sent.append((self.To, getattr(self, "CC", ""), self.Subject, self.Body))
class FakeOutlook:
    def CreateItem(self, _): return FakeMail()
fake.client.Dispatch = lambda _: FakeOutlook()
sys.modules["win32com"], sys.modules["win32com.client"] = fake, fake.client

import pandas as pd
from pipeline.Settings import Settings
from pipeline.SuspensionsRun import SuspensionsRun
from pipeline.IvrRun import IvrRun
from pipeline.ReportPortal import ReportPortal

TODAY = date(2026, 10, 30)        # Friday -> activity Monday 02.11, new date Tuesday 03.11
ACTIVITY, NEW = "2026-11-02", "2026-11-03"
COLS = ["BAN", "BAN_STATUS", "DEBTOR_STATUS", "ACCOUNT_TYPE", "COL PATH CODE", "BAN_Nr_msisdns", "COL_NEXT_STEP_DATE",
        "COL_ACTIVITY_CODE", "FOLLOW_UP_TYPE", "Account_Act_Date", "ban overdue amount"]

def make_report(path, pri_msisdn, bus_msisdn, title_date="2026-10-30"):
    rows, n = [], 100
    def add(typ, path_code, msisdn, step, date_, overdue, follow="X", act="2020-01-01"):
        nonlocal n; n += 1
        rows.append([str(n), "O", "C", typ, path_code, str(msisdn), date_, step, follow, act, str(overdue)])
    for i in range(pri_msisdn // 2):
        add("PRI", "", 2, "S3", ACTIVITY, 100, act=f"2019-{1 + i % 12:02d}-{1 + i % 28:02d}")
    for i in range(bus_msisdn // 2):   # every 3rd: business only by path code; every 4th: overdue above 6000
        add("XXX" if i % 3 == 0 else "BUS", "BB1" if i % 3 == 0 else "", 2, "S3", ACTIVITY,
            9000 if i % 4 == 0 else 500, act=f"2018-{1 + i % 12:02d}-{1 + i % 28:02d}")
    add("BUS", "", 4, "S3", NEW, 100)                 # business, suspension on new_date -> Business_korisnici
    add("PRI", "", 3, "M", ACTIVITY, 0, follow="IVR"); add("PRI", "", 2, "M", ACTIVITY, 0, follow="SUSP")
    add("PRI", "", 1, "SM", ACTIVITY, 0); add("BUS", "", 1, "C", ACTIVITY, 0)
    df = pd.DataFrame([[f"MAZ BAN Open Invoices - {title_date}"] + [None] * 10, [None] * 11, COLS] + rows)
    df.to_excel(path, header=False, index=False)

def settings(tmp):
    return Settings(portal_url="http://x", link_selector="a", auth_mode="none", download_dir=tmp / "report",
        share_dir=tmp / "share", alarm_time=dtime(13, 30), mail_alarm_to="alarm@x", mail_pre_final_to="vip@x",
        mail_final_to="final@x", mail_final_cc="cc@x", mail_bulk_to="bulk@x", mail_bulk_cc="vipcc@x",
        check_interval_min=60, state_file=tmp / "seen.json", daily_state_file=tmp / "daily.json",
        pending_file=tmp / "pending.json", log_file=tmp / "p.log")

def run_case(name, pri, bus):
    tmp = Path(tempfile.mkdtemp()); s = settings(tmp); sent.clear()
    rep = tmp / "src.xlsx"; make_report(rep, pri, bus)
    run = SuspensionsRun(s); run.process_downloaded_report(rep)
    IvrRun(s).run()
    print(f"\n#### {name}: PRI {pri}, BUS {bus}")
    for to, cc, subj, body in sent: print(f"-- To {to} | Cc {cc} | {subj}\n{body}")
    f = s.share_dir / "02.11.2026_odlozuvanje suspenzii" / "MCD_col_mass_chng_suspensions.csv"
    lines = f.read_text().splitlines() if f.exists() else []; print("CSV lines:", len(lines), "| first:", lines[0] if lines else None)
    xl = pd.read_excel(s.share_dir / "Business_korisnici.xlsx", dtype=str); print("Business_korisnici rows:", len(xl), list(xl.columns))
    return tmp, s, sent[:], lines

# 1) PRI is enough: total 4000 -> postpone 500 PRI msisdn
tmp, s, mails, lines = run_case("PRI postponed", 2500, 1500)
assert [m[2] for m in mails] == ["Collection activities 02.11.2026 pre-final", "Collection activities 02.11.2026",
    "Sledni bulk-ovi na suspenzii (nokjta pomegju 01.11.2026 i 02.11.2026)"], [m[2] for m in mails]
assert len(lines) == 250 and "MSISDN 3500" in mails[1][3] and "MSISDN 4000" in mails[0][3]
# 2) BUS alone above limit: BUS 3800 + PRI 200 -> all PRI + eligible BUS (overdue<=6000) postponed
tmp, s, mails, lines = run_case("BUS postponed", 200, 3800)
body = mails[1][3]; print("final line:", [l for l in body.splitlines() if "suspenzija" in l])
ids = [l.split(";")[1] for l in lines]; assert len(lines) > 100
# 3) small day: no postponement, no bulk mail
tmp, s, mails, lines = run_case("small", 1000, 500)
assert len(mails) == 2 and lines == []

# 4) lookup: alarm + share
tmp = Path(tempfile.mkdtemp()); s = settings(tmp); sent.clear(); (s.share_dir).mkdir()
from pipeline.ReportFinder import ReportFinder
from pipeline.StateController import StateController
from pipeline.MailSender import MailSender
sc = StateController(s); finder = ReportFinder(s, sc, MailSender(s))
with mock.patch.object(ReportPortal, "find_reports", return_value={}):
    assert finder.find_todays_report(datetime(2026, 10, 30, 12, 0)) is None and not sent
    assert finder.find_todays_report(datetime(2026, 10, 30, 13, 40)) is None and len(sent) == 1 and sent[0][2] == "ALARM: Nepostaven ben_open file"
    assert finder.find_todays_report(datetime(2026, 10, 30, 14, 0)) is None and len(sent) == 1   # alarm only once
    f = s.share_dir / "maz_ben_open_invoices_New_20261030.xlsx"; make_report(f, 100, 100)
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime - 600))
    (s.share_dir / "~$maz_ben_open_invoices_New_20261030.xlsx").write_text("x")
    assert finder.find_todays_report(datetime(2026, 10, 30, 12, 0)) is None            # before 13:30 share is not used
    got = finder.find_todays_report(datetime(2026, 10, 30, 14, 5)); assert got and got.exists(), got
    assert finder.find_todays_report(datetime(2026, 11, 1, 15, 0)) is None             # Sunday: nothing
# portal: stale report (Saturday) ignored, today's downloaded
sent.clear(); sc.save_daily_state(TODAY, False, False)
with mock.patch.object(ReportPortal, "find_reports", return_value={"http://p/f?fileid=5": "ben_open_2026-10-24"}):
    assert finder.find_todays_report(datetime(2026, 10, 30, 9, 0)) is None and not sent
    assert "http://p/f?fileid=5" in sc.load_seen_reports()
src = tmp / "dl.xlsx"; make_report(src, 100, 100)
with mock.patch.object(ReportPortal, "find_reports", return_value={"http://p/f?fileid=9": "ben_open 30.10.2026"}), \
     mock.patch.object(ReportPortal, "download_report", return_value=src):
    assert finder.find_todays_report(datetime(2026, 10, 30, 9, 0)) == src
print("\nALL OK")
