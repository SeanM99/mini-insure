from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from miniinsure.reserving.deterministic_methods import deterministic_reserving_results
from miniinsure.reserving.reserve_risk import QUICK_MODE_SIMULATIONS, simulate_reserve_risk_quick
from miniinsure.reserving.triangles import build_annual_triangles
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


def paid_triangle_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "solvency_ii_lob": ["Other motor insurance"] * 5,
            "homogeneous_risk_group": ["partial_casco|retail|small"] * 5,
            "origin_year": [2024, 2024, 2024, 2025, 2025],
            "accident_year": [2024, 2024, 2024, 2025, 2025],
            "development_year": [1, 2, 3, 1, 2],
            "development_period": [1, 2, 3, 1, 2],
            "incremental_paid": [100.0, 80.0, 40.0, 120.0, 60.0],
            "cumulative_paid": [100.0, 180.0, 220.0, 120.0, 180.0],
        }
    )


def incurred_triangle_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "solvency_ii_lob": ["Other motor insurance"] * 5,
            "homogeneous_risk_group": ["partial_casco|retail|small"] * 5,
            "origin_year": [2024, 2024, 2024, 2025, 2025],
            "accident_year": [2024, 2024, 2024, 2025, 2025],
            "development_year": [1, 2, 3, 1, 2],
            "development_period": [1, 2, 3, 1, 2],
            "incremental_incurred": [140.0, 90.0, 20.0, 160.0, 70.0],
            "cumulative_incurred": [140.0, 230.0, 250.0, 160.0, 230.0],
        }
    )


def opening_results_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "solvency_ii_lob": [
                "Other motor insurance",
                "Other motor insurance",
                "Motor vehicle liability",
                "Motor vehicle liability",
                "Other motor insurance",
            ],
            "homogeneous_risk_group": [
                "partial_casco|retail|small",
                "partial_casco|retail|small",
                "tpl|retail|medium",
                "tpl|retail|medium",
                "HRG04",
            ],
            "origin_year": [2024, 2025, 2025, 2025, 2026],
            "claim_type_basis": [
                "own_damage_attritional",
                "theft_fire",
                "attritional_bi",
                "large_bi",
                "catastrophe_allocated",
            ],
            "claim_count": [20, 12, 5, 1, 1],
            "latest_development_year": [3, 2, 2, 2, 1],
            "sparse_hrg_fallback": [False, False, False, False, True],
            "selected_method": ["fixture"] * 5,
            "latest_paid": [220.0, 180.0, 100.0, 250.0, 50.0],
            "latest_incurred": [250.0, 230.0, 450.0, 900.0, 300.0],
            "paid_chain_ladder_ultimate": [260.0, 240.0, 700.0, 1_100.0, 400.0],
            "incurred_chain_ladder_ultimate": [260.0, 240.0, 720.0, 1_150.0, 420.0],
            "bornhuetter_ferguson_ultimate": [255.0, 235.0, 680.0, 1_050.0, 380.0],
            "selected_ultimate": [270.0, 250.0, 800.0, 1_200.0, 500.0],
            "ibnr": [20.0, 20.0, 350.0, 300.0, 200.0],
            "selected_reserve": [50.0, 70.0, 700.0, 950.0, 450.0],
        }
    )


def empty_policies() -> pd.DataFrame:
    return pd.DataFrame({"policy_id": [], "accident_year": [], "earned_premium": []})


def empty_claims() -> pd.DataFrame:
    return pd.DataFrame()


def test_deterministic_simulation_reproducibility_for_fixed_seed() -> None:
    first = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=12345,
    )
    second = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=12345,
    )

    pd.testing.assert_frame_equal(first.simulations, second.simulations)
    pd.testing.assert_frame_equal(first.summary, second.summary)
    assert first.settings["mode"] == "quick"


def test_output_statistics_exist() -> None:
    result = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=20261231,
    )

    expected_columns = {
        "mean",
        "standard_deviation",
        "var_95",
        "var_99",
        "var_995",
        "tvar_995",
        "probability_of_adverse_development",
        "expected_reserve_loss",
        "reserve_capital",
    }
    assert expected_columns.issubset(result.summary.columns)
    assert result.settings["simulation_count"] == 50


def test_reserve_capital_formula() -> None:
    result = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=20261231,
    )
    summary = result.summary.iloc[0]

    assert summary["reserve_capital"] == pytest.approx(summary["var_995"] - summary["expected_reserve_loss"])


def test_adverse_development_probability_is_between_zero_and_one() -> None:
    result = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=20261231,
    )
    probability = result.summary.iloc[0]["probability_of_adverse_development"]

    assert 0.0 <= probability <= 1.0


def test_closing_reserve_is_reestimated_not_copied_from_truth() -> None:
    result = simulate_reserve_risk_quick(
        paid_triangle_fixture(),
        incurred_triangle_fixture(),
        empty_policies(),
        empty_claims(),
        opening_results_fixture(),
        n_simulations=50,
        seed=20261231,
    )

    assert result.simulations["closing_reestimated_from_observed_triangle"].all()
    assert (
        result.simulations["closing_best_estimate_basis"]
        == "re-estimated_from_simulated_one_year_observed_triangle"
    ).all()
    assert not np.allclose(
        result.simulations["closing_best_estimate"],
        result.simulations["simulated_direct_remaining_unpaid_diagnostic"],
    )


def test_default_quick_mode_uses_1000_simulations() -> None:
    assert QUICK_MODE_SIMULATIONS == 1_000


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
    result = simulate_reserve_risk_quick(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
        reserving,
        n_simulations=25,
        seed=20261231,
    )
    elapsed = time.perf_counter() - started

    assert len(result.simulations) == 25
    assert elapsed < 15.0
