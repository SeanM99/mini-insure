"""Simple market stress tests used by capital calculations."""

from __future__ import annotations

import pandas as pd

from miniinsure.risk_engine.aggregation import aggregate_with_correlation

EQUITY_SHOCK = 0.39
INTEREST_RATE_SHOCK = 0.01
SPREAD_SHOCK = 0.01


def equity_shock_loss(asset_portfolio: pd.DataFrame, shock: float = EQUITY_SHOCK) -> float:
    """Own-funds loss from a fall in equity values."""
    equity_value = float(asset_portfolio.loc[asset_portfolio["asset_class"] == "equities", "market_value"].sum())
    return equity_value * float(shock)


def interest_rate_shock_loss(
    asset_portfolio: pd.DataFrame,
    shock: float = INTEREST_RATE_SHOCK,
) -> dict[str, float]:
    """Take the worse own-funds impact of +100 bps and -100 bps asset shocks."""
    bond_assets = asset_portfolio.loc[asset_portfolio["asset_class"].isin(["short_bonds", "long_bonds"])]
    up_loss = float((bond_assets["market_value"] * bond_assets["interest_duration"] * shock).sum())
    down_loss = float((bond_assets["market_value"] * bond_assets["interest_duration"] * -shock).sum())
    worse_loss = max(up_loss, down_loss, 0.0)
    return {
        "interest_rate_up_loss": up_loss,
        "interest_rate_down_loss": down_loss,
        "interest_rate_scr": worse_loss,
    }


def spread_shock_loss(asset_portfolio: pd.DataFrame, shock: float = SPREAD_SHOCK) -> float:
    """Own-funds loss from a +100 bps credit-spread widening."""
    bond_assets = asset_portfolio.loc[asset_portfolio["asset_class"].isin(["short_bonds", "long_bonds"])]
    return float((bond_assets["market_value"] * bond_assets["spread_duration"] * shock).sum())


def market_risk_stress_summary(asset_portfolio: pd.DataFrame) -> pd.DataFrame:
    """Return simple market stress charges before and after aggregation."""
    equity = equity_shock_loss(asset_portfolio)
    interest = interest_rate_shock_loss(asset_portfolio)
    spread = spread_shock_loss(asset_portfolio)
    charges = {
        "equity": equity,
        "interest": interest["interest_rate_scr"],
        "spread": spread,
        "currency": 0.0,
        "concentration": 0.0,
    }
    corr = market_correlation_matrix()
    aggregate = aggregate_with_correlation(charges, corr)
    return pd.DataFrame(
        [
            {
                **charges,
                **interest,
                "market_scr": aggregate,
            }
        ]
    )


def market_correlation_matrix() -> pd.DataFrame:
    """Return simplified market-risk correlations."""
    names = ["equity", "interest", "spread", "currency", "concentration"]
    matrix = pd.DataFrame(0.0, index=names, columns=names)
    for name in names:
        matrix.loc[name, name] = 1.0
    matrix.loc["equity", "spread"] = 0.50
    matrix.loc["spread", "equity"] = 0.50
    matrix.loc["interest", "spread"] = 0.25
    matrix.loc["spread", "interest"] = 0.25
    return matrix
