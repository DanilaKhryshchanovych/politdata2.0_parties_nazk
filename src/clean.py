"""
Cleaning primitives, ported from the old repo's main_functions.py (pure pandas,
API-agnostic). Behaviour is kept 1:1 with the original so outputs match the golden
files; the only change is that the manual-fix dictionaries are read from
config/*_renamer.json instead of being hard-coded.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402

CONFIG_DIR = settings.ROOT_DIR / "config"


@lru_cache(maxsize=None)
def _load_renamer(name: str) -> tuple:
    path = CONFIG_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(data.items())


def party_renamer() -> dict:
    return dict(_load_renamer("party_renamer.json"))


def org_renamer() -> dict:
    return dict(_load_renamer("org_renamer.json"))


# --- generic --------------------------------------------------------------
# v2 marks a whole depersonalised cell with this literal (old API used '***').
CONFIDENTIAL = "[конфіденційна інформація]"


def replace_stars(cell):
    """A depersonalised cell -> None. Handles the old star form and v2's literal."""
    if isinstance(cell, str):
        s = cell.strip()
        if s == CONFIDENTIAL:
            return None
        if s and (set(s) == {"*"} or set(s) == {"*", "_"}):
            return None
    return cell


def replace_stars_df(df: pd.DataFrame) -> pd.DataFrame:
    """Null out depersonalised cells in every text column (in place)."""
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].map(replace_stars)
    return df


def clean_bank_account(series: pd.Series) -> pd.Series:
    """Strip IBAN of №, spaces, colons and newlines."""
    return (series.astype("string")
            .str.replace("№", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(":", "", regex=False)
            .str.replace("\n", "", regex=False)
            .str.strip())


# --- party names ----------------------------------------------------------
_PARTY_PREFIXES = [
    r"^ПОЛІТИЧНА ПАРТІЯ", r"^ВСЕУКРАЇНСЬКЕ ОБ'ЄДНАННЯ", r"ВСЕУКРАЇНСЬКЕ ПОЛІТИЧНЕ ОБ'ЄДНАННЯ",
    r"ПОЛІТИЧНОЇ ПАРТІЇ", r"ПОЛІТИЧЯНА ПАРТІЯ", r"СОЦІАЛЬНО-ЕКОЛОГІЧНА ПАРТІЯ",
    r"ВСЕУКРАЇНСЬКЕ ОБ'ЄДНАННЯ", r"СОЦІАЛЬНО-ПОЛІТИЧНИЙ СОЮЗ", "«", "»", '"',
]


def clean_party_name(series: pd.Series) -> pd.Series:
    """Uppercase, strip party prefixes/quotes, collapse spaces, apply manual fixes."""
    s = series.astype("string").str.upper()
    for pat in _PARTY_PREFIXES:
        s = s.str.replace(pat, "", regex=True)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    return s.replace(party_renamer())


# --- org / counterparty names ---------------------------------------------
_FOP_VARIANTS = [
    "ФІЗИЧНА ОСОБА ПІДРИЄМЕЦЬ", "ФІЗИЧНА ОСОБА ПІДПРИЄМЕЦЬ",
    "ФІЗИЧНА ОСОБА- ПІДПРИЄМЕЦЬ", "ФІЗИЧНА ОСОБА-ПІДПРИЄМЕЦЬ", "ФІЗИЧНА ОСОБА-ПІДРИЄМЕЦЬ",
    "ФІЗИЧНА ОСОБА - ПІДПРИЄМЕЦЬ", "ФІЗИЧНА ОСОБА -ПІДПРИЄМЕЦЬ", "ФІЗИЧНА ОБОБА-ПІДПРИЄМЕЦЬ",
    "ФІЗИЧНА ОСОБА-ПІДПРИМЕЦЬ",
]
_ABBREV = [
    (["ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ", "ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПРОВІДАЛЬНІСТЮ"], "ТОВ"),
    (["ПРИВАТНЕ АКЦІОНЕРНЕ ТОВАРИСТВО"], "ПрАТ"),
    (["ПУБЛІЧНЕ АКЦІОНЕРНЕ ТОВАРИСТВО"], "ПАТ"),
    (["ДЕРЖАВНОЇ ПОДАТКОВОЇ СЛУЖБИ", "ДЕРЖАВНА ПОДАТКОВА СЛУЖБА"], "ДПС"),
    (["ПОЛІТИЧНА ПАРТІЯ"], "ПП"),
    (["АКЦІОНЕРНЕ ТОВАРИВСТВО", "АКЦІОНЕРНЕ ТОВАРИСТВО"], "АТ"),
]


def clean_org_name(series: pd.Series) -> pd.Series:
    """
    Full counterparty-name normalisation (donors, recipients, owners, banks):
    uppercase -> collapse spaces -> manual dict -> ФОП/ТОВ/ПрАТ/ПАТ/ДПС/ПП/АТ ->
    move leading ФОП to the end -> unify apostrophes -> latin C/I -> Cyrillic С/І.
    Mirrors table_functions.py exactly.
    """
    s = series.astype("string").str.upper()
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()

    # manual collapses (config/org_renamer.json)
    s = s.replace(org_renamer())

    for variant in _FOP_VARIANTS:
        s = s.str.replace(variant, "ФОП", regex=True)
    for variants, short in _ABBREV:
        for v in variants:
            s = s.str.replace(v, short, regex=True)

    # leading "ФОП ..." -> "... ФОП"
    mask = s.str.startswith("ФОП", na=False)
    s.loc[mask] = s.loc[mask].str.replace("ФОП ", "", regex=False).str.strip() + " ФОП"

    # unify apostrophes between word chars
    s = s.str.replace(r"(?<=\w)[’\"`](?=\w)", "'", regex=True)

    # occasional latin letters inside a Cyrillic string
    cyr = s.str.contains("[А-Я]", na=False)
    s.loc[cyr] = s.loc[cyr].str.replace("C", "С", regex=False).str.replace("I", "І", regex=False)
    return s
