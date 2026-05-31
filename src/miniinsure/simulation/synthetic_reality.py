"""End-to-end deterministic synthetic reality generation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import numpy as np
import pandas as pd

from miniinsure.dnb_validation import ValidationMessage, error
from miniinsure.simulation.catastrophes import simulate_catastrophe_events_and_claims
from miniinsure.simulation.claim_frequency import simulate_claim_frequency
from miniinsure.simulation.claim_reporting import apply_reporting_delay
from miniinsure.simulation.claim_settlement import VALUATION_DATE, apply_settlement_and_payments
from miniinsure.simulation.claim_severity import simulate_claim_severity
from miniinsure.simulation.policy_generator import generate_policy_data
from miniinsure.simulation.validation import validate_generated_policies
from miniinsure.utils import MASTER_SEED

HIDDEN_TRUTH_COLUMNS = {
    "truth_record_id",
    "gross_ultimate_amount",
    "insured_ultimate_amount",
    "policy_limit_amount",
    "deductible_amount",
}


@dataclass(frozen=True)
class SyntheticReality:
    """Container for generated observed data and isolated diagnostic truth."""

    policies: pd.DataFrame
    claims: pd.DataFrame
    payments: pd.DataFrame
    case_reserves: pd.DataFrame
    catastrophe_events: pd.DataFrame
    observed_valuation_snapshot: pd.DataFrame
    _synthetic_truth_diagnostics_only: pd.DataFrame
    valuation_date: pd.Timestamp = VALUATION_DATE


def derive_module_seed(master_seed: int, module_name: str) -> int:
    """Derive a stable 32-bit module seed from the master seed."""
    digest = sha256(f"{master_seed}:{module_name}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def generate_synthetic_reality(
    *,
    portfolio_mode: str = "small",
    seed: int = MASTER_SEED,
    policies_per_year: int | None = None,
    valuation_date: pd.Timestamp = VALUATION_DATE,
) -> SyntheticReality:
    """Run Policies -> Frequency -> Severity -> Reporting -> Settlement -> Observed snapshot."""
    policies = generate_policy_data(
        portfolio_mode=portfolio_mode,
        seed=seed,
        policies_per_year=policies_per_year,
    )

    frequency_rng = np.random.default_rng(derive_module_seed(seed, "claim_frequency"))
    severity_rng = np.random.default_rng(derive_module_seed(seed, "claim_severity"))
    reporting_rng = np.random.default_rng(derive_module_seed(seed, "claim_reporting"))
    catastrophe_rng = np.random.default_rng(derive_module_seed(seed, "catastrophes"))
    settlement_rng = np.random.default_rng(derive_module_seed(seed, "claim_settlement"))

    attritional_stubs = simulate_claim_frequency(policies, rng=frequency_rng)
    catastrophe_events, catastrophe_stubs = simulate_catastrophe_events_and_claims(
        policies,
        rng=catastrophe_rng,
    )
    claim_stubs = pd.concat([attritional_stubs, catastrophe_stubs], ignore_index=True)

    claim_features, truth = simulate_claim_severity(claim_stubs, rng=severity_rng)
    reported = apply_reporting_delay(claim_features, rng=reporting_rng)
    reported_visible = reported.loc[pd.to_datetime(reported["report_date"]) <= valuation_date].reset_index(drop=True)
    lifecycle = apply_settlement_and_payments(
        reported_visible,
        truth,
        rng=settlement_rng,
        valuation_date=valuation_date,
    )

    observed_snapshot = create_observed_valuation_snapshot(
        observed_claims=lifecycle.observed_claims,
        payments=lifecycle.payments,
        case_reserves=lifecycle.case_reserves,
        policies=policies,
        valuation_date=valuation_date,
    )

    return SyntheticReality(
        policies=policies,
        claims=lifecycle.observed_claims,
        payments=lifecycle.payments,
        case_reserves=lifecycle.case_reserves,
        catastrophe_events=catastrophe_events,
        observed_valuation_snapshot=observed_snapshot,
        _synthetic_truth_diagnostics_only=truth,
        valuation_date=valuation_date,
    )


def create_observed_valuation_snapshot(
    *,
    observed_claims: pd.DataFrame,
    payments: pd.DataFrame,
    case_reserves: pd.DataFrame,
    policies: pd.DataFrame,
    valuation_date: pd.Timestamp = VALUATION_DATE,
) -> pd.DataFrame:
    """Create claim-level observed modelling input as of valuation date."""
    if observed_claims.empty:
        return pd.DataFrame(
            columns=[
                "snapshot_id",
                "valuation_date",
                "claim_id",
                "policy_id",
                "accident_year",
                "claim_type",
                "coverage_type",
                "solvency_ii_lob",
                "homogeneous_risk_group",
                "claim_status",
                "paid_to_date",
                "case_reserve",
                "latest_case_estimate",
                "earned_premium",
            ]
        )

    policy_premium = policies[["policy_id", "earned_premium"]].drop_duplicates("policy_id")
    snapshot = observed_claims.merge(policy_premium, on="policy_id", how="left")
    snapshot = snapshot[
        [
            "claim_id",
            "policy_id",
            "accident_year",
            "accident_date",
            "report_date",
            "settlement_date",
            "claim_type",
            "coverage_type",
            "solvency_ii_lob",
            "homogeneous_risk_group",
            "claim_status",
            "paid_to_date",
            "case_reserve",
            "latest_case_estimate",
            "earned_premium",
            "zero_insured_flag",
            "large_loss_flag",
            "catastrophe_event_id",
        ]
    ].copy()
    snapshot.insert(0, "valuation_date", valuation_date)
    snapshot.insert(0, "snapshot_id", [f"OBS{idx:09d}" for idx in range(1, len(snapshot) + 1)])
    return snapshot


def validate_synthetic_reality(reality: SyntheticReality) -> list[ValidationMessage]:
    """Validate generated observed outputs for lifecycle consistency and truth isolation."""
    messages: list[ValidationMessage] = []
    messages.extend(validate_generated_policies(reality.policies))
    claims = reality.claims
    payments = reality.payments
    if not claims.empty:
        if (pd.to_datetime(claims["report_date"]) < pd.to_datetime(claims["accident_date"])).any():
            messages.append(error("DQ005", "claims", "report date must be on or after accident date"))
        settled = claims["settlement_date"].notna()
        if settled.any() and (
            pd.to_datetime(claims.loc[settled, "settlement_date"])
            < pd.to_datetime(claims.loc[settled, "report_date"])
        ).any():
            messages.append(error("DQ006", "claims", "settlement date must be on or after report date"))
        if not HIDDEN_TRUTH_COLUMNS.isdisjoint(set(claims.columns)):
            messages.append(error("TRUTH001", "claims", "hidden truth columns are not allowed in observed claims"))

    if not payments.empty and not claims.empty:
        joined = payments.merge(claims[["claim_id", "accident_date", "report_date"]], on="claim_id", how="left")
        if (pd.to_datetime(joined["payment_date"]) < pd.to_datetime(joined["accident_date"])).any():
            messages.append(error("DQ004", "payments", "payment date must be on or after accident date"))
        if (pd.to_datetime(joined["payment_date"]) < pd.to_datetime(joined["report_date"])).any():
            messages.append(error("DQ004", "payments", "payment date must be on or after report date"))
        if (pd.to_datetime(payments["payment_date"]) > reality.valuation_date).any():
            messages.append(error("OBS001", "payments", "future payments after valuation date are not observable"))

    for table_name, table in observed_model_inputs(reality).items():
        hidden = HIDDEN_TRUTH_COLUMNS.intersection(table.columns)
        if hidden:
            messages.append(error("TRUTH001", table_name, f"hidden truth columns present: {sorted(hidden)}"))
    return messages


def observed_model_inputs(reality: SyntheticReality) -> dict[str, pd.DataFrame]:
    """Return observed modelling inputs only, never diagnostic truth."""
    return {
        "policies": reality.policies.copy(),
        "claims": reality.claims.copy(),
        "payments": reality.payments.copy(),
        "case_reserves": reality.case_reserves.copy(),
        "catastrophe_events": reality.catastrophe_events.copy(),
        "observed_valuation_snapshot": reality.observed_valuation_snapshot.copy(),
    }


def load_synthetic_truth_for_diagnostics_only(
    reality: SyntheticReality,
    *,
    acknowledge_truth_isolation: bool = False,
) -> pd.DataFrame:
    """Load hidden synthetic truth only for diagnostics tests and never for modelling pages."""
    if not acknowledge_truth_isolation:
        raise PermissionError("synthetic truth is isolated; pass acknowledge_truth_isolation=True for diagnostics")
    return reality._synthetic_truth_diagnostics_only.copy()


def validation_summary_dict(reality: SyntheticReality) -> dict[str, Any]:
    """Return a compact validation summary for Streamlit."""
    messages = validate_synthetic_reality(reality)
    errors = [message.to_dict() for message in messages if message.severity == "error"]
    warnings = [message.to_dict() for message in messages if message.severity == "warning"]
    return {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
