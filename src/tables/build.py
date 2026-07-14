"""
Table builders. Most tables follow one pattern (explode a section -> rename v2
fields to the golden contract -> depersonalise -> clean -> filter -> conform), so
they are driven by SECTION_SPECS. Table 1 and the 0_* aggregates are special-cased.

Field mappings come from api_v2_findings.md §4a/§6 and the old renamers. Where v2
has no source for a golden column (see DIVERGENCES in docs) the column is emitted
empty rather than dropped, so the column contract still holds.
"""
from __future__ import annotations

import pandas as pd

from src.clean import clean_bank_account, clean_org_name, replace_stars_df
from src.enrich import check_edrpou_for_party, set_central_region
from src.load import explode_section
from src.tables.base import conform


# --- filters (v2-adapted; see DIVERGENCES) --------------------------------
def _f_donor(df):        return df[df["donor_name"].notna()]
def _f_donor_type(df):   return df[df["donor_name"].notna() & df["donor_type"].notna()]
def _f_recipient(df):    return df[df["recipient_name"].notna()]
def _f_object(df):       return df[df["object_type"].notna()]
def _f_vehicle(df):      return df[df["object_type"].notna() & df["object_brand"].notna()]
def _f_name(df):         return df[df["name"].notna()]
def _f_other_org(df):    return df[(df["other_party_org_name"] != "0") | (df["other_party_org_EDRPOU"] != "00000000")]


# section -> spec. rename maps v2 field -> golden clean column.
SECTION_SPECS: dict[str, dict] = {
    # ---- properties ----
    "3.1_property_objects": {
        "section": "properties.property_object",
        "rename": {"object_address": "object_location", "owning_date": "object_date_of_acquisition_of_the_right",
                   "owning_cost": "object_price", "total_area": "object_area", "object_number": "object_registration_number",
                   "object_rights": "object_type_of_use", "owner_name": "object_owner_name", "owner_code": "object_owner_edrpou"},
        "filter": _f_object, "org_clean": ["object_owner_name"],
        "check_edrpou": [("object_owner_edrpou", "object_owner_type")],
        "numeric": ("object_price", "object_area"),
    },
    "3.2_movable_property": {
        "section": "properties.property_movable",
        "rename": {"movable_type": "object_type", "owning_date": "object_date_of_acquisition_of_the_right",
                   "owning_cost": "object_price", "description": "object_description", "trade_mark": "object_trademark",
                   "movable_rights": "object_type_of_use"},
        "org_clean": ["object_owner"], "numeric": ("object_price",),
    },
    "3.3_vehicles": {
        "section": "properties.property_transport",
        "rename": {"transport_type": "object_type", "owning_date": "object_date_of_acquisition_of_the_right",
                   "owning_cost": "object_price", "object_number": "object_id_number", "transport_brand": "object_brand",
                   "transport_model": "object_model", "production_year": "object_production_year",
                   "object_rights": "object_type_of_use", "substraction_date": "object_alienation_date"},
        "filter": _f_vehicle, "org_clean": ["object_owner"],
        "check_edrpou": [("object_owner_edrpou", "object_owner_type")],
        "numeric": ("object_price", "object_production_year"),
    },
    "3.5_intangible_assets": {
        "section": "properties.property_intangible_asset",
        "rename": {"asset_count": "asset_amount", "owning_date": "date_of_acquisition_of_the_right",
                   "owning_cost": "asset_value", "asset_rights": "type_of_use", "substraction_date": "alienation_date"},
        "numeric": ("asset_value", "asset_amount"),
    },
    "3.4_securities": {  # empty across the whole cache (no v2 data) -> schema-only file
        "section": "properties.property_paper", "rename": {},
    },
    # ---- obligations ----
    "10_liabilities": {
        "section": "obligations",
        "rename": {"object_type": "obligation_type", "owning_reason": "reason", "owning_date": "date_of_occurrence",
                   "person_name": "name", "person_type": "type", "person_code": "edrpou", "person_addr": "location",
                   "owning_cost": "obligations_sum", "end_period_remains_cost": "amount_not_yet_paid"},
        "filter": _f_name, "org_clean": ["name"], "numeric": ("obligations_sum", "amount_not_yet_paid"),
    },
    # ---- bank accounts ----
    "4_bank_accounts": {
        "section": "properties.property_moneys",
        "rename": {"account_holder": "bank_name", "account_holder_code": "bank_edrpou",
                   "begin_period_balance": "balance_for_first_day_of_period",
                   "report_period_income": "income_during_reporting_period",
                   "report_period_used_funds": "spent_during_reporting_period",
                   "end_period_balance": "balance_for_last_day_of_period"},
        "bank_cols": ["account_number"],
        "numeric": ("balance_for_first_day_of_period", "income_during_reporting_period",
                    "spent_during_reporting_period", "balance_for_last_day_of_period"),
    },
    # ---- incoming payments (payer = source) ----
    "5_private_contributions": {
        "section": "payment_info.incoming.monetary_contributions",
        "rename": {"payer_name": "donor_name", "payer_code": "donor_edrpou", "payer_type": "donor_type",
                   "payer_birthday": "donor_birth_date", "payer_address": "donor_location",
                   "receiver_bank_name": "bank_name", "receiver_bank_code": "bank_edrpou",
                   "receiver_account_iban": "bank_account", "payment_operation_date": "donation_date",
                   "payment_amount": "donation_sum", "refund_amount": "donation_refund_sum"},
        "filter": _f_donor, "bank_cols": ["bank_account"], "org_clean": ["donor_name"],
        "check_edrpou": [("donor_edrpou", "donor_type")], "numeric": ("donation_sum", "donation_refund_sum"),
    },
    "6_in_kind_donations": {
        "section": "payment_info.incoming.other_contributions",
        "rename": {"payment_type": "donation_type", "payer_name": "donor_name", "payer_code": "donor_edrpou",
                   "payer_type": "donor_type", "payer_birthday": "donor_birth_date", "payer_address": "donor_location",
                   "payment_operation_date": "donation_date", "payment_number": "object_registration_number",
                   "payment_amount": "donation_contract_price"},
        "filter": _f_donor_type, "org_clean": ["donor_name"],
        "check_edrpou": [("donor_edrpou", "donor_type")],
        "numeric": ("donation_contract_price", "donation_metodological_price"),
    },
    "7_state_funding_transactions": {
        "section": "payment_info.incoming.state_funding",
        "rename": {"payment_type": "state_funding_form", "receiver_bank_name": "bank_name",
                   "receiver_bank_code": "bank_edrpou", "receiver_account_iban": "bank_account",
                   "payment_operation_date": "transaction_date", "payment_amount": "transaction_sum",
                   "refund_amount": "refund_sum"},
        "bank_cols": ["bank_account"], "numeric": ("transaction_sum", "refund_sum"),
    },
    "8_other_income": {
        "section": "payment_info.incoming.other_incomes",
        "rename": {"payment_type": "income_type", "payment_description": "income_description",
                   "payer_name": "sender_name", "payer_type": "sender_type", "payment_number": "object_registration_number",
                   "payment_operation_date": "income_date", "receiver_bank_name": "bank_name",
                   "receiver_bank_code": "bank_edrpou", "receiver_account_iban": "bank_account",
                   "payment_amount": "income_sum"},
        "bank_cols": ["bank_account"], "org_clean": ["sender_name"], "numeric": ("income_sum",),
    },
    # ---- outgoing payments (receiver = recipient) ----
    "9.1_expenditures_public_funding": {
        "section": "payment_info.outgoing.budget_expenses",
        "rename": {"payer_bank_name": "bank_name", "payer_bank_code": "bank_EDRPOU",
                   "payer_account_iban": "account_number", "payer_account_type": "account_type",
                   "payment_operation_date": "payment_date", "payment_reason": "payment_purpose",
                   "receiver_name": "recipient_name", "receiver_code": "recipient_EDRPOU",
                   "receiver_type": "recipient_type", "receiver_address": "recipient_location",
                   "payment_purpose": "payment_purpose2", "payment_amount": "amount"},
        "bank_cols": ["account_number"], "org_clean": ["recipient_name"],
        "check_edrpou": [("recipient_EDRPOU", "recipient_type")], "numeric": ("amount",),
    },
    "9.2_expenditures_private_funds": {
        "section": "payment_info.outgoing.outgoing_expenses",
        "rename": {"payer_bank_name": "bank_name", "payer_bank_code": "bank_EDRPOU",
                   "payer_account_iban": "account_number", "payer_account_type": "account_type",
                   "payment_operation_date": "payment_date", "payment_reason": "payment_purpose",
                   "receiver_name": "recipient_name", "receiver_type": "recipient_type",
                   "receiver_code": "recipient_EDRPOU", "receiver_address": "recipient_location",
                   "payment_purpose": "payment_purpose2", "payment_amount": "amount"},
        "filter": _f_recipient, "bank_cols": ["account_number"], "org_clean": ["recipient_name"],
        "check_edrpou": [("recipient_EDRPOU", "recipient_type")], "numeric": ("amount",),
    },
    "9.3_false_donations_info": {
        "section": "payment_info.outgoing.return_expenses",
        "rename": {"receiver_bank_name": "bank_name", "receiver_bank_code": "bank_EDRPOU",
                   "receiver_account_iban": "account_number", "payment_operation_date": "receiving_date",
                   "payer_name": "donor_name", "payer_code": "donor_edrpou", "payer_type": "donor_type",
                   "payment_amount": "amount", "refund_date": "returning_date", "receiver_name": "recepient_name",
                   "receiver_type": "recepient_type", "receiver_code": "recepient_edrpou",
                   "refund_reason": "returning_reason", "refund_amount": "returning_sum",
                   "refund_budget_amount": "returning_to_budget"},
        "bank_cols": ["account_number"], "org_clean": ["donor_name"],
        "numeric": ("amount", "returning_sum", "returning_to_budget"),
    },
    "9.5_false_in_kind_donations_info": {
        "section": "payment_info.outgoing.transfer_expenses",
        "rename": {"payment_type": "donation_type", "payment_number": "object_registration_number",
                   "payment_operation_date": "receiving_date", "payer_name": "donor_name",
                   "payer_type": "donor_type", "payer_code": "donor_edrpou", "payment_amount": "donation_sum",
                   "refund_date": "returning_date", "receiver_name": "recepient_name",
                   "receiver_type": "recepient_type", "receiver_code": "recepient_edrpou",
                   "refund_reason": "returning_reason", "refund_amount": "returning_sum"},
        "org_clean": ["donor_name"], "numeric": ("donation_sum", "returning_sum"),
    },
    # ---- report-level lists ----
    "2.1_local_orgs_info": {
        "section": "regional_offices",
        "rename": {"name": "local_org_name", "code": "local_org_EDRPOU"},
    },
    "2.2_other_party_orgs_info": {
        "section": "organizations",
        "rename": {"name": "other_party_org_name", "code": "other_party_org_EDRPOU"},
        "filter": _f_other_org,
    },
}


def transform_section(schema: str, df: pd.DataFrame, central: set[str], office: set[str]) -> pd.DataFrame:
    """Turn a section frame (already merged with report metadata) into the golden table."""
    spec = SECTION_SPECS[schema]
    if df.empty:
        return conform(df, schema)
    df = df.rename(columns=spec.get("rename", {}))
    replace_stars_df(df)                       # depersonalise [конфіденційна інформація] / ***
    for c in spec.get("bank_cols", []):
        if c in df.columns:
            df[c] = clean_bank_account(df[c])
    for edc, tc in spec.get("check_edrpou", []):
        check_edrpou_for_party(df, edc, tc, central, office)
    set_central_region(df)
    if spec.get("filter"):
        df = spec["filter"](df)
    for c in spec.get("org_clean", []):
        if c in df.columns:
            df[c] = clean_org_name(df[c])
    return conform(df, schema, numeric=spec.get("numeric", ()))


def build_section_table(schema: str, meta: pd.DataFrame, central: set[str], office: set[str],
                        cards: dict | None = None) -> pd.DataFrame:
    """Standalone (single-section) build: explode from the raw cache, then transform."""
    df = explode_section(SECTION_SPECS[schema]["section"], meta, cards)
    return transform_section(schema, df, central, office)


def build_section_from_staged(schema: str, raw: pd.DataFrame, meta: pd.DataFrame,
                              central: set[str], office: set[str]) -> pd.DataFrame:
    """Build from a pre-staged raw section frame (single-pass path)."""
    if raw.empty:
        return conform(raw, schema)
    merged = raw.merge(meta, on="report_id", how="left", suffixes=("", "_meta"))
    return transform_section(schema, merged, central, office)


# --- table 1 --------------------------------------------------------------
def build_table_1(meta: pd.DataFrame) -> pd.DataFrame:
    return conform(meta.copy(), "1_legal_entity_report_info",
                   numeric=("number_of_employees_contract", "number_of_employees_civil_agreement"))


# --- 0_* aggregates -------------------------------------------------------
def build_0_reports_per_period(table1: pd.DataFrame) -> pd.DataFrame:
    keys = ["legal_entity_name", "legal_entity_edrpou", "officeType", "party_main_name", "party_main_EDRPOU"]
    t = table1[keys + ["report_id", "report_period", "report_year"]].copy()
    t["reported_period"] = t["report_year"].astype("string") + ", " + t["report_period"].astype("string")
    t = t.drop(columns=["report_period", "report_year"]).drop_duplicates()
    t = t.groupby(keys + ["reported_period"], as_index=False, dropna=False).agg(
        {"report_id": lambda x: "; ".join(x.dropna().astype(str))})
    t = t.pivot(index=keys, columns="reported_period", values="report_id").reset_index()
    t.columns.name = None
    value_cols = [c for c in t.columns if c not in keys]
    t[value_cols] = t[value_cols].fillna("")           # only period columns, not Int64 keys
    return t.sort_values("party_main_name")


def build_0_duplicates(meta: pd.DataFrame) -> pd.DataFrame:
    key = ["report_period", "report_year", "legal_entity_name", "legal_entity_edrpou", "report_id"]
    dup = meta[meta.duplicated(subset=key, keep=False)]
    cols = ["legal_entity_name", "legal_entity_edrpou", "party_main_name", "party_main_EDRPOU",
            "report_year", "report_type", "report_period", "report_submition_date"]
    return dup[cols].reset_index(drop=True)


def membership_set(name: str, df: pd.DataFrame):
    """The EDRPOU set used by 0_files: a table's own legal_entity_edrpou (or local_org_EDRPOU)."""
    if name.startswith("0_") or name.startswith("1_") or name == "2.2_other_party_orgs_info":
        return None
    col = "legal_entity_edrpou" if "legal_entity_edrpou" in df.columns else \
          ("local_org_EDRPOU" if "local_org_EDRPOU" in df.columns else None)
    return set(df[col].dropna().tolist()) if col else None


def build_0_files(table1: pd.DataFrame, sets: dict[str, set]) -> pd.DataFrame:
    df = table1[["legal_entity_name", "legal_entity_edrpou", "officeType",
                 "party_main_name", "party_main_EDRPOU"]].drop_duplicates().reset_index(drop=True)
    for name in sorted(s for s in sets if sets[s] is not None):
        df[f"{name}.xlsx"] = df["legal_entity_edrpou"].isin(sets[name]).astype(int)
    return df
