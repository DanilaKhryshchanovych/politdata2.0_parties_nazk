"""
One-off: (1) extract the golden column contract from the old repo's xlsx into
config/schemas/, and (2) answer the Phase-2 open data questions by sampling the
raw cache. Read-only w.r.t. the API; writes only config/schemas/*.json and prints
a recon report.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "reference" / "old_repo" / "data" / "excel_tables"
SCHEMA_DIR = ROOT / "config" / "schemas"
RAW_DIR = ROOT / "data" / "raw"
PARTIES_FILE = RAW_DIR / "_parties.json"


def extract_schemas() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for xlsx in sorted(GOLDEN_DIR.glob("*.xlsx")):
        cols = pd.read_excel(xlsx, nrows=0).columns.tolist()
        name = xlsx.stem
        (SCHEMA_DIR / f"{name}.json").write_text(
            json.dumps(cols, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        out[name] = cols
    print(f"[schemas] wrote {len(out)} schema files to config/schemas/")
    for name, cols in out.items():
        print(f"  {name}: {len(cols)} cols")


def _iter_raw(limit: int | None):
    n = 0
    for entry in os.scandir(RAW_DIR):
        if not entry.name.endswith(".json") or entry.name.startswith("_"):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                yield entry.name[:-5], json.load(f)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! failed to read {entry.name}: {exc}")
            continue
        n += 1
        if limit and n >= limit:
            return


def _type_name(v):
    if v is None:
        return "None"
    return type(v).__name__


def recon(limit: int) -> None:
    # party directory: which ids are central vs office
    parties = json.loads(PARTIES_FILE.read_text(encoding="utf-8"))
    central_ids, office_ids = set(), set()
    for p in parties:
        if p.get("id"):
            central_ids.add(p["id"])
        for o in p.get("regional_offices") or []:
            if o.get("id"):
                office_ids.add(o["id"])
    print(f"\n[dir] central parties={len(central_ids)} offices={len(office_ids)}")

    office_flag_by_dir = Counter()   # (is_party_office, in_central_dir, in_office_dir)
    special_status = Counter()
    report_status = Counter()
    sum_types: dict[str, Counter] = {}
    star_hits = Counter()
    star_examples: dict[str, set] = {}
    group_codes: dict[str, Counter] = {}
    paper_schema = None
    paper_report = None
    volunteer_keys = Counter()
    employees_seen = Counter()

    def note_sum(field, v):
        sum_types.setdefault(field, Counter())[_type_name(v)] += 1

    def note_star(field, v):
        if isinstance(v, str) and v and set(v) <= {"*", "_", " "}:
            star_hits[field] += 1
            star_examples.setdefault(field, set())
            if len(star_examples[field]) < 5:
                star_examples[field].add(v)

    seen = 0
    for rid, r in _iter_raw(limit):
        seen += 1
        pid = r.get("party_id")
        flag = r.get("is_party_office")
        office_flag_by_dir[(flag, pid in central_ids, pid in office_ids)] += 1
        special_status[r.get("special_status")] += 1
        for k in ("employees_by_employment_contract", "employees_by_civil_contract",
                  "employees_by_volunteers", "quantityThird", "volunteers"):
            if k in r:
                employees_seen[k] += 1

        props = r.get("properties") or {}
        paper = props.get("property_paper") or []
        if paper and paper_schema is None:
            paper_schema = sorted(paper[0].keys())
            paper_report = rid
        for row in props.get("property_moneys") or []:
            report_status[row.get("report_status")] += 1
            for f in ("begin_period_balance", "end_period_balance",
                      "report_period_income", "report_period_used_funds"):
                note_sum(f"money.{f}", row.get(f))

        pi = r.get("payment_info") or {}
        for direction in ("incoming", "outgoing"):
            for sect, rows in (pi.get(direction) or {}).items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    report_status[row.get("report_status")] += 1
                    note_sum(f"pay.{sect}.payment_amount", row.get("payment_amount"))
                    gc = row.get("group_code")
                    group_codes.setdefault(sect, Counter())[gc] += 1
                    for f in ("payer_code", "payer_birthday", "receiver_code", "receiver_birthday"):
                        note_star(f, row.get(f))

    print(f"\n[recon] scanned {seen} reports (limit={limit})")
    print("\n[is_party_office vs directory]  (flag, in_central, in_office): count")
    for k, v in office_flag_by_dir.most_common():
        print(f"  {k}: {v}")
    print("\n[special_status on report]:", dict(special_status))
    print("[report_status on section rows]:", dict(report_status))
    print("[employees keys present]:", dict(employees_seen))
    print("\n[sum field types]:")
    for f, c in sorted(sum_types.items()):
        print(f"  {f}: {dict(c)}")
    print("\n[star / depersonalization hits]:", dict(star_hits))
    for f, ex in star_examples.items():
        print(f"  {f} examples: {ex}")
    print("\n[group_code per payment section]:")
    for sect, c in group_codes.items():
        print(f"  {sect}: {dict(c)}")
    print(f"\n[paper schema] from report {paper_report}: {paper_schema}")


if __name__ == "__main__":
    extract_schemas()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    recon(limit)
