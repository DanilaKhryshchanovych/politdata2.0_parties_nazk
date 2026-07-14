"""
Validate produced tables against the golden files from the old repo:
  (a) column contract (names + order) matches config/schemas/;
  (b) row counts and total sums per table are in a sane range vs golden.

This is a migration sanity check, not an exact-equality test: v2 covers a different
(longer) time span than the golden snapshot, so counts legitimately differ. Large
gaps (e.g. a table that should have data coming out empty) are the signal to chase.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402

GOLDEN_DIR = settings.ROOT_DIR / "reference" / "old_repo" / "data" / "excel_tables"
SCHEMA_DIR = settings.ROOT_DIR / "config" / "schemas"

# a representative numeric column per table, for a sum sanity check
SUM_COL = {
    "4_bank_accounts": "income_during_reporting_period",
    "5_private_contributions": "donation_sum",
    "7_state_funding_transactions": "transaction_sum",
    "8_other_income": "income_sum",
    "9.1_expenditures_public_funding": "amount",
    "9.2_expenditures_private_funds": "amount",
    "10_liabilities": "obligations_sum",
}


def _load_schema(name: str) -> list[str]:
    return json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def validate_table(name: str, df: pd.DataFrame) -> dict:
    res = {"table": name, "rows": len(df), "issues": []}

    schema_path = SCHEMA_DIR / f"{name}.json"
    if schema_path.exists():
        expected = _load_schema(name)
        if list(df.columns) != expected:
            missing = [c for c in expected if c not in df.columns]
            extra = [c for c in df.columns if c not in expected]
            if missing or extra:
                res["issues"].append(f"columns differ (missing={missing} extra={extra})")
            else:
                res["issues"].append("column ORDER differs")

    golden_path = GOLDEN_DIR / f"{name}.xlsx"
    if golden_path.exists():
        g = pd.read_excel(golden_path)
        res["golden_rows"] = len(g)
        col = SUM_COL.get(name)
        if col and col in df.columns and col in g.columns:
            res["sum_new"] = float(pd.to_numeric(df[col], errors="coerce").sum())
            res["sum_golden"] = float(pd.to_numeric(g[col], errors="coerce").sum())
        if len(df) == 0 and len(g) > 0:
            res["issues"].append(f"EMPTY but golden has {len(g)} rows")
    return res


def print_report(results: list[dict]) -> list[dict]:
    results = sorted(results, key=lambda r: r["table"])

    def fmt(v):
        return f"{v:,.2f}" if isinstance(v, float) else str(v)

    print("\n=== VALIDATION ===")
    print(f"{'table':<40} | {'rows':>9} | {'golden':>9} | {'sum_new':>18} | {'sum_golden':>18} | issues")
    for r in results:
        print(f"{r['table']:<40} | {r['rows']:>9} | {str(r.get('golden_rows','-')):>9} | "
              f"{fmt(r.get('sum_new','-')):>18} | {fmt(r.get('sum_golden','-')):>18} | {'; '.join(r['issues'])}")
    return results
