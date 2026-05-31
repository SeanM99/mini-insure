"""Validation rules for reserving and claims tables."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from miniinsure.dnb_validation import (
    TableSchema,
    ValidationMessage,
    error,
    validate_table_schema,
)

CLAIMS_SCHEMA = TableSchema(
    table_name="claims",
    primary_key=("claim_id",),
    columns={
        "claim_id": "string",
        "policy_id": "string",
        "accident_date": "date",
        "report_date": "date",
        "settlement_date": "date",
        "claim_status": "string",
        "ultimate_claim": "number",
    },
)

PAYMENTS_SCHEMA = TableSchema(
    table_name="payments",
    primary_key=("payment_id",),
    columns={
        "payment_id": "string",
        "claim_id": "string",
        "payment_date": "date",
        "paid_amount": "number",
    },
)

CASE_RESERVES_SCHEMA = TableSchema(
    table_name="case_reserves",
    primary_key=("case_reserve_id",),
    columns={
        "case_reserve_id": "string",
        "claim_id": "string",
        "valuation_date": "date",
        "case_reserve": "number",
    },
)

PAID_TRIANGLE_SCHEMA = TableSchema(
    table_name="paid_triangle",
    primary_key=("origin_year", "development_period"),
    columns={
        "origin_year": "integer",
        "development_period": "integer",
        "cumulative_paid": "number",
    },
)

RESERVING_SCHEMAS = {
    schema.table_name: schema
    for schema in (
        CLAIMS_SCHEMA,
        PAYMENTS_SCHEMA,
        CASE_RESERVES_SCHEMA,
    )
}


def validate_reserving_tables(
    tables: Mapping[str, pd.DataFrame],
) -> list[ValidationMessage]:
    """Validate reserving-side tables and data quality rules."""
    typed_tables: dict[str, pd.DataFrame] = {}
    messages: list[ValidationMessage] = []
    for table_name, schema in RESERVING_SCHEMAS.items():
        typed_df, schema_messages = validate_table_schema(tables.get(table_name), schema)
        messages.extend(schema_messages)
        if typed_df is not None:
            typed_tables[table_name] = typed_df

    claims = typed_tables.get("claims")
    if claims is not None:
        messages.extend(validate_claim_ultimates(claims))
        messages.extend(validate_claim_report_dates(claims))
        messages.extend(validate_claim_settlement_dates(claims))

    payments = typed_tables.get("payments")
    if payments is not None and claims is not None:
        messages.extend(validate_payment_dates(payments, claims))

    case_reserves = typed_tables.get("case_reserves")
    if case_reserves is not None:
        messages.extend(validate_case_reserves(case_reserves))

    if "paid_triangle" in tables:
        messages.extend(validate_paid_triangle(tables["paid_triangle"]))

    return messages


def validate_claim_ultimates(claims: pd.DataFrame) -> list[ValidationMessage]:
    """DQ003: claim ultimate must be non-negative."""
    if "ultimate_claim" not in claims.columns:
        return []
    invalid = claims["ultimate_claim"] < 0
    if not invalid.any():
        return []
    return [
        error(
            "DQ003",
            "claims",
            "claim ultimate must be greater than or equal to zero",
            ", ".join(claims.loc[invalid, "claim_id"].astype(str)),
        )
    ]


def validate_payment_dates(payments: pd.DataFrame, claims: pd.DataFrame) -> list[ValidationMessage]:
    """DQ004: payment date must be on or after accident date."""
    required_payment_cols = {"payment_id", "claim_id", "payment_date"}
    required_claim_cols = {"claim_id", "accident_date"}
    if not required_payment_cols.issubset(payments.columns) or not required_claim_cols.issubset(claims.columns):
        return []

    joined = payments.merge(
        claims[["claim_id", "accident_date"]],
        on="claim_id",
        how="left",
    )
    invalid = joined["payment_date"].notna() & joined["accident_date"].notna() & (
        joined["payment_date"] < joined["accident_date"]
    )
    if not invalid.any():
        return []
    return [
        error(
            "DQ004",
            "payments",
            "payment date must be on or after the claim accident date",
            ", ".join(joined.loc[invalid, "payment_id"].astype(str)),
        )
    ]


def validate_claim_report_dates(claims: pd.DataFrame) -> list[ValidationMessage]:
    """DQ005: report date must be on or after accident date."""
    if "report_date" not in claims.columns or "accident_date" not in claims.columns:
        return []
    invalid = claims["report_date"].notna() & claims["accident_date"].notna() & (
        claims["report_date"] < claims["accident_date"]
    )
    if not invalid.any():
        return []
    return [
        error(
            "DQ005",
            "claims",
            "report date must be on or after accident date",
            ", ".join(claims.loc[invalid, "claim_id"].astype(str)),
        )
    ]


def validate_claim_settlement_dates(claims: pd.DataFrame) -> list[ValidationMessage]:
    """DQ006: settlement date must be on or after report date."""
    if "settlement_date" not in claims.columns or "report_date" not in claims.columns:
        return []
    invalid = claims["settlement_date"].notna() & claims["report_date"].notna() & (
        claims["settlement_date"] < claims["report_date"]
    )
    if not invalid.any():
        return []
    return [
        error(
            "DQ006",
            "claims",
            "settlement date must be on or after report date",
            ", ".join(claims.loc[invalid, "claim_id"].astype(str)),
        )
    ]


def validate_paid_triangle(triangle: pd.DataFrame) -> list[ValidationMessage]:
    """DQ007: cumulative paid must be non-decreasing by origin year."""
    typed_triangle, messages = validate_table_schema(triangle, PAID_TRIANGLE_SCHEMA)
    if typed_triangle is None:
        return messages
    if messages:
        return messages

    ordered = typed_triangle.sort_values(["origin_year", "development_period"])
    movement = ordered.groupby("origin_year")["cumulative_paid"].diff()
    invalid = movement < 0
    if not invalid.any():
        return []
    invalid_rows = ordered.loc[invalid, ["origin_year", "development_period"]]
    row_ids = [
        f"{int(row.origin_year)}|{int(row.development_period)}"
        for row in invalid_rows.itertuples(index=False)
    ]
    return [
        error(
            "DQ007",
            "paid_triangle",
            "cumulative paid must be non-decreasing by origin year",
            ", ".join(row_ids),
        )
    ]


def validate_case_reserves(case_reserves: pd.DataFrame) -> list[ValidationMessage]:
    """DQ008: case reserve must be non-negative."""
    if "case_reserve" not in case_reserves.columns:
        return []
    invalid = case_reserves["case_reserve"] < 0
    if not invalid.any():
        return []
    return [
        error(
            "DQ008",
            "case_reserves",
            "case reserve must be greater than or equal to zero",
            ", ".join(case_reserves.loc[invalid, "case_reserve_id"].astype(str)),
        )
    ]
