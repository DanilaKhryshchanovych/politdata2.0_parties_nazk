"""Unit tests for the cleaning primitives, on real-world cases from the data."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import clean


def _one(series_func, value):
    return series_func(pd.Series([value])).iloc[0]


# --- replace_stars / depersonalisation ------------------------------------
@pytest.mark.parametrize("cell,expected", [
    ("[конфіденційна інформація]", None),
    ("***", None),
    ("****", None),
    ("*_*", None),
    ("44501620", "44501620"),
    ("", ""),
    (None, None),
])
def test_replace_stars(cell, expected):
    assert clean.replace_stars(cell) == expected or (expected is None and clean.replace_stars(cell) is None)


# --- clean_bank_account ---------------------------------------------------
def test_clean_bank_account():
    assert _one(clean.clean_bank_account, "UA 25 320371 0000000260002163900") == "UA253203710000000260002163900"


def test_clean_bank_account_symbols():
    assert _one(clean.clean_bank_account, "№ UA12:  3456\n") == "UA123456"


# --- clean_org_name -------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Фізична особа-підприємець Іванов І.І.", "ІВАНОВ І.І. ФОП"),
    ("ФОП Петренко П.П.", "ПЕТРЕНКО П.П. ФОП"),
    ("Товариство з обмеженою відповідальністю \"Ромашка\"", "ТОВ \"РОМАШКА\""),
    ("Приватне акціонерне товариство \"Банк\"", "ПрАТ \"БАНК\""),
    ("Публічне акціонерне товариство \"Х\"", "ПАТ \"Х\""),
])
def test_clean_org_name(raw, expected):
    assert _one(clean.clean_org_name, raw) == expected


def test_clean_org_name_latin_fix():
    # latin C and I inside a Cyrillic string -> Cyrillic С/І
    assert _one(clean.clean_org_name, "БАНC ІНCАЙД") == "БАНС ІНСАЙД"


# --- clean_party_name -----------------------------------------------------
def test_clean_party_name_prefix():
    assert _one(clean.clean_party_name, "Політична партія \"Слуга народу\"") == "СЛУГА НАРОДУ"


def test_clean_party_name_manual_fix():
    assert _one(clean.clean_party_name, "рішучих дій") == "ПАРТІЯ РІШУЧИХ ДІЙ"
