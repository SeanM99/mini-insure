"""Claims provision cash-flow projection for already incurred obligations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.reserving.cashflow_projection import DEFAULT_RISK_FREE_CURVE, add_discount_factors

ALLOCATED_LOSS_ADJUSTMENT_EXPENSE_RATE = 0.04
UNALLOCATED_LOSS_ADJUSTMENT_EXPENSE_RATE = 0.02

CLAIM_TYPE_PAYMENT_PATTERNS: dict[str, tuple[tuple[int, float], ...]] = {
    "liability_property_damage": ((3, 0.45), (6, 0.70), (12, 0.90), (24, 1.00)),
    "own_damage_attritional": ((2, 0.55), (4, 0.80), (8, 0.95), (12, 1.00)),
    "theft_fire": ((3, 0.35), (6, 0.65), (12, 0.90), (18, 1.00)),
    "attritional_bi": ((12, 0.20), (24, 0.50), (36, 0.75), (60, 1.00)),
    "large_bi": ((12, 0.05), (24, 0.20), (48, 0.45), (72, 0.70), (120, 1.00)),
    "catastrophe_allocated": ((3, 0.40), (6, 0.70), (12, 0.90), (18, 1.00)),
    "attritional": ((6, 0.50), (12, 0.80), (24, 1.00)),
}


@dataclass(frozen=True)
class ClaimsProvisionResult:
    """Discounted claims provision with auditable projected cash flows."""

    cashflows: pd.DataFrame
    summary: dict[str, float]


def future_claim_cashflow_shares(
    claim_type: str,
    paid_percentage: float,
) -> pd.DataFrame:
    """Return future monthly shares conditional on the paid percentage at valuation."""
    pattern = CLAIM_TYPE_PAYMENT_PATTERNS.get(claim_type, CLAIM_TYPE_PAYMENT_PATTERNS["attritional"])
    paid = float(np.clip(paid_percentage, 0.0, 1.0))
    remaining = 1.0 - paid
    if remaining <= 0.0:
        return pd.DataFrame(columns=["month_offset", "share"])

    rows: list[dict[str, float]] = []
    previous_clamped = paid
    for month_offset, cumulative_share in pattern:
        clamped = max(float(cumulative_share), paid)
        incremental = max(clamped - previous_clamped, 0.0)
        if incremental > 0.0:
            rows.append({"month_offset": int(month_offset), "share": incremental / remaining})
        previous_clamped = clamped

    projected = pd.DataFrame(rows)
    if projected.empty:
        return pd.DataFrame([{"month_offset": int(pattern[-1][0]), "share": 1.0}])
    projected["share"] = projected["share"] / projected["share"].sum()
    return projected


def project_claims_cashflows(
    reserving_results: pd.DataFrame,
) -> pd.DataFrame:
    """Project undiscounted monthly claim and claims handling expense cash flows."""
    if reserving_results.empty:
        return _empty_cashflows()

    rows: list[dict[str, object]] = []
    for row in reserving_results.itertuples(index=False):
        unpaid_loss = max(float(row.selected_reserve), 0.0)
        if unpaid_loss <= 0.0:
            continue
        selected_ultimate = max(float(row.selected_ultimate), 0.0)
        paid_percentage = 1.0 if selected_ultimate <= 0.0 else float(row.latest_paid) / selected_ultimate
        shares = future_claim_cashflow_shares(str(row.claim_type_basis), paid_percentage)
        for share_row in shares.itertuples(index=False):
            loss_payment = unpaid_loss * float(share_row.share)
            alae = loss_payment * ALLOCATED_LOSS_ADJUSTMENT_EXPENSE_RATE
            ulae = loss_payment * UNALLOCATED_LOSS_ADJUSTMENT_EXPENSE_RATE
            rows.append(
                {
                    "solvency_ii_lob": row.solvency_ii_lob,
                    "homogeneous_risk_group": row.homogeneous_risk_group,
                    "origin_year": int(row.origin_year),
                    "claim_type_basis": row.claim_type_basis,
                    "month_offset": int(share_row.month_offset),
                    "loss_payment": float(loss_payment),
                    "allocated_loss_adjustment_expense": float(alae),
                    "unallocated_loss_adjustment_expense": float(ulae),
                    "cashflow": float(loss_payment + alae + ulae),
                }
            )
    if not rows:
        return _empty_cashflows()
    return pd.DataFrame(rows).sort_values(
        ["solvency_ii_lob", "homogeneous_risk_group", "origin_year", "month_offset"]
    ).reset_index(drop=True)


def calculate_claims_provision(
    reserving_results: pd.DataFrame,
    *,
    risk_free_curve: Mapping[float, float] | None = None,
) -> ClaimsProvisionResult:
    """Calculate the discounted claims provision for incurred obligations."""
    curve = risk_free_curve or DEFAULT_RISK_FREE_CURVE
    cashflows = add_discount_factors(project_claims_cashflows(reserving_results), curve=curve)
    summary = {
        "undiscounted_loss_payments": float(cashflows["loss_payment"].sum()) if not cashflows.empty else 0.0,
        "allocated_loss_adjustment_expense": (
            float(cashflows["allocated_loss_adjustment_expense"].sum()) if not cashflows.empty else 0.0
        ),
        "unallocated_loss_adjustment_expense": (
            float(cashflows["unallocated_loss_adjustment_expense"].sum()) if not cashflows.empty else 0.0
        ),
        "undiscounted_cashflows": float(cashflows["cashflow"].sum()) if not cashflows.empty else 0.0,
        "present_value": float(cashflows["present_value"].sum()) if not cashflows.empty else 0.0,
    }
    return ClaimsProvisionResult(cashflows=cashflows, summary=summary)


def _empty_cashflows() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "solvency_ii_lob",
            "homogeneous_risk_group",
            "origin_year",
            "claim_type_basis",
            "month_offset",
            "loss_payment",
            "allocated_loss_adjustment_expense",
            "unallocated_loss_adjustment_expense",
            "cashflow",
        ]
    )
