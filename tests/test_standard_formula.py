from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from miniinsure.standard_formula import (
    bscr_aggregation,
    catastrophe_scr,
    counterparty_default_scr,
    non_life_premium_reserve_scr,
    operational_scr,
    simplified_standard_formula_scr,
)


def asset_portfolio_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "asset_class": ["cash", "short_bonds", "long_bonds", "equities"],
            "market_value": [150.0, 500.0, 250.0, 100.0],
            "interest_duration": [0.0, 2.0, 7.0, 0.0],
            "spread_duration": [0.0, 1.6, 5.6, 0.0],
            "expected_return": [0.02, 0.026, 0.03, 0.065],
        }
    )


def test_non_life_premium_reserve_scr_formula() -> None:
    scr, by_lob = non_life_premium_reserve_scr(
        {"Motor vehicle liability": 100.0, "Other motor insurance": 200.0},
        {"Motor vehicle liability": 50.0, "Other motor insurance": 100.0},
    )

    motor = 3 * 0.10 * 150.0
    other = 3 * 0.08 * 300.0
    assert by_lob.set_index("solvency_ii_lob").loc["Motor vehicle liability", "scr_pr_lob"] == pytest.approx(motor)
    assert scr == pytest.approx(np.sqrt(motor**2 + other**2 + 2 * 0.50 * motor * other))


def test_catastrophe_scr_formula() -> None:
    losses = pd.Series([0.0, 10.0, 20.0, 100.0])

    assert catastrophe_scr(losses) == pytest.approx(np.quantile(losses, 0.995) - losses.mean())


def test_market_shocks_and_aggregation() -> None:
    result = simplified_standard_formula_scr(
        nep_by_lob={"Other motor insurance": 100.0},
        net_claims_be_by_lob={"Other motor insurance": 50.0},
        net_catastrophe_losses=[0.0],
        asset_portfolio=asset_portfolio_fixture(),
        reinsurance_recoverables=0.0,
        nep=100.0,
        net_technical_provisions=50.0,
    )

    market = result.market.iloc[0]
    assert market["equity"] == pytest.approx(39.0)
    assert market["interest_rate_scr"] == pytest.approx((500.0 * 2.0 + 250.0 * 7.0) * 0.01)
    assert market["spread"] == pytest.approx((500.0 * 1.6 + 250.0 * 5.6) * 0.01)
    assert market["market_scr"] > max(market["equity"], market["interest_rate_scr"], market["spread"])


def test_counterparty_default_formula() -> None:
    assert counterparty_default_scr(1_000.0, pd_=0.005, lgd=0.50) == pytest.approx(7.5)


def test_operational_scr_formula() -> None:
    assert operational_scr(1_000.0, 500.0) == pytest.approx(40.0)


def test_bscr_aggregation_and_final_scr() -> None:
    bscr = bscr_aggregation(market_scr=100.0, non_life_scr=200.0, counterparty_scr=50.0)
    expected = np.sqrt(
        100.0**2
        + 200.0**2
        + 50.0**2
        + 2 * 0.25 * 100.0 * 200.0
        + 2 * 0.25 * 100.0 * 50.0
        + 2 * 0.50 * 200.0 * 50.0
    )
    assert bscr == pytest.approx(expected)

    result = simplified_standard_formula_scr(
        nep_by_lob={"Other motor insurance": 100.0},
        net_claims_be_by_lob={"Other motor insurance": 50.0},
        net_catastrophe_losses=[0.0, 10.0, 20.0],
        asset_portfolio=asset_portfolio_fixture(),
        reinsurance_recoverables=1_000.0,
        nep=100.0,
        net_technical_provisions=50.0,
    )
    assert result.summary["scr"] == pytest.approx(result.summary["bscr"] + result.summary["operational_scr"])
