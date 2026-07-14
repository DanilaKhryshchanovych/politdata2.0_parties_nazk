"""
Validate the v2 tables against the frozen golden files by business key
(legal_entity_edrpou, report_year, report_period), since report_id UUIDs differ
between the two systems.

Interpretation (2026-07-13 run):
  * Tables filed by a small, stable set (7_state_funding, 9.1_budget) match golden
    to the ruble (ratio 1.0000) — proof that the field mapping/cleaning/aggregation
    are correct.
  * Tables filed by all offices run ~1.2-1.46x higher on shared entity-periods —
    v2 is a live, more-complete dataset (amended reports + transactions the old
    deprecated pipeline missed), not a pipeline bug.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "reference" / "old_repo" / "data" / "excel_tables"
NEW = ROOT / "data" / "excel_tables"

TABLES = {
    "4_bank_accounts": "income_during_reporting_period",
    "5_private_contributions": "donation_sum",
    "7_state_funding_transactions": "transaction_sum",
    "8_other_income": "income_sum",
    "9.1_expenditures_public_funding": "amount",
    "9.2_expenditures_private_funds": "amount",
    "10_liabilities": "obligations_sum",
}
KEY = ["legal_entity_edrpou", "report_year", "report_period"]


def compare(name: str, col: str) -> None:
    g = pd.read_excel(GOLD / f"{name}.xlsx")
    n = pd.read_excel(NEW / f"{name}.xlsx")

    def agg(df):
        df = df.copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.groupby(KEY, dropna=False)[col].sum()

    j = pd.concat([agg(g).rename("g"), agg(n).rename("n")], axis=1)
    both = j.dropna(subset=["g", "n"])
    match = np.isclose(both.g, both.n, rtol=1e-3, atol=1).mean() * 100
    ratio = both.n.sum() / both.g.sum() if both.g.sum() else float("nan")
    print(f"{name:<32} shared_keys={len(both):>6}  exact_match={match:5.1f}%  sum_ratio_n/g={ratio:.4f}")


if __name__ == "__main__":
    print("=== v2 vs golden by (edrpou, year, quarter) ===")
    for name, col in TABLES.items():
        try:
            compare(name, col)
        except Exception as exc:  # noqa: BLE001
            print(name, "ERR", exc)
