"""Asset-liability management summaries for MiniInsure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.simulation.economic_scenarios import (
    bond_return,
    cash_return,
    deterministic_equity_return,
    discount_factor_for_month,
    interpolate_risk_free_rate,
)

ASSET_WEIGHTS = {
    "cash": 0.15,
    "short_bonds": 0.50,
    "long_bonds": 0.25,
    "equities": 0.10,
}

SHORT_BOND_DURATION = 2.0
LONG_BOND_DURATION = 7.0
SPREAD_DURATION_RATIO = 0.80
EQUITY_EXPECTED_RETURN = 0.065
EQUITY_VOLATILITY = 0.18


@dataclass(frozen=True)
class ALMSummary:
    """ALM summary tables."""

    asset_allocation: pd.DataFrame
    liability_cashflow_profile: pd.DataFrame
    liquidity_gap: pd.DataFrame
    duration_gap: pd.DataFrame
    market_stresses: pd.DataFrame


def calibrate_asset_portfolio(
    *,
    opening_liabilities: float,
    scr: float,
) -> pd.DataFrame:
    """Calibrate opening assets as liabilities plus 1.40 times SCR."""
    opening_assets = float(opening_liabilities) + 1.40 * float(scr)
    rows = [
        {
            "asset_class": "cash",
            "weight": ASSET_WEIGHTS["cash"],
            "market_value": opening_assets * ASSET_WEIGHTS["cash"],
            "interest_duration": 0.0,
            "spread_duration": 0.0,
            "expected_return": cash_return(),
            "volatility": 0.0,
        },
        {
            "asset_class": "short_bonds",
            "weight": ASSET_WEIGHTS["short_bonds"],
            "market_value": opening_assets * ASSET_WEIGHTS["short_bonds"],
            "interest_duration": SHORT_BOND_DURATION,
            "spread_duration": SHORT_BOND_DURATION * SPREAD_DURATION_RATIO,
            "expected_return": interpolate_risk_free_rate(SHORT_BOND_DURATION),
            "volatility": 0.0,
        },
        {
            "asset_class": "long_bonds",
            "weight": ASSET_WEIGHTS["long_bonds"],
            "market_value": opening_assets * ASSET_WEIGHTS["long_bonds"],
            "interest_duration": LONG_BOND_DURATION,
            "spread_duration": LONG_BOND_DURATION * SPREAD_DURATION_RATIO,
            "expected_return": interpolate_risk_free_rate(LONG_BOND_DURATION),
            "volatility": 0.0,
        },
        {
            "asset_class": "equities",
            "weight": ASSET_WEIGHTS["equities"],
            "market_value": opening_assets * ASSET_WEIGHTS["equities"],
            "interest_duration": 0.0,
            "spread_duration": 0.0,
            "expected_return": EQUITY_EXPECTED_RETURN,
            "volatility": EQUITY_VOLATILITY,
        },
    ]
    return pd.DataFrame(rows)


def combine_liability_cashflows(
    *,
    claims_cashflows: pd.DataFrame,
    premium_cashflows: pd.DataFrame,
    reinsurance_cashflows: pd.DataFrame,
) -> pd.DataFrame:
    """Combine liability cash flows as monthly net outflows."""
    frames: list[pd.DataFrame] = []
    if not claims_cashflows.empty:
        frames.append(
            claims_cashflows[["month_offset", "cashflow"]]
            .assign(source="claims_provision")
        )
    if not premium_cashflows.empty:
        frames.append(
            premium_cashflows[["month_offset", "cashflow"]]
            .assign(source="premium_provision")
        )
    if not reinsurance_cashflows.empty:
        frames.append(
            reinsurance_cashflows[["month_offset", "default_adjusted_recoverable"]]
            .rename(columns={"default_adjusted_recoverable": "cashflow"})
            .assign(source="reinsurance_recoverable", cashflow=lambda df: -df["cashflow"])
        )
    if not frames:
        return pd.DataFrame(columns=["source", "month_offset", "cashflow"])
    return pd.concat(frames, ignore_index=True)[["source", "month_offset", "cashflow"]]


def liability_cashflow_profile(liability_cashflows: pd.DataFrame) -> pd.DataFrame:
    """Summarize liability cash flows by maturity bucket."""
    if liability_cashflows.empty:
        return pd.DataFrame(columns=["maturity_bucket", "month_start", "month_end", "undiscounted_cashflow", "present_value"])
    cashflows = liability_cashflows.copy()
    cashflows["month_offset"] = cashflows["month_offset"].astype(int)
    cashflows["discount_factor"] = cashflows["month_offset"].apply(discount_factor_for_month)
    cashflows["present_value"] = cashflows["cashflow"].astype(float) * cashflows["discount_factor"]
    cashflows["maturity_bucket"] = cashflows["month_offset"].apply(_maturity_bucket)
    grouped = (
        cashflows.groupby("maturity_bucket", as_index=False)
        .agg(
            month_start=("month_offset", "min"),
            month_end=("month_offset", "max"),
            undiscounted_cashflow=("cashflow", "sum"),
            present_value=("present_value", "sum"),
        )
    )
    bucket_order = {"0-12 months": 0, "13-36 months": 1, "37+ months": 2}
    grouped["bucket_order"] = grouped["maturity_bucket"].map(bucket_order)
    return grouped.sort_values("bucket_order").drop(columns="bucket_order").reset_index(drop=True)


def liquidity_gap_summary(
    asset_allocation: pd.DataFrame,
    liability_cashflows: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate simple 12-month liquidity gap."""
    liquid_assets = float(
        asset_allocation.loc[
            asset_allocation["asset_class"].isin(["cash", "short_bonds"]),
            "market_value",
        ].sum()
    )
    due_12_months = (
        float(liability_cashflows.loc[liability_cashflows["month_offset"] <= 12, "cashflow"].sum())
        if not liability_cashflows.empty
        else 0.0
    )
    return pd.DataFrame(
        [
            {
                "liquid_assets_12m": liquid_assets,
                "liability_outflows_12m": due_12_months,
                "liquidity_gap": liquid_assets - due_12_months,
                "liquidity_coverage_ratio": liquid_assets / due_12_months if due_12_months > 0 else np.inf,
            }
        ]
    )


def duration_gap_summary(
    asset_allocation: pd.DataFrame,
    liability_cashflows: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate weighted asset duration, liability duration, and duration gap."""
    total_assets = float(asset_allocation["market_value"].sum())
    asset_duration = (
        float((asset_allocation["market_value"] * asset_allocation["interest_duration"]).sum() / total_assets)
        if total_assets > 0
        else 0.0
    )
    if liability_cashflows.empty:
        liability_duration = 0.0
    else:
        cf = liability_cashflows.copy()
        cf["month_offset"] = cf["month_offset"].astype(float)
        cf["discount_factor"] = cf["month_offset"].apply(discount_factor_for_month)
        cf["present_value"] = cf["cashflow"].astype(float) * cf["discount_factor"]
        liability_pv = float(cf["present_value"].sum())
        liability_duration = (
            float(((cf["month_offset"] / 12.0) * cf["present_value"]).sum() / liability_pv)
            if liability_pv > 0
            else 0.0
        )
    return pd.DataFrame(
        [
            {
                "asset_duration": asset_duration,
                "liability_duration": liability_duration,
                "duration_gap": asset_duration - liability_duration,
            }
        ]
    )


def market_stress_outputs(asset_allocation: pd.DataFrame) -> pd.DataFrame:
    """Apply simple market stresses to the asset portfolio."""
    return pd.DataFrame(
        [
            _stress_row(asset_allocation, "base", interest_rate_change=0.0, spread_change=0.0, equity_return_value=EQUITY_EXPECTED_RETURN),
            _stress_row(asset_allocation, "interest_rate_up_100bp", interest_rate_change=0.01, spread_change=0.0, equity_return_value=EQUITY_EXPECTED_RETURN),
            _stress_row(asset_allocation, "spread_widening_100bp", interest_rate_change=0.0, spread_change=0.01, equity_return_value=EQUITY_EXPECTED_RETURN),
            _stress_row(asset_allocation, "equity_down_30pct", interest_rate_change=0.0, spread_change=0.0, equity_return_value=-0.30),
            _stress_row(asset_allocation, "combined_downside", interest_rate_change=0.01, spread_change=0.01, equity_return_value=-0.30),
        ]
    )


def alm_summary(
    *,
    opening_liabilities: float,
    scr: float,
    liability_cashflows: pd.DataFrame,
) -> ALMSummary:
    """Build all ALM summary tables."""
    assets = calibrate_asset_portfolio(opening_liabilities=opening_liabilities, scr=scr)
    return ALMSummary(
        asset_allocation=assets,
        liability_cashflow_profile=liability_cashflow_profile(liability_cashflows),
        liquidity_gap=liquidity_gap_summary(assets, liability_cashflows),
        duration_gap=duration_gap_summary(assets, liability_cashflows),
        market_stresses=market_stress_outputs(assets),
    )


def _stress_row(
    asset_allocation: pd.DataFrame,
    stress_name: str,
    *,
    interest_rate_change: float,
    spread_change: float,
    equity_return_value: float,
) -> dict[str, float | str]:
    stressed = asset_allocation.copy()
    returns = []
    for row in stressed.itertuples(index=False):
        if row.asset_class == "cash":
            returns.append(cash_return())
        elif row.asset_class in {"short_bonds", "long_bonds"}:
            returns.append(
                bond_return(
                    yield_rate=float(row.expected_return),
                    duration=float(row.interest_duration),
                    interest_rate_change=interest_rate_change,
                    spread_change=spread_change,
                )
            )
        else:
            returns.append(deterministic_equity_return(equity_return_value))
    stressed["stress_return"] = returns
    stressed["stressed_value"] = stressed["market_value"] * (1.0 + stressed["stress_return"])
    opening_assets = float(stressed["market_value"].sum())
    stressed_assets = float(stressed["stressed_value"].sum())
    return {
        "stress": stress_name,
        "opening_assets": opening_assets,
        "stressed_assets": stressed_assets,
        "asset_impact": stressed_assets - opening_assets,
        "portfolio_return": stressed_assets / opening_assets - 1.0 if opening_assets > 0 else 0.0,
    }


def _maturity_bucket(month_offset: int) -> str:
    if month_offset <= 12:
        return "0-12 months"
    if month_offset <= 36:
        return "13-36 months"
    return "37+ months"
