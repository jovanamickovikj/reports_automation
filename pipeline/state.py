"""Remembers which report links were already downloaded (seen_reports.json)
and which downloaded report is still waiting for the IVR run (pending_ivr.json)."""
import json
from pathlib import Path


def _write_json(path: Path, data) -> None:
    # Write to a temp file first, then swap it in, so a crash never leaves a broken JSON file.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_seen(path: Path) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return set()


def save_seen(path: Path, seen: set[str]) -> None:
    _write_json(path, sorted(seen))


def save_pending(path: Path, report_path: Path) -> None:
    """main.py calls this after the suspensions are saved, so main_ivr.py knows which file to process."""
    _write_json(path, {"report": str(report_path)})


def load_pending(path: Path) -> Path | None:
    if not path.exists():
        return None
    return Path(json.loads(path.read_text(encoding="utf-8"))["report"])


def clear_pending(path: Path) -> None:
    path.unlink(missing_ok=True)
