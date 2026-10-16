"""Remembers which report links have already been downloaded (seen_reports.json)."""
import json
from pathlib import Path


def load_seen(path: Path) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return set()


def save_seen(path: Path, seen: set[str]) -> None:
    # Write to a temp file first, then swap it in, so a crash never leaves a broken JSON file.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")
    tmp.replace(path)
