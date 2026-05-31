"""Solvency II-style technical provisions from observed deterministic reserving outputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from miniinsure.reserving.cashflow_projection import DEFAULT_RISK_FREE_CURVE, discount_factor_for_month
from miniinsure.reserving.claims_provision import ClaimsProvisionResult, calculate_claims_provision
from miniinsure.reserving.premium_provision import PremiumProvisionResult, calculate_premium_provision
from miniinsure.risk_margin import RiskMarginResult, calculate_risk_margin
from miniinsure.simulation.reinsurance_simulation import (
    ReinsuranceProgram,
    ReinsuranceResult,
    apply_default_reinsurance_program,
)
from miniinsure.simulation.claim_settlement import VALUATION_DATE

VALUATION_TOLERANCE = 0.01


@dataclass(frozen=True)
class ReinsuranceRecoverablesResult:
    """Discounted default-adjusted reinsurance recoverables."""

    reinsurance_result: ReinsuranceResult
    cashflows: pd.DataFrame
    summary: dict[str, float]


@dataclass(frozen=True)
class TechnicalProvisionsResult:
    """Gross and net technical provisions with reconciliation status."""

    claims_provision: ClaimsProvisionResult
    premium_provision: PremiumProvisionResult
    reinsurance_recoverables: ReinsuranceRecoverablesResult
    risk_margin: RiskMarginResult
    summary: dict[str, float | bool | str]


def calculate_reinsurance_recoverables(
    reserving_results: pd.DataFrame,
    policies: pd.DataFrame,
    *,
    program: ReinsuranceProgram | None = None,
    risk_free_curve: Mapping[float, float] | None = None,
) -> ReinsuranceRecoverablesResult:
    """Calculate discounted default-adjusted recoverables on selected future reserves."""
    treaty = program or ReinsuranceProgram()
    curve = risk_free_curve or DEFAULT_RISK_FREE_CURVE
    pseudo_claims = _reserving_rows_as_reinsurance_claims(reserving_results)
    result = apply_default_reinsurance_program(
        pseudo_claims,
        policies,
        program=treaty,
        loss_column="selected_reserve",
    )
    if result.annual_level.empty:
        cashflows = _empty_reinsurance_cashflows()
    else:
        cashflows = result.annual_level[["accident_year", "default_adjusted_recoverable"]].copy()
        cashflows["month_offset"] = treaty.recovery_delay_months
        cashflows["discount_factor"] = discount_factor_for_month(treaty.recovery_delay_months, curve)
        cashflows["present_value"] = cashflows["default_adjusted_recoverable"] * cashflows["discount_factor"]
    summary = {
        "undiscounted_recoverable": float(cashflows["default_adjusted_recoverable"].sum()) if not cashflows.empty else 0.0,
        "present_value": float(cashflows["present_value"].sum()) if not cashflows.empty else 0.0,
    }
    return ReinsuranceRecoverablesResult(reinsurance_result=result, cashflows=cashflows, summary=summary)


def calculate_technical_provisions(
    reserving_results: pd.DataFrame,
    policies: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    risk_free_curve: Mapping[float, float] | None = None,
    reinsurance_program: ReinsuranceProgram | None = None,
    valuation_tolerance: float = VALUATION_TOLERANCE,
) -> TechnicalProvisionsResult:
    """Calculate claims provision, premium provision, recoverables, risk margin, and TP views."""
    curve = risk_free_curve or DEFAULT_RISK_FREE_CURVE
    claims = calculate_claims_provision(reserving_results, risk_free_curve=curve)
    premium = calculate_premium_provision(
        policies,
        valuation_date=valuation_date,
        risk_free_curve=curve,
    )
    recoverables = calculate_reinsurance_recoverables(
        reserving_results,
        policies,
        program=reinsurance_program,
        risk_free_curve=curve,
    )
    gross_best_estimate = claims.summary["present_value"] + premium.summary["present_value"]
    net_best_estimate = gross_best_estimate - recoverables.summary["present_value"]
    risk_margin = calculate_risk_margin(
        claims_provision=claims.summary["present_value"],
        premium_provision=premium.summary["present_value"],
        reinsurance_recoverables=recoverables.summary["present_value"],
        gross_best_estimate=gross_best_estimate,
        risk_free_curve=curve,
        reinsurance_counterparty_pd=(reinsurance_program or ReinsuranceProgram()).counterparty_default_pd,
        reinsurance_counterparty_lgd=(reinsurance_program or ReinsuranceProgram()).counterparty_lgd,
    )
    gross_technical_provisions = gross_best_estimate + risk_margin.risk_margin
    net_technical_provisions = net_best_estimate + risk_margin.risk_margin
    reconciliation_difference = gross_technical_provisions - recoverables.summary["present_value"] - net_technical_provisions
    reconciles = abs(reconciliation_difference) <= valuation_tolerance
    summary: dict[str, float | bool | str] = {
        "claims_provision": claims.summary["present_value"],
        "premium_provision": premium.summary["present_value"],
        "reinsurance_recoverables": recoverables.summary["present_value"],
        "gross_best_estimate": gross_best_estimate,
        "net_best_estimate": net_best_estimate,
        "risk_margin": risk_margin.risk_margin,
        "gross_technical_provisions": gross_technical_provisions,
        "net_technical_provisions": net_technical_provisions,
        "reconciliation_difference": reconciliation_difference,
        "valuation_tolerance": float(valuation_tolerance),
        "reconciliation_status": "pass" if reconciles else "fail",
        "reconciles": reconciles,
    }
    return TechnicalProvisionsResult(
        claims_provision=claims,
        premium_provision=premium,
        reinsurance_recoverables=recoverables,
        risk_margin=risk_margin,
        summary=summary,
    )


def valuation_reconciles(
    actual: float,
    expected: float,
    *,
    tolerance: float = VALUATION_TOLERANCE,
) -> bool:
    """Return whether two valuation amounts reconcile within tolerance."""
    return abs(float(actual) - float(expected)) <= float(tolerance)


def _reserving_rows_as_reinsurance_claims(reserving_results: pd.DataFrame) -> pd.DataFrame:
    if reserving_results.empty:
        return pd.DataFrame(columns=["claim_id", "accident_year", "selected_reserve"])
    claims = reserving_results.copy()
    claims["claim_id"] = [
        f"TP{idx:09d}"
        for idx in range(1, len(claims) + 1)
    ]
    if "accident_year" not in claims.columns and "origin_year" in claims.columns:
        claims["accident_year"] = claims["origin_year"]
    claims["selected_reserve"] = claims["selected_reserve"].clip(lower=0.0)
    return claims[
        [
            "claim_id",
            "accident_year",
            "selected_reserve",
            "solvency_ii_lob",
            "homogeneous_risk_group",
        ]
    ]


def _empty_reinsurance_cashflows() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "accident_year",
            "default_adjusted_recoverable",
            "month_offset",
            "discount_factor",
            "present_value",
        ]
    )
