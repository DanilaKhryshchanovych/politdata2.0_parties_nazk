"""
Enrichment steps, ported from main_functions.py / table_functions.py:
  * clean party_main_name and unify names to the latest-dated spelling per EDRPOU;
  * mark counterparties that are themselves party structures as 'Партійний осередок';
  * force legal_entity_region -> 'Україна' for central offices.
"""
from __future__ import annotations

import pandas as pd

from src.clean import clean_party_name

CENTRAL_OFFICE = "Центральний офіс"
PARTY_UNIT = "Партійний осередок"


def clean_party_main(meta: pd.DataFrame) -> pd.DataFrame:
    meta["party_main_name"] = clean_party_name(meta["party_main_name"])
    return meta


def _unify(df: pd.DataFrame, code_col: str, name_col: str, date_col: str) -> None:
    """Give every row of a code the name from its latest-dated report (in place)."""
    ref = (df[[date_col, code_col, name_col]]
           .sort_values([code_col, date_col])
           .drop_duplicates([code_col], keep="last")
           .set_index(code_col)[name_col]
           .to_dict())
    df[name_col] = df[code_col].map(ref).fillna(df[name_col])


def unify_names(meta: pd.DataFrame) -> pd.DataFrame:
    _unify(meta, "party_main_EDRPOU", "party_main_name", "report_submition_date")
    _unify(meta, "legal_entity_edrpou", "legal_entity_name", "report_submition_date")
    return meta


def check_edrpou_for_party(df: pd.DataFrame, edrpou_col: str, type_col: str,
                           central: set[str], office: set[str]) -> pd.DataFrame:
    if edrpou_col not in df.columns or type_col not in df.columns:
        return df
    codes = df[edrpou_col].astype("string")
    mask = codes.isin(central) | codes.isin(office)
    df.loc[mask, type_col] = PARTY_UNIT
    return df


def set_central_region(df: pd.DataFrame, region_col: str = "legal_entity_region") -> pd.DataFrame:
    if region_col in df.columns and "officeType" in df.columns:
        df.loc[df["officeType"] == CENTRAL_OFFICE, region_col] = "Україна"
    return df
