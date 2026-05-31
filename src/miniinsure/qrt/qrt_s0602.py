"""Mock S.06.02.01 asset holdings template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate(capital: CapitalWorkflowResult) -> pd.DataFrame:
    """Generate asset holdings from the ALM asset portfolio."""
    assets = capital.standard_formula.asset_portfolio
    if assets is None or assets.empty:
        return add_currency(pd.DataFrame())
    qrt = assets.copy().reset_index(drop=True)
    qrt.insert(0, "holding_id", [f"AST{idx:04d}" for idx in range(1, len(qrt) + 1)])
    qrt["asset_description"] = qrt["asset_class"].str.replace("_", " ").str.title()
    qrt["market_value"] = qrt["market_value"].apply(eur)
    qrt["source_field"] = "standard_formula.asset_portfolio"
    return add_currency(
        qrt[
            [
                "holding_id",
                "asset_class",
                "asset_description",
                "weight",
                "market_value",
                "interest_duration",
                "spread_duration",
                "expected_return",
                "volatility",
                "source_field",
            ]
        ]
    )
