"""Remembers which report links were already downloaded (seen_reports.json), what happened today
(daily_state.json) and what run 1 left ready for the IVR run (pending_ivr.json)."""
import json
from datetime import date
from pathlib import Path

from .PendingIvr import PendingIvr
from .Settings import Settings


class StateController:

    def __init__(self, settings: Settings):
        self.seen_reports_file = settings.state_file
        self.pending_ivr_file = settings.pending_file
        self.daily_state_file = settings.daily_state_file

    # ---- reports that were already downloaded ----
    def load_seen_reports(self) -> set[str]:
        if self.seen_reports_file.exists():
            return set(json.loads(self.seen_reports_file.read_text(encoding="utf-8")))
        return set()

    def save_seen_reports(self, seen: set[str]) -> None:
        self._write_json(self.seen_reports_file, sorted(seen))

    # ---- what happened today: is the report processed, was the alarm sent ----
    def load_daily_state(self, today: date) -> dict:
        """{'processed': bool, 'alarm_sent': bool} for today (everything False on a new day)."""
        empty = {"processed": False, "alarm_sent": False}
        if not self.daily_state_file.exists():
            return empty
        data = json.loads(self.daily_state_file.read_text(encoding="utf-8"))
        if data.get("date") != today.isoformat():
            return empty
        return {"processed": bool(data.get("processed")), "alarm_sent": bool(data.get("alarm_sent"))}

    def save_daily_state(self, today: date, processed: bool, alarm_sent: bool) -> None:
        self._write_json(self.daily_state_file, {"date": today.isoformat(), "processed": processed,
                                                 "alarm_sent": alarm_sent})

    # ---- what main.py leaves ready for main_ivr.py ----
    def save_pending_ivr(self, pending: PendingIvr) -> None:
        """main.py calls this after the suspensions are saved. The IVR file and the mail are already finished."""
        self._write_json(self.pending_ivr_file, {
            "report": str(pending.report_path),
            "activity_date": pending.activity_date.isoformat(),
            "mail_final_text": pending.mail_final_text,
            "ivr_csv_text": pending.ivr_csv_text,
            "ivr_bans": pending.ivr_bans,
            "bulk_msisdns": pending.bulk_msisdns,
        })

    def load_pending_ivr(self) -> PendingIvr | None:
        """Returns None when nothing is pending (also for a pending file written by an older version)."""
        if not self.pending_ivr_file.exists():
            return None
        data = json.loads(self.pending_ivr_file.read_text(encoding="utf-8"))
        if "mail_final_text" not in data:
            return None
        return PendingIvr(
            report_path=Path(data["report"]),
            activity_date=date.fromisoformat(data["activity_date"]),
            mail_final_text=data["mail_final_text"],
            ivr_csv_text=data["ivr_csv_text"],
            ivr_bans=data["ivr_bans"],
            bulk_msisdns=data["bulk_msisdns"],
        )

    def clear_pending_ivr(self) -> None:
        self.pending_ivr_file.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path: Path, data) -> None:
        # Write to a temp file first, then swap it in, so a crash never leaves a half-written file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
