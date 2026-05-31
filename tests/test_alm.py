from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from miniinsure.alm import (
    alm_summary,
    calibrate_asset_portfolio,
    combine_liability_cashflows,
    duration_gap_summary,
    liability_cashflow_profile,
    liquidity_gap_summary,
    market_stress_outputs,
)


def liability_cashflows_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["claims", "claims", "premium", "reinsurance"],
            "month_offset": [6, 24, 3, 3],
            "cashflow": [100.0, 200.0, -30.0, -20.0],
        }
    )


def test_asset_weights_sum_to_one() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=100.0)

    assert assets["weight"].sum() == pytest.approx(1.0)


def test_asset_calibration_formula() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=100.0)

    assert assets["market_value"].sum() == pytest.approx(1_140.0)
    assert assets.loc[assets["asset_class"] == "short_bonds", "interest_duration"].iloc[0] == 2.0
    assert assets.loc[assets["asset_class"] == "long_bonds", "spread_duration"].iloc[0] == pytest.approx(5.6)


def test_combine_liability_cashflows() -> None:
    claims = pd.DataFrame({"month_offset": [6], "cashflow": [100.0]})
    premium = pd.DataFrame({"month_offset": [3], "cashflow": [-30.0]})
    reinsurance = pd.DataFrame({"month_offset": [3], "default_adjusted_recoverable": [20.0]})

    combined = combine_liability_cashflows(
        claims_cashflows=claims,
        premium_cashflows=premium,
        reinsurance_cashflows=reinsurance,
    )

    assert combined["cashflow"].sum() == 50.0
    assert set(combined["source"]) == {"claims_provision", "premium_provision", "reinsurance_recoverable"}


def test_alm_summary_outputs_required_fields() -> None:
    summary = alm_summary(
        opening_liabilities=1_000.0,
        scr=100.0,
        liability_cashflows=liability_cashflows_fixture(),
    )

    assert {"asset_class", "weight", "market_value", "interest_duration", "spread_duration"}.issubset(
        summary.asset_allocation.columns
    )
    assert {"maturity_bucket", "undiscounted_cashflow", "present_value"}.issubset(
        summary.liability_cashflow_profile.columns
    )
    assert {"liquid_assets_12m", "liability_outflows_12m", "liquidity_gap"}.issubset(
        summary.liquidity_gap.columns
    )
    assert {"asset_duration", "liability_duration", "duration_gap"}.issubset(summary.duration_gap.columns)
    assert {"stress", "opening_assets", "stressed_assets", "asset_impact", "portfolio_return"}.issubset(
        summary.market_stresses.columns
    )


def test_liquidity_gap_and_duration_gap_are_numeric() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=100.0)
    liquidity = liquidity_gap_summary(assets, liability_cashflows_fixture())
    duration = duration_gap_summary(assets, liability_cashflows_fixture())

    assert np.isfinite(liquidity.loc[0, "liquidity_gap"])
    assert np.isfinite(duration.loc[0, "duration_gap"])


def test_market_stress_outputs() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=100.0)
    stresses = market_stress_outputs(assets)

    assert "combined_downside" in set(stresses["stress"])
    assert (
        stresses.loc[stresses["stress"] == "combined_downside", "stressed_assets"].iloc[0]
        < stresses.loc[stresses["stress"] == "base", "stressed_assets"].iloc[0]
    )


def test_liability_cashflow_profile_buckets() -> None:
    profile = liability_cashflow_profile(liability_cashflows_fixture())

    assert set(profile["maturity_bucket"]) == {"0-12 months", "13-36 months"}
