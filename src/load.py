"""
Reshape layer: raw JSON cache -> pandas frames the table builders consume.

Replaces the old in-memory `r_df`. Two products:
  * report_meta_frame() — one row per report with every metadata/enrichment column
    the tables need (the table-1 base, clean-named), resolved from the report +
    the party card (addresses, party_main via card.parent).
  * explode_section() — a section's nested rows flattened to one row each, with the
    report metadata attached (join on report_id).

All party names/codes/addresses come from data/raw/_party_cards.json because the
directory listing and the report itself omit office addresses (see api_v2_findings §6.9).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterator

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402

CARDS_FILE = settings.RAW_DIR / "_party_cards.json"
PARTIES_FILE = settings.RAW_DIR / "_parties.json"

# register_address / actual_address subfield -> clean suffix
_ADDR_MAP = {
    "country": "country", "post_index": "index", "region": "region",
    "district": "district", "city": "city", "street": "street",
    "building": "building", "building_part_num": "korpus", "apartments": "apartment",
}


# --- caches ---------------------------------------------------------------
def load_cards() -> dict[str, dict]:
    return json.loads(CARDS_FILE.read_text(encoding="utf-8")) if CARDS_FILE.exists() else {}


def load_parties() -> list[dict]:
    return json.loads(PARTIES_FILE.read_text(encoding="utf-8")) if PARTIES_FILE.exists() else []


def directory_codes() -> tuple[set[str], set[str]]:
    """(central party codes, office codes) — for check_edrpou_for_party."""
    parties = load_parties()
    central, office = set(), set()
    for p in parties:
        if p.get("code"):
            central.add(str(p["code"]))
        for o in p.get("regional_offices") or []:
            if o.get("code"):
                office.add(str(o["code"]))
    return central, office


# --- report metadata ------------------------------------------------------
def _quarter_to_period(q):
    if q in (5, "5"):
        return "рік"
    if q in (None, "", 0):
        return None
    return f"{q} квартал"


def _address_cols(addr: dict | None, prefix: str) -> dict:
    addr = addr or {}
    out = {}
    for src, suf in _ADDR_MAP.items():
        val = addr.get(src)
        out[f"{prefix}_{suf}"] = val if val not in ("",) else None
    return out


def _meta_for_report(report: dict, cards: dict[str, dict]) -> dict:
    pid = report.get("party_id")
    card = cards.get(pid) or {}
    is_office = bool(report.get("is_party_office"))

    # party_main: office -> card.parent; central -> itself
    parent = card.get("parent")
    if is_office and isinstance(parent, dict) and parent:
        main_name, main_code = parent.get("name"), parent.get("code")
    else:
        main_name, main_code = card.get("name"), card.get("code")

    head = report.get("head_info") or {}
    row = {
        "report_id": report.get("id"),
        "party_id": pid,
        "officeType": "Регіональний офіс" if is_office else "Центральний офіс",
        "report_submition_date": report.get("signed_date"),
        "documentId": report.get("document_id"),
        "report_type": "Основний" if report.get("report_type") == "main" else report.get("report_type"),
        "report_period": _quarter_to_period(report.get("quarter")),
        "report_year": report.get("year"),
        "legal_entity_name": card.get("name"),
        "legal_entity_edrpou": card.get("code"),
        "legal_entity_head_last_name": head.get("surname"),
        "legal_entity_head_first_name": head.get("name"),
        "legal_entity_head_middle_name": head.get("patronymic"),
        "number_of_employees_contract": report.get("employees_by_employment_contract"),
        "number_of_employees_civil_agreement": report.get("employees_by_civil_contract"),
        "number_of_employees_volunteers": None,  # no v2 source (findings §6.7)
        "is_actual_address": card.get("actual_address_same_register"),
        "party_main_name": main_name,
        "party_main_EDRPOU": main_code,
    }
    row.update(_address_cols(card.get("register_address"), "legal_entity"))
    row.update(_address_cols(card.get("actual_address"), "actual_address"))
    return row


def iter_reports(limit: int | None = None) -> Iterator[dict]:
    n = 0
    for entry in os.scandir(settings.RAW_DIR):
        if not entry.name.endswith(".json") or entry.name.startswith("_"):
            continue
        with open(entry.path, encoding="utf-8") as f:
            yield json.load(f)
        n += 1
        if limit and n >= limit:
            return


def report_meta_frame(cards: dict[str, dict] | None = None, limit: int | None = None) -> pd.DataFrame:
    cards = load_cards() if cards is None else cards
    rows = [_meta_for_report(r, cards) for r in iter_reports(limit)]
    return pd.DataFrame(rows)


# --- section explosion ----------------------------------------------------
def get_section(report: dict, path: str) -> list[dict]:
    """Navigate a dotted path (e.g. 'payment_info.outgoing.outgoing_expenses') to a list."""
    node = report
    for key in path.split("."):
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    return node if isinstance(node, list) else []


def _stringify(v):
    return None if v is None else str(v)


STAGING_DIR = settings.DATA_DIR / "staging"


def _safe(path: str) -> str:
    return path.replace(".", "_").replace("/", "_")


def _section_file(path: str) -> Path:
    return STAGING_DIR / f"{_safe(path)}.jsonl"


def staging_exists() -> bool:
    return (STAGING_DIR / "meta.pkl").exists()


def stage_to_disk(section_paths: list[str], cards: dict[str, dict] | None = None,
                  limit: int | None = None) -> pd.DataFrame:
    """
    Single pass over the raw cache (each report parsed once). Section rows are streamed
    to one JSONL file per section (O(1) memory — the whole cache never lives in RAM at
    once), and the small report-meta frame is returned and cached as parquet. Re-runs
    can skip this slow, IO-bound read and rebuild tables straight from the staged files.
    """
    cards = load_cards() if cards is None else cards
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    files = {p: _section_file(p).open("w", encoding="utf-8") for p in section_paths}
    meta_rows: list[dict] = []
    try:
        for report in iter_reports(limit):
            meta_rows.append(_meta_for_report(report, cards))
            rid = report.get("id")
            for path in section_paths:
                fh = files[path]
                for row in get_section(report, path):
                    rec = {k: _stringify(v) for k, v in row.items()}
                    rec["report_id"] = rid
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        for fh in files.values():
            fh.close()
    meta = pd.DataFrame(meta_rows)
    meta.to_pickle(STAGING_DIR / "meta.pkl")
    return meta


def load_staged_meta() -> pd.DataFrame:
    return pd.read_pickle(STAGING_DIR / "meta.pkl")


def read_staged_section(path: str) -> pd.DataFrame:
    f = _section_file(path)
    if not f.exists() or f.stat().st_size == 0:
        return pd.DataFrame()
    # DataFrame-from-dicts is much faster than pd.read_json(lines=True) here.
    with f.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    return pd.DataFrame(rows)


def explode_section(path: str, meta: pd.DataFrame, cards: dict[str, dict] | None = None,
                    limit: int | None = None) -> pd.DataFrame:
    """
    Flatten one section across all reports into a DataFrame, one row per section row,
    with report metadata merged in on report_id. Returns the raw v2 section columns
    (renaming to the golden contract is the table builder's job).
    """
    records: list[dict] = []
    for report in iter_reports(limit):
        rows = get_section(report, path)
        if not rows:
            continue
        rid = report.get("id")
        for row in rows:
            row = dict(row)
            row["report_id"] = rid
            records.append(row)
    section = pd.DataFrame(records)
    if section.empty:
        return section
    return section.merge(meta, on="report_id", how="left", suffixes=("", "_meta"))
