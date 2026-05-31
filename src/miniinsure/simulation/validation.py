"""Validation rules for synthetic simulation tables."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from miniinsure.dnb_validation import (
    TableSchema,
    ValidationMessage,
    error,
    validate_table_schema,
)

POLICIES_SCHEMA = TableSchema(
    table_name="policies",
    primary_key=("policy_id",),
    columns={
        "policy_id": "string",
        "inception_date": "date",
        "expiry_date": "date",
        "accident_year": "integer",
        "product": "string",
        "portfolio_mode": "string",
        "written_premium": "number",
        "earned_premium": "number",
        "exposure": "number",
        "sum_insured": "number",
    },
)

GENERATED_POLICIES_SCHEMA = TableSchema(
    table_name="policies",
    primary_key=("policy_id",),
    columns={
        "policy_id": "string",
        "underwriting_year": "integer",
        "accident_year": "integer",
        "inception_date": "date",
        "expiry_date": "date",
        "written_exposure": "number",
        "earned_exposure": "number",
        "country_group": "string",
        "solvency_ii_lob": "string",
        "homogeneous_risk_group": "string",
        "coverage_type": "string",
        "distribution_channel": "string",
        "customer_type": "string",
        "driver_age_band": "string",
        "vehicle_segment": "string",
        "mileage_band": "string",
        "prior_claims_band": "string",
        "bonus_malus_class": "string",
        "deductible_band": "string",
        "urbanicity": "string",
        "technical_premium": "number",
        "charged_premium": "number",
        "written_premium": "number",
        "earned_premium": "number",
        "lapse_probability": "number",
        "renewal_probability": "number",
    },
)

CATASTROPHE_EVENTS_SCHEMA = TableSchema(
    table_name="catastrophe_events",
    primary_key=("event_id",),
    columns={
        "event_id": "string",
        "event_date": "date",
        "event_type": "string",
        "gross_loss": "number",
        "insured_loss": "number",
    },
)

REINSURANCE_RECOVERIES_SCHEMA = TableSchema(
    table_name="reinsurance_recoveries",
    primary_key=("recovery_id",),
    columns={
        "recovery_id": "string",
        "event_id": "string",
        "treaty_id": "string",
        "insured_loss": "number",
        "treaty_retention": "number",
        "treaty_limit": "number",
        "recovery_amount": "number",
    },
)

ECONOMIC_SCENARIOS_SCHEMA = TableSchema(
    table_name="economic_scenarios",
    primary_key=("scenario_id",),
    columns={
        "scenario_id": "string",
        "scenario_name": "string",
        "valuation_date": "date",
        "risk_free_rate": "number",
        "inflation_rate": "number",
        "equity_return": "number",
    },
)

ASSET_PORTFOLIO_SCHEMA = TableSchema(
    table_name="asset_portfolio",
    primary_key=("asset_id",),
    columns={
        "asset_id": "string",
        "asset_class": "string",
        "market_value": "number",
        "portfolio_weight": "number",
        "currency": "string",
    },
)

SYNTHETIC_TRUTH_SCHEMA = TableSchema(
    table_name="synthetic_truth",
    primary_key=("truth_id",),
    columns={
        "truth_id": "string",
        "claim_id": "string",
        "ultimate_claim": "number",
        "true_frequency_factor": "number",
        "true_severity_factor": "number",
        "generation_seed": "integer",
    },
)

OBSERVED_VALUATION_SNAPSHOT_SCHEMA = TableSchema(
    table_name="observed_valuation_snapshot",
    primary_key=("snapshot_id",),
    columns={
        "snapshot_id": "string",
        "valuation_date": "date",
        "policy_count": "integer",
        "claim_count": "integer",
        "paid_to_date": "number",
        "case_reserve_total": "number",
        "ultimate_claim_total": "number",
        "assumption_hash": "string",
    },
)

SIMULATION_SCHEMAS = {
    schema.table_name: schema
    for schema in (
        POLICIES_SCHEMA,
        CATASTROPHE_EVENTS_SCHEMA,
        REINSURANCE_RECOVERIES_SCHEMA,
        ECONOMIC_SCENARIOS_SCHEMA,
        ASSET_PORTFOLIO_SCHEMA,
        SYNTHETIC_TRUTH_SCHEMA,
        OBSERVED_VALUATION_SNAPSHOT_SCHEMA,
    )
}


def validate_simulation_tables(
    tables: Mapping[str, pd.DataFrame],
) -> list[ValidationMessage]:
    """Validate simulation-side tables and data quality rules."""
    typed_tables: dict[str, pd.DataFrame] = {}
    messages: list[ValidationMessage] = []
    for table_name, schema in SIMULATION_SCHEMAS.items():
        typed_df, schema_messages = validate_table_schema(tables.get(table_name), schema)
        messages.extend(schema_messages)
        if typed_df is not None:
            typed_tables[table_name] = typed_df

    policies = typed_tables.get("policies")
    if policies is not None:
        messages.extend(validate_policy_premiums(policies))
        messages.extend(validate_policy_exposure(policies))

    recoveries = typed_tables.get("reinsurance_recoveries")
    if recoveries is not None:
        messages.extend(validate_reinsurance_recoveries(recoveries))

    assets = typed_tables.get("asset_portfolio")
    if assets is not None:
        messages.extend(validate_asset_weights(assets))

    return messages


def validate_policy_premiums(policies: pd.DataFrame) -> list[ValidationMessage]:
    """DQ001: policy premiums must be non-negative."""
    if "written_premium" not in policies.columns or "earned_premium" not in policies.columns:
        return []
    invalid = (policies["written_premium"] < 0) | (policies["earned_premium"] < 0)
    if not invalid.any():
        return []
    return [
        error(
            "DQ001",
            "policies",
            "policy premiums must be greater than or equal to zero",
            ", ".join(policies.loc[invalid, "policy_id"].astype(str)),
        )
    ]


def validate_policy_exposure(policies: pd.DataFrame) -> list[ValidationMessage]:
    """DQ002: exposure must be in (0, 1]."""
    exposure_columns = [
        column
        for column in ("exposure", "written_exposure", "earned_exposure")
        if column in policies.columns
    ]
    if not exposure_columns:
        return []
    invalid = pd.Series(False, index=policies.index)
    for column in exposure_columns:
        invalid = invalid | (policies[column] <= 0) | (policies[column] > 1)
    if not invalid.any():
        return []
    return [
        error(
            "DQ002",
            "policies",
            "policy exposure must be greater than zero and less than or equal to one",
            ", ".join(policies.loc[invalid, "policy_id"].astype(str)),
        )
    ]


def validate_generated_policies(policies: pd.DataFrame) -> list[ValidationMessage]:
    """Validate a generated policy table without requiring other synthetic tables."""
    typed, messages = validate_table_schema(policies, GENERATED_POLICIES_SCHEMA)
    if typed is None or messages:
        return messages
    messages.extend(validate_policy_premiums(typed))
    messages.extend(validate_policy_exposure(typed))
    return messages


def validate_reinsurance_recoveries(recoveries: pd.DataFrame) -> list[ValidationMessage]:
    """DQ009: recovery must not exceed recoverable insured loss after treaty terms."""
    required = {"insured_loss", "treaty_retention", "treaty_limit", "recovery_amount", "recovery_id"}
    if not required.issubset(recoveries.columns):
        return []

    recoverable_loss = (recoveries["insured_loss"] - recoveries["treaty_retention"]).clip(lower=0)
    allowed_recovery = pd.concat([recoverable_loss, recoveries["treaty_limit"]], axis=1).min(axis=1)
    invalid = recoveries["recovery_amount"] > allowed_recovery
    if not invalid.any():
        return []
    return [
        error(
            "DQ009",
            "reinsurance_recoveries",
            "reinsurance recovery exceeds insured loss after treaty retention and limit",
            ", ".join(recoveries.loc[invalid, "recovery_id"].astype(str)),
        )
    ]


def validate_asset_weights(assets: pd.DataFrame, tolerance: float = 1e-6) -> list[ValidationMessage]:
    """DQ010: asset weights must sum to one within tolerance."""
    if "portfolio_weight" not in assets.columns:
        return []
    total_weight = float(assets["portfolio_weight"].sum())
    if abs(total_weight - 1.0) <= tolerance:
        return []
    return [
        error(
            "DQ010",
            "asset_portfolio",
            f"asset weights must sum to 1.0000 within {tolerance}; got {total_weight:.8f}",
        )
    ]
