"""
Phase 0 API reconnaissance for politdata.nazk.gov.ua/api/v2.

Walks parties -> party card -> reports -> report detail -> every section,
dumps raw JSON into exploration/samples/, and prints a compact schema summary
(HTTP status, response wrapper shape, keys of first row) for each endpoint.

Goal: learn the REAL row schemas of each section so we can build renamers from
facts, not from the (incomplete) Swagger. Stdlib + requests only.
"""
import json
import os
import time
from collections import Counter

import requests

BASE = "https://politdata.nazk.gov.ua/api/v2"
OUT = os.path.join(os.path.dirname(__file__), "samples")
os.makedirs(OUT, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "politdata-v2-explorer/0.1 (research; contact danilakk14@gmail.com)",
})

SECTIONS = [
    "realty", "movable", "transport", "paper", "intangible", "money",
    "obligations", "payments",
]
PAYMENT_TYPES = [
    "monetary_contributions", "other_contributions", "state_funding",
    "other_incomes", "budget_expenses", "outgoing_expenses",
    "return_expenses", "transfer_expenses",
]

SUMMARY = []  # (label, http, wrapper_keys, count, row_keys)


def dump(name, obj):
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def unwrap(data):
    """Return (list_of_rows, count, wrapper_keys). Handles {results:{list,count}}."""
    if isinstance(data, dict):
        wk = list(data.keys())
        node = data.get("results", data)
        if isinstance(node, dict):
            lst = node.get("list") or node.get("data") or node.get("items") or []
            cnt = node.get("count")
            return (lst if isinstance(lst, list) else []), cnt, wk
        if isinstance(node, list):
            return node, None, wk
        return [], None, wk
    if isinstance(data, list):
        return data, None, ["<list>"]
    return [], None, ["<scalar>"]


def row_keys(rows):
    if rows and isinstance(rows[0], dict):
        return list(rows[0].keys())
    return None


def call(method, path, body=None, label=None, save=None):
    url = f"{BASE}{path}"
    try:
        if method == "POST":
            r = SESSION.post(url, data=json.dumps(body or {}), timeout=40)
        else:
            r = SESSION.get(url, timeout=40)
    except Exception as e:  # noqa
        SUMMARY.append((label or path, f"ERR {e}", None, None, None))
        return None, None
    try:
        data = r.json()
    except Exception:
        SUMMARY.append((label or path, f"{r.status_code} non-json", None, None, r.text[:120]))
        return None, r
    rows, cnt, wk = unwrap(data)
    SUMMARY.append((label or path, r.status_code, wk, cnt if cnt is not None else len(rows), row_keys(rows)))
    if save:
        dump(save, data)
    time.sleep(0.4)
    return data, r


def pager(page=1, size=50, filters=None, order=None):
    return {"filters": filters, "order": order, "pager": {"page": page, "size": size}}


def explore():
    # 1) parties list + pagination probe
    d, _ = call("POST", "/parties", pager(1, 50), "POST /parties (size=50)", "01_parties")
    rows, cnt, _ = unwrap(d) if d else ([], None, [])
    print(f"parties returned: {len(rows)}  count-field: {cnt}")

    # probe: does a big size return more? (pagination behaviour)
    d2, _ = call("POST", "/parties", pager(1, 5000), "POST /parties (size=5000)")
    rows_big, _, _ = unwrap(d2) if d2 else ([], None, [])
    print(f"parties with size=5000: {len(rows_big)}")

    # choose a party WITH regional_offices (to study parent/child), plus first party
    parent_party = next((p for p in rows if p.get("regional_offices")), None)
    child_hint = None
    if parent_party:
        dump("01b_party_with_offices", parent_party)
        ro = parent_party.get("regional_offices")
        print(f"parent party {parent_party.get('code')} has regional_offices sample: "
              f"{json.dumps(ro[:1], ensure_ascii=False)[:300]}")

    probe_parties = [p for p in [parent_party, rows[0] if rows else None] if p]

    reports_found = []  # (party, report)
    year_counter = Counter()

    for pi, party in enumerate(probe_parties):
        pid = party.get("id")
        call("GET", f"/party/{pid}", None, f"GET /party/{{id}} (p{pi})", f"02_party_card_{pi}")
        # reports list: try POST with pager first
        d, r = call("POST", f"/party/{pid}/reports", pager(1, 200),
                    f"POST /party/{{id}}/reports (p{pi})", f"03_reports_{pi}")
        rrows, _, _ = unwrap(d) if d else ([], None, [])
        if not rrows:
            # fallback: GET
            d, r = call("GET", f"/party/{pid}/reports", None,
                        f"GET /party/{{id}}/reports (p{pi})", f"03g_reports_{pi}")
            rrows, _, _ = unwrap(d) if d else ([], None, [])
        for rep in rrows:
            y = rep.get("year")
            if y:
                year_counter[y] += 1
        # keep a handful of reports to probe sections
        for rep in rrows[:6]:
            reports_found.append((pi, party, rep))

    print(f"report years seen: {dict(sorted(year_counter.items()))}")

    # 2) report detail + sections. Probe until we capture NON-EMPTY samples per section.
    captured = {}   # section -> row_keys (first non-empty wins)
    pay_captured = {}
    for idx, (pi, party, rep) in enumerate(reports_found):
        rid = rep.get("id")
        tag = f"{pi}_{idx}"
        if idx < 3:
            call("GET", f"/party/report/{rid}", None,
                 f"GET /party/report/{{id}} (r{tag})", f"04_report_detail_{tag}")
        for sec in SECTIONS:
            if sec == "payments":
                continue
            if captured.get(sec):
                continue
            d, _ = call("POST", f"/party/report/{rid}/{sec}", pager(1, 100),
                        f"POST report/{sec} (r{tag})")
            srows, _, _ = unwrap(d) if d else ([], None, [])
            if srows:
                captured[sec] = row_keys(srows)
                dump(f"05_section_{sec}", d)
        for pt in PAYMENT_TYPES:
            if pay_captured.get(pt):
                continue
            d, _ = call("POST", f"/party/report/{rid}/payments/{pt}", pager(1, 100),
                        f"POST payments/{pt} (r{tag})")
            prows, _, _ = unwrap(d) if d else ([], None, [])
            if prows:
                pay_captured[pt] = row_keys(prows)
                dump(f"06_payments_{pt}", d)
        # stop early if we captured most sections
        if len(captured) >= len(SECTIONS) - 1 and len(pay_captured) >= 5:
            print(f"captured enough after {idx+1} reports")
            break

    print("\n=== SECTION ROW SCHEMAS (non-empty samples) ===")
    for sec in SECTIONS:
        if sec == "payments":
            continue
        print(f"  {sec:14} -> {captured.get(sec)}")
    print("\n=== PAYMENTS/{type} ROW SCHEMAS ===")
    for pt in PAYMENT_TYPES:
        print(f"  {pt:24} -> {pay_captured.get(pt)}")

    # persist summary + captured schemas
    dump("00_summary", [
        {"label": s[0], "http": s[1], "wrapper": s[2], "count": s[3], "row_keys": s[4]}
        for s in SUMMARY
    ])
    dump("00_captured_schemas", {"sections": captured, "payments": pay_captured})


if __name__ == "__main__":
    explore()
    print("\n=== ENDPOINT CALL SUMMARY ===")
    for label, http, wk, cnt, rk in SUMMARY:
        print(f"[{http}] {label:38} wrap={wk} n={cnt}")
        if rk:
            print(f"        row_keys: {rk}")
    print(f"\nSamples saved to: {OUT}")
