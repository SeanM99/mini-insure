from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from miniinsure.alm import calibrate_asset_portfolio
from miniinsure.reserving.deterministic_methods import deterministic_reserving_results
from miniinsure.reserving.reserve_risk import simulate_reserve_risk_quick
from miniinsure.reserving.triangles import build_annual_triangles
from miniinsure.risk_engine.one_year_engine import economic_capital_summary, simulate_one_year_economic_capital
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


def policies_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "policy_id": ["P1", "P2"],
            "earned_premium": [1_000.0, 2_000.0],
            "loss_cost": [500.0, 1_000.0],
            "expected_frequency_attritional_damage": [0.10, 0.20],
            "expected_frequency_bodily_injury": [0.02, 0.03],
            "expected_frequency_theft_fire": [0.04, 0.05],
        }
    )


def reserve_risk_fixture() -> pd.DataFrame:
    return pd.DataFrame({"simulation": [1, 2, 3], "reserve_loss": [10.0, -5.0, 20.0]})


def test_economic_capital_formula_and_tvar() -> None:
    losses = pd.Series([0.0, 100.0, 200.0, 1_000.0])
    summary = economic_capital_summary(losses).iloc[0]

    expected = losses.mean()
    var_995 = np.quantile(losses, 0.995)
    assert summary["expected_loss"] == pytest.approx(expected)
    assert summary["var_995"] == pytest.approx(var_995)
    assert summary["tvar_995"] == pytest.approx(1_000.0)
    assert summary["economic_capital"] == pytest.approx(var_995 - expected)


def test_deterministic_reproducibility() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=500.0)
    first = simulate_one_year_economic_capital(
        policies_fixture(),
        reserve_risk_fixture(),
        opening_own_funds=700.0,
        opening_net_best_estimate=1_000.0,
        reinsurance_recoverables=100.0,
        n_simulations=30,
        seed=20261231,
        asset_portfolio=assets,
    )
    second = simulate_one_year_economic_capital(
        policies_fixture(),
        reserve_risk_fixture(),
        opening_own_funds=700.0,
        opening_net_best_estimate=1_000.0,
        reinsurance_recoverables=100.0,
        n_simulations=30,
        seed=20261231,
        asset_portfolio=assets,
    )

    pd.testing.assert_frame_equal(first.simulations, second.simulations)
    pd.testing.assert_frame_equal(first.summary, second.summary)


def test_one_year_loss_distribution_has_required_contributions() -> None:
    assets = calibrate_asset_portfolio(opening_liabilities=1_000.0, scr=500.0)
    result = simulate_one_year_economic_capital(
        policies_fixture(),
        reserve_risk_fixture(),
        opening_own_funds=700.0,
        opening_net_best_estimate=1_000.0,
        reinsurance_recoverables=100.0,
        n_simulations=30,
        seed=20261231,
        asset_portfolio=assets,
    )

    assert {
        "one_year_loss",
        "reserve_loss",
        "premium_risk_loss",
        "market_risk_loss",
        "operational_loss",
        "credit_loss",
    }.issubset(result.simulations.columns)
    assert {"expected_loss", "var_995", "tvar_995", "economic_capital"}.issubset(result.summary.columns)


def test_small_mode_runtime_sanity() -> None:
    started = time.perf_counter()
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)
    triangles = build_annual_triangles(reality.observed_valuation_snapshot, reality.payments)
    reserving = deterministic_reserving_results(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
    )
    reserve_risk = simulate_reserve_risk_quick(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
        reserving,
        n_simulations=25,
        seed=20261231,
    )
    assets = calibrate_asset_portfolio(opening_liabilities=1_000_000.0, scr=500_000.0)
    result = simulate_one_year_economic_capital(
        reality.policies,
        reserve_risk.simulations,
        opening_own_funds=700_000.0,
        opening_net_best_estimate=1_000_000.0,
        reinsurance_recoverables=100_000.0,
        n_simulations=25,
        seed=20261231,
        asset_portfolio=assets,
    )
    elapsed = time.perf_counter() - started

    assert len(result.simulations) == 25
    assert elapsed < 15.0
