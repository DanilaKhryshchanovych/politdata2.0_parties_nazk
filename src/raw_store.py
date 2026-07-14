"""
Disk layer for the raw API cache and download state.

Design goal (from the plan): decouple download from transform. Every report is
written to `data/raw/<report_id>.json` exactly as the API returned it, so the
Phase 2 transforms can be re-run offline any number of times without touching
the network.

Freshness is tracked per report by a *fingerprint* — not a bare id — because a
report can be re-signed or change status after we first saw it. The old pipeline
keyed only on report_id and therefore could never notice a re-signed report;
here the fingerprint is (signed_date, special_status), both available from the
cheap report-list call, so we re-fetch the detail only when it actually changed.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402


def _ensure_dirs() -> None:
    settings.RAW_DIR.mkdir(parents=True, exist_ok=True)
    settings.STATE_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    tmp.replace(path)  # atomic: never leave a half-written cache file


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# --- party directory -----------------------------------------------------
def save_parties(parties: list[dict]) -> None:
    _ensure_dirs()
    _write_json(settings.PARTIES_FILE, parties)


def load_parties() -> list[dict]:
    if not settings.PARTIES_FILE.exists():
        return []
    return _read_json(settings.PARTIES_FILE)


# --- raw reports ---------------------------------------------------------
def raw_report_path(report_id: str) -> Path:
    return settings.RAW_DIR / f"{report_id}.json"


def save_raw_report(report_id: str, detail: dict) -> None:
    _ensure_dirs()
    _write_json(raw_report_path(report_id), detail)


def load_raw_report(report_id: str) -> dict:
    return _read_json(raw_report_path(report_id))


def iter_raw_reports() -> Iterator[tuple[str, dict]]:
    """(report_id, detail) for every cached report — the input to Phase 2."""
    for path in sorted(settings.RAW_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue  # _parties.json and friends are not reports
        yield path.stem, _read_json(path)


# --- download state ------------------------------------------------------
def load_state() -> dict[str, dict]:
    if not settings.STATE_FILE.exists():
        return {}
    return _read_json(settings.STATE_FILE)


def save_state(state: dict[str, dict]) -> None:
    _ensure_dirs()
    _write_json(settings.STATE_FILE, state)


def fingerprint(report_meta: dict) -> tuple:
    """The identity that decides whether a cached report is still current."""
    return (report_meta.get("signed_date"), report_meta.get("special_status"))


def needs_download(state: dict[str, dict], report_meta: dict, full: bool) -> bool:
    report_id = report_meta["id"]
    if full:
        return True
    if report_id not in state:
        return True
    if not raw_report_path(report_id).exists():
        return True  # state says done but the cache file is gone
    prev = state[report_id]
    return (prev.get("signed_date"), prev.get("special_status")) != fingerprint(report_meta)


def mark_downloaded(state: dict[str, dict], report_meta: dict) -> None:
    state[report_meta["id"]] = {
        "signed_date": report_meta.get("signed_date"),
        "special_status": report_meta.get("special_status"),
        "party_id": report_meta.get("party_id"),
        "is_party_office": report_meta.get("is_party_office"),
        "year": report_meta.get("year"),
        "quarter": report_meta.get("quarter"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --- error ids -----------------------------------------------------------
def reset_errors() -> None:
    _ensure_dirs()
    settings.ERROR_IDS_FILE.write_text("", encoding="utf-8")


def record_error(report_id: str, reason: str = "") -> None:
    _ensure_dirs()
    line = report_id if not reason else f"{report_id}\t{reason}"
    with settings.ERROR_IDS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_error_ids() -> list[str]:
    if not settings.ERROR_IDS_FILE.exists():
        return []
    ids = []
    for line in settings.ERROR_IDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.append(line.split("\t", 1)[0])
    return ids
