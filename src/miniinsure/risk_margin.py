"""Solvency II-style cost-of-capital risk margin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from miniinsure.reserving.cashflow_projection import DEFAULT_RISK_FREE_CURVE, discount_factor_for_month

COST_OF_CAPITAL_RATE = 0.06

RUNOFF_FACTORS: dict[int, float] = {
    1: 1.00,
    2: 0.72,
    3: 0.52,
    4: 0.38,
    5: 0.27,
    6: 0.19,
    7: 0.13,
    8: 0.08,
    9: 0.04,
    10: 0.02,
}

RESERVE_RISK_FACTOR = 0.10
PREMIUM_PROVISION_RISK_FACTOR = 0.08
OPERATIONAL_RISK_FACTOR = 0.03


@dataclass(frozen=True)
class RiskMarginResult:
    """Risk margin and supporting SCR runoff table."""

    risk_margin: float
    base_scr: float
    scr_components: dict[str, float]
    runoff: pd.DataFrame


def non_hedgeable_scr_components(
    *,
    claims_provision: float,
    premium_provision: float,
    reinsurance_recoverables: float,
    gross_best_estimate: float,
    reinsurance_counterparty_pd: float = 0.005,
    reinsurance_counterparty_lgd: float = 0.50,
) -> dict[str, float]:
    """Return simple educational non-hedgeable SCR components."""
    reserve_risk = max(float(claims_provision), 0.0) * RESERVE_RISK_FACTOR
    premium_risk = abs(float(premium_provision)) * PREMIUM_PROVISION_RISK_FACTOR
    counterparty_risk = max(float(reinsurance_recoverables), 0.0) * reinsurance_counterparty_pd * reinsurance_counterparty_lgd
    operational_risk = max(float(gross_best_estimate), 0.0) * OPERATIONAL_RISK_FACTOR
    return {
        "reserve_risk": reserve_risk,
        "premium_provision_risk": premium_risk,
        "reinsurance_counterparty_risk": counterparty_risk,
        "operational_risk": operational_risk,
    }


def calculate_risk_margin(
    *,
    claims_provision: float,
    premium_provision: float,
    reinsurance_recoverables: float,
    gross_best_estimate: float,
    risk_free_curve: Mapping[float, float] | None = None,
    cost_of_capital_rate: float = COST_OF_CAPITAL_RATE,
    runoff_factors: Mapping[int, float] | None = None,
    reinsurance_counterparty_pd: float = 0.005,
    reinsurance_counterparty_lgd: float = 0.50,
) -> RiskMarginResult:
    """Calculate a cost-of-capital risk margin over the 10-year SCR runoff."""
    curve = risk_free_curve or DEFAULT_RISK_FREE_CURVE
    runoff_map = dict(runoff_factors or RUNOFF_FACTORS)
    components = non_hedgeable_scr_components(
        claims_provision=claims_provision,
        premium_provision=premium_provision,
        reinsurance_recoverables=reinsurance_recoverables,
        gross_best_estimate=gross_best_estimate,
        reinsurance_counterparty_pd=reinsurance_counterparty_pd,
        reinsurance_counterparty_lgd=reinsurance_counterparty_lgd,
    )
    base_scr = float(sum(components.values()))
    rows: list[dict[str, float]] = []
    for year, runoff_factor in sorted(runoff_map.items()):
        projected_scr = base_scr * float(runoff_factor)
        discount_factor = discount_factor_for_month(int(year) * 12, curve)
        rows.append(
            {
                "runoff_year": int(year),
                "runoff_factor": float(runoff_factor),
                "projected_scr": projected_scr,
                "cost_of_capital": projected_scr * cost_of_capital_rate,
                "discount_factor": discount_factor,
                "present_value_cost_of_capital": projected_scr * cost_of_capital_rate * discount_factor,
            }
        )
    runoff = pd.DataFrame(rows)
    return RiskMarginResult(
        risk_margin=float(runoff["present_value_cost_of_capital"].sum()) if not runoff.empty else 0.0,
        base_scr=base_scr,
        scr_components=components,
        runoff=runoff,
    )
