"""
Shared helpers for the table builders: load a golden column contract and conform a
DataFrame to it (add missing columns, coerce numeric/EDRPOU dtypes, order columns).
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import settings  # noqa: E402

SCHEMA_DIR = settings.ROOT_DIR / "config" / "schemas"

# EDRPOU-style columns are int64 in the golden files (nullable Int64 here, since v2
# can leave a counterparty code null where the old API did not).
EDRPOU_COLS = {
    "legal_entity_edrpou", "party_main_EDRPOU", "bank_edrpou", "bank_EDRPOU",
    "donor_edrpou", "recipient_EDRPOU", "recepient_edrpou", "object_owner_edrpou",
    "other_party_org_EDRPOU", "local_org_EDRPOU", "edrpou", "sender_edrpou",
}


@lru_cache(maxsize=None)
def load_schema(name: str) -> tuple:
    return tuple(json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8")))


def conform(df: pd.DataFrame, schema_name: str, numeric: tuple = ()) -> pd.DataFrame:
    """Return df with exactly the golden columns, in order, with dtypes coerced."""
    cols = list(load_schema(schema_name))
    for c in cols:
        if c not in df.columns:
            df[c] = None
    for c in numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in cols:
        if c in EDRPOU_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df[cols].reset_index(drop=True)
