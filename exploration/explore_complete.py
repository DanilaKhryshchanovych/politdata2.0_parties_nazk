"""
Phase 0 completion probe: iterate parties/reports until EVERY section and
payment-type has a non-empty sample captured, so we learn all real row schemas.
Writes results to samples/ and a schema report to samples/00_all_schemas.json.
"""
import json
import os
import time

import requests

BASE = "https://politdata.nazk.gov.ua/api/v2"
OUT = os.path.join(os.path.dirname(__file__), "samples")
os.makedirs(OUT, exist_ok=True)

S = requests.Session()
S.headers.update({
    "Content-Type": "application/json", "Accept": "application/json",
    "User-Agent": "politdata-v2-explorer/0.1 (research; danilakk14@gmail.com)",
})

SECTIONS = ["realty", "movable", "transport", "paper", "intangible", "money", "obligations"]
PAY = ["monetary_contributions", "other_contributions", "state_funding", "other_incomes",
       "budget_expenses", "outgoing_expenses", "return_expenses", "transfer_expenses"]


def unwrap(d):
    node = d.get("results", d) if isinstance(d, dict) else d
    if isinstance(node, dict):
        return node.get("list") or []
    return node if isinstance(node, list) else []


def post(path, body):
    try:
        r = S.post(f"{BASE}{path}", data=json.dumps(body), timeout=40)
        time.sleep(0.3)
        return r.json()
    except Exception:
        return {}


def pager(size=200):
    return {"filters": None, "order": None, "pager": {"page": 1, "size": size}}


def sample_row(rows):
    """First row that has the most non-null values (most informative)."""
    best, best_score = rows[0], -1
    for r in rows:
        if isinstance(r, dict):
            score = sum(1 for v in r.values() if v not in (None, "", []))
            if score > best_score:
                best, best_score = r, score
    return best


sec_schema, pay_schema = {}, {}
sec_sample, pay_sample = {}, {}

parties = unwrap(post("/parties", pager(5000)))
print(f"total parties: {len(parties)}")

active = [p for p in parties if p.get("is_active")] or parties
checked_parties = 0
for party in active:
    if len(sec_schema) == len(SECTIONS) and len(pay_schema) == len(PAY):
        break
    pid = party.get("id")
    reports = unwrap(post(f"/party/{pid}/reports", pager(300)))
    checked_parties += 1
    for rep in reports:
        if len(sec_schema) == len(SECTIONS) and len(pay_schema) == len(PAY):
            break
        rid = rep.get("id")
        for sec in SECTIONS:
            if sec in sec_schema:
                continue
            rows = unwrap(post(f"/party/report/{rid}/{sec}", pager(100)))
            if rows:
                sec_schema[sec] = list(rows[0].keys())
                sec_sample[sec] = sample_row(rows)
                print(f"  captured section {sec} (party {party.get('code')}, {rep.get('year')} q{rep.get('quarter')})")
        for pt in PAY:
            if pt in pay_schema:
                continue
            rows = unwrap(post(f"/party/report/{rid}/payments/{pt}", pager(100)))
            if rows:
                pay_schema[pt] = list(rows[0].keys())
                pay_sample[pt] = sample_row(rows)
                print(f"  captured payments/{pt} (party {party.get('code')}, {rep.get('year')} q{rep.get('quarter')})")
    if checked_parties % 10 == 0:
        print(f"...checked {checked_parties} parties; sections {len(sec_schema)}/{len(SECTIONS)}, payments {len(pay_schema)}/{len(PAY)}")

missing_sec = [s for s in SECTIONS if s not in sec_schema]
missing_pay = [p for p in PAY if p not in pay_schema]
print(f"\nchecked {checked_parties} parties")
print("MISSING sections:", missing_sec)
print("MISSING payments:", missing_pay)

with open(os.path.join(OUT, "00_all_schemas.json"), "w", encoding="utf-8") as f:
    json.dump({
        "section_schema": sec_schema, "payment_schema": pay_schema,
        "section_sample": sec_sample, "payment_sample": pay_sample,
        "missing_sections": missing_sec, "missing_payments": missing_pay,
    }, f, ensure_ascii=False, indent=1)
print("saved samples/00_all_schemas.json")
