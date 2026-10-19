"""Remembers which report links were already downloaded (seen_reports.json)."""
import json
from pathlib import Path

from .Settings import Settings


class StateController:

    def __init__(self, settings: Settings):
        self.seen_reports_file = settings.state_file

    def load_seen_reports(self) -> set[str]:
        if self.seen_reports_file.exists():
            return set(json.loads(self.seen_reports_file.read_text(encoding="utf-8")))
        return set()

    def save_seen_reports(self, seen: set[str]) -> None:
        self._write_json(self.seen_reports_file, sorted(seen))

    @staticmethod
    def _write_json(path: Path, data) -> None:
        # Write to a temp file first, then swap it in, so a crash never leaves a half-written file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
