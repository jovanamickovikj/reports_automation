"""Remembers which report links were already downloaded (seen_reports.json), what happened today
(daily_state.json) and what run 1 left ready for the IVR run (pending_ivr.json)."""
import json
import logging
from datetime import date
from pathlib import Path

from .PendingIvr import PendingIvr
from .Settings import Settings

log = logging.getLogger(__name__)


class StateController:

    def __init__(self, settings: Settings):
        self.seen_reports_file = settings.state_file
        self.pending_ivr_file = settings.pending_file
        self.daily_state_file = settings.daily_state_file

    # ---- reports that were already downloaded ----
    def load_seen_reports(self) -> set[str]:
        if self.seen_reports_file.exists():
            return set(self._read_json(self.seen_reports_file) or [])
        return set()

    def save_seen_reports(self, seen: set[str]) -> None:
        self._write_json(self.seen_reports_file, sorted(seen))

    # ---- what happened today: is the report processed, was the alarm / the pre-final mail sent ----
    DAILY_DEFAULTS = {"processed": False, "alarm_sent": False, "pre_final_sent": False}

    def load_daily_state(self, today: date) -> dict:
        """{'processed', 'alarm_sent', 'pre_final_sent'} for today (everything False on a new day)."""
        empty = dict(self.DAILY_DEFAULTS)
        if not self.daily_state_file.exists():
            return empty
        data = self._read_json(self.daily_state_file)
        if not isinstance(data, dict) or data.get("date") != today.isoformat():
            return empty
        return {key: bool(data.get(key)) for key in self.DAILY_DEFAULTS}

    def update_daily_state(self, today: date, **changes: bool) -> None:
        """Changes some of today's flags and keeps the others, e.g. update_daily_state(today, alarm_sent=True)."""
        state = self.load_daily_state(today)
        state.update(changes)
        self._write_json(self.daily_state_file, {"date": today.isoformat(), **state})

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
            "final_mail_sent": pending.final_mail_sent,
        })

    def load_pending_ivr(self) -> PendingIvr | None:
        """Returns None when nothing is pending (also for a pending file written by an older version)."""
        if not self.pending_ivr_file.exists():
            return None
        data = self._read_json(self.pending_ivr_file)
        if not isinstance(data, dict) or "mail_final_text" not in data:
            return None
        return PendingIvr(
            report_path=Path(data["report"]),
            activity_date=date.fromisoformat(data["activity_date"]),
            mail_final_text=data["mail_final_text"],
            ivr_csv_text=data["ivr_csv_text"],
            ivr_bans=data["ivr_bans"],
            bulk_msisdns=data["bulk_msisdns"],
            final_mail_sent=data.get("final_mail_sent", False),
        )

    def clear_pending_ivr(self) -> None:
        self.pending_ivr_file.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path):
        """Returns the content of a state file, or None if it is empty or damaged (then it is treated as missing)."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("State file %s is empty or damaged - ignoring it.", path)
            return None

    @staticmethod
    def _write_json(path: Path, data) -> None:
        # Write to a temp file first, then swap it in, so a crash never leaves a half-written file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
