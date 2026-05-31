"""Premium provision for future coverage within existing contract boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.pricing import EXPENSE_RATIO
from miniinsure.reserving.cashflow_projection import DEFAULT_RISK_FREE_CURVE, add_discount_factors
from miniinsure.simulation.claim_settlement import VALUATION_DATE

UPFRONT_PREMIUM_SHARE = 0.85
MONTHLY_INSTALLMENT_PREMIUM_SHARE = 0.15
ACQUISITION_EXPENSE_RATIO = 0.12
ADMINISTRATIVE_EXPENSE_RATIO = max(EXPENSE_RATIO - ACQUISITION_EXPENSE_RATIO, 0.0)


@dataclass(frozen=True)
class PremiumProvisionResult:
    """Discounted premium provision with auditable projected cash flows."""

    cashflows: pd.DataFrame
    in_force_policies: pd.DataFrame
    summary: dict[str, float]


def calculate_unearned_exposure(
    policies: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
) -> pd.DataFrame:
    """Return policies with future unearned exposure inside current annual contracts."""
    if policies.empty:
        return pd.DataFrame(columns=[*policies.columns, "unearned_exposure", "unearned_ratio"])

    valuation = pd.Timestamp(valuation_date)
    in_force = policies.copy()
    in_force["inception_date"] = pd.to_datetime(in_force["inception_date"], errors="coerce")
    in_force["expiry_date"] = pd.to_datetime(in_force["expiry_date"], errors="coerce")
    in_force = in_force.loc[
        (in_force["inception_date"].notna())
        & (in_force["expiry_date"].notna())
        & (in_force["inception_date"] <= valuation)
        & (in_force["expiry_date"] > valuation)
    ].copy()
    if in_force.empty:
        in_force["unearned_exposure"] = pd.Series(dtype=float)
        in_force["unearned_ratio"] = pd.Series(dtype=float)
        return in_force

    total_days = (in_force["expiry_date"] - in_force["inception_date"]).dt.days.clip(lower=1)
    remaining_days = (in_force["expiry_date"] - valuation).dt.days.clip(lower=0)
    if "written_exposure" in in_force.columns:
        written_exposure = pd.to_numeric(in_force["written_exposure"], errors="coerce").fillna(1.0)
    else:
        written_exposure = pd.Series(1.0, index=in_force.index)
    in_force["unearned_ratio"] = remaining_days / total_days
    in_force["unearned_exposure"] = written_exposure * in_force["unearned_ratio"]
    return in_force.reset_index(drop=True)


def project_premium_provision_cashflows(
    policies: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Project future premium, claim, and administration cash flows."""
    in_force = calculate_unearned_exposure(policies, valuation_date=valuation_date)
    if in_force.empty:
        return _empty_cashflows(), in_force

    rows: list[dict[str, object]] = []
    for row in in_force.itertuples(index=False):
        remaining_months = _remaining_month_offsets(pd.Timestamp(row.expiry_date), valuation_date)
        if not remaining_months:
            continue
        charged_premium = float(getattr(row, "charged_premium", getattr(row, "earned_premium", 0.0)))
        loss_cost = float(getattr(row, "loss_cost", 0.65 * charged_premium))
        unearned_ratio = float(row.unearned_ratio)
        future_claims_total = loss_cost * unearned_ratio
        admin_expense_total = charged_premium * ADMINISTRATIVE_EXPENSE_RATIO * unearned_ratio
        future_installment_total = charged_premium * MONTHLY_INSTALLMENT_PREMIUM_SHARE * len(remaining_months) / 12.0
        for month_offset in remaining_months:
            share = 1.0 / len(remaining_months)
            rows.append(
                {
                    "policy_id": row.policy_id,
                    "accident_year": int(getattr(row, "accident_year", getattr(row, "underwriting_year", 0))),
                    "month_offset": int(month_offset),
                    "future_claims": float(future_claims_total * share),
                    "administrative_expenses": float(admin_expense_total * share),
                    "future_premium_inflows": float(future_installment_total * share),
                    "cashflow": float((future_claims_total + admin_expense_total - future_installment_total) * share),
                }
            )
    if not rows:
        return _empty_cashflows(), in_force
    return pd.DataFrame(rows).sort_values(["policy_id", "month_offset"]).reset_index(drop=True), in_force


def calculate_premium_provision(
    policies: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    risk_free_curve: Mapping[float, float] | None = None,
) -> PremiumProvisionResult:
    """Calculate the premium provision; negative values are allowed."""
    curve = risk_free_curve or DEFAULT_RISK_FREE_CURVE
    undiscounted, in_force = project_premium_provision_cashflows(
        policies,
        valuation_date=valuation_date,
    )
    cashflows = add_discount_factors(undiscounted, curve=curve)
    summary = {
        "in_force_policy_count": float(len(in_force)),
        "unearned_exposure": float(in_force["unearned_exposure"].sum()) if not in_force.empty else 0.0,
        "future_claims": float(cashflows["future_claims"].sum()) if not cashflows.empty else 0.0,
        "administrative_expenses": float(cashflows["administrative_expenses"].sum()) if not cashflows.empty else 0.0,
        "future_premium_inflows": float(cashflows["future_premium_inflows"].sum()) if not cashflows.empty else 0.0,
        "present_value": float(cashflows["present_value"].sum()) if not cashflows.empty else 0.0,
    }
    return PremiumProvisionResult(cashflows=cashflows, in_force_policies=in_force, summary=summary)


def _remaining_month_offsets(expiry_date: pd.Timestamp, valuation_date: pd.Timestamp) -> list[int]:
    valuation = pd.Timestamp(valuation_date)
    expiry = pd.Timestamp(expiry_date)
    if expiry <= valuation:
        return []
    months = max((expiry.year - valuation.year) * 12 + expiry.month - valuation.month, 1)
    return list(range(1, months + 1))


def _empty_cashflows() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "policy_id",
            "accident_year",
            "month_offset",
            "future_claims",
            "administrative_expenses",
            "future_premium_inflows",
            "cashflow",
        ]
    )
