"""Remembers which report links were already downloaded (seen_reports.json)
and which downloaded report is still waiting for the IVR run (pending_ivr.json)."""
import json
from pathlib import Path

from .Settings import Settings


class StateController:

    def __init__(self, settings: Settings):
        self.seen_reports_file = settings.state_file
        self.pending_report_file = settings.pending_file

    # ---- reports that were already downloaded ----
    def load_seen_reports(self) -> set[str]:
        if self.seen_reports_file.exists():
            return set(json.loads(self.seen_reports_file.read_text(encoding="utf-8")))
        return set()

    def save_seen_reports(self, seen: set[str]) -> None:
        self._write_json(self.seen_reports_file, sorted(seen))

    # ---- the report that main_ivr.py still has to process ----
    def save_pending_report(self, report_path: Path) -> None:
        """main.py calls this after the suspensions are saved, so main_ivr.py knows which file to process."""
        self._write_json(self.pending_report_file, {"report": str(report_path)})

    def load_pending_report(self) -> Path | None:
        if not self.pending_report_file.exists():
            return None
        return Path(json.loads(self.pending_report_file.read_text(encoding="utf-8"))["report"])

    def clear_pending_report(self) -> None:
        self.pending_report_file.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path: Path, data) -> None:
        # Write to a temp file first, then swap it in, so a crash never leaves a broken JSON file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
