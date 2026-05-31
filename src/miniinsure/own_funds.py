"""Own funds and Solvency II balance sheet helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BalanceSheetResult:
    """Opening Solvency II-style balance sheet."""

    summary: dict[str, float | str | bool]
    own_funds_tiers: pd.DataFrame


def one_year_own_funds_movement(
    *,
    of0: float,
    nep: float,
    net_claims: float,
    reserve_loss: float,
    expenses: float,
    investment_result: float,
    operational_loss: float,
    credit_loss: float,
) -> float:
    """OF1 = OF0 + NEP - net_claims - reserve_loss - expenses + investment_result - op - credit."""
    return float(
        float(of0)
        + float(nep)
        - float(net_claims)
        - float(reserve_loss)
        - float(expenses)
        + float(investment_result)
        - float(operational_loss)
        - float(credit_loss)
    )


def opening_balance_sheet(
    *,
    technical_provisions: float,
    other_liabilities: float,
    scr: float,
) -> BalanceSheetResult:
    """Opening liabilities, assets, and unrestricted Tier 1 own funds."""
    liabilities = float(technical_provisions) + float(other_liabilities)
    own_funds = 1.40 * float(scr)
    assets = liabilities + own_funds
    summary = {
        "assets": assets,
        "liabilities": liabilities,
        "technical_provisions": float(technical_provisions),
        "other_liabilities": float(other_liabilities),
        "own_funds": own_funds,
        "eligible_own_funds": own_funds,
        "tier_1_unrestricted": own_funds,
        "scr": float(scr),
        "reconciliation_difference": assets - liabilities - own_funds,
        "reconciliation_status": "pass" if abs(assets - liabilities - own_funds) <= 0.01 else "fail",
        "reconciles": abs(assets - liabilities - own_funds) <= 0.01,
    }
    tiers = pd.DataFrame(
        [
            {
                "tier": "Tier 1 unrestricted",
                "amount": own_funds,
                "eligible": own_funds,
            }
        ]
    )
    return BalanceSheetResult(summary=summary, own_funds_tiers=tiers)


def own_funds_summary(
    *,
    assets: float,
    liabilities: float,
    scr: float,
    mcr: float,
) -> dict[str, float]:
    """Calculate excess assets, eligible own funds, and coverage ratios."""
    excess = float(assets) - float(liabilities)
    eligible = excess
    return {
        "excess_assets_over_liabilities": excess,
        "eligible_own_funds": eligible,
        "tier_1_unrestricted": eligible,
        "solvency_ratio": eligible / float(scr) if scr > 0 else float("inf"),
        "mcr_ratio": eligible / float(mcr) if mcr > 0 else float("inf"),
    }
