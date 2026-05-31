from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.reserving.deterministic_methods import (
    apply_sparse_hrg_fallback,
    bornhuetter_ferguson,
    cape_cod,
    development_factors,
    incurred_chain_ladder,
    method_weights,
    paid_chain_ladder,
)


def paid_triangle_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            1: [100.0, 120.0, 90.0],
            2: [160.0, 180.0, None],
            3: [200.0, None, None],
        },
        index=[2021, 2022, 2023],
    )


def incurred_triangle_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            1: [220.0, 150.0, 80.0],
            2: [230.0, 210.0, None],
            3: [240.0, None, None],
        },
        index=[2021, 2022, 2023],
    )


def test_paid_chain_ladder() -> None:
    result = paid_chain_ladder(paid_triangle_matrix(), tail_factor=1.05).origin_estimates
    by_year = result.set_index("origin_year")

    assert by_year.loc[2021, "ultimate"] == pytest.approx(210.0)
    assert by_year.loc[2022, "ultimate"] == pytest.approx(236.25)
    assert by_year.loc[2023, "ultimate"] == pytest.approx(182.5568, rel=1e-4)


def test_incurred_chain_ladder() -> None:
    result = incurred_chain_ladder(incurred_triangle_matrix(), tail_factor=1.05).origin_estimates
    by_year = result.set_index("origin_year")

    assert by_year.loc[2021, "ultimate"] == pytest.approx(252.0)
    assert by_year.loc[2022, "ultimate"] == pytest.approx(230.0870, rel=1e-4)


def test_bornhuetter_ferguson() -> None:
    result = bornhuetter_ferguson(
        paid_triangle_matrix(),
        {2021: 300.0, 2022: 300.0, 2023: 300.0},
        expected_loss_ratio=0.60,
        tail_factor=1.05,
    ).set_index("origin_year")

    assert result.loc[2021, "ibnr"] == pytest.approx(8.5714, rel=1e-4)
    assert result.loc[2021, "ultimate"] == pytest.approx(208.5714, rel=1e-4)


def test_cape_cod() -> None:
    result = cape_cod(
        paid_triangle_matrix(),
        {2021: 300.0, 2022: 300.0, 2023: 300.0},
        tail_factor=1.05,
    ).set_index("origin_year")

    assert result.loc[2021, "selected_loss_ratio"] == pytest.approx(0.7098, rel=1e-4)
    assert (result["ibnr"] >= 0).all()


def test_tail_factor_application_is_visible_in_factors() -> None:
    factors = development_factors(paid_triangle_matrix(), tail_factor=1.05)

    tail = factors.loc[factors["is_tail"]].iloc[0]
    assert tail["factor"] == 1.05
    assert tail["to_development_year"] == "ultimate"


def test_method_weights() -> None:
    assert method_weights(
        solvency_ii_lob="Other motor insurance",
        claim_type="own_damage_attritional",
        latest_development_year=3,
    ) == {"paid_chain_ladder": 0.80, "bornhuetter_ferguson": 0.20}
    assert method_weights(
        solvency_ii_lob="Other motor insurance",
        claim_type="own_damage_attritional",
        latest_development_year=2,
    ) == {"paid_chain_ladder": 0.40, "bornhuetter_ferguson": 0.60}
    assert method_weights(
        solvency_ii_lob="Motor vehicle liability",
        claim_type="attritional_bi",
        latest_development_year=4,
    ) == {"paid_chain_ladder": 0.20, "incurred_chain_ladder": 0.40, "bornhuetter_ferguson": 0.40}
    assert method_weights(
        solvency_ii_lob="Motor vehicle liability",
        claim_type="attritional_bi",
        latest_development_year=2,
    ) == {"incurred_chain_ladder": 0.20, "bornhuetter_ferguson": 0.80}
    assert method_weights(
        solvency_ii_lob="Motor vehicle liability",
        claim_type="large_bi",
        latest_development_year=2,
    ) == {"incurred_chain_ladder": 0.20, "frequency_severity": 0.60, "case_adequacy_review": 0.20}
    assert method_weights(
        solvency_ii_lob="Other motor insurance",
        claim_type="catastrophe_allocated",
        latest_development_year=2,
    ) == {"event_based_estimate": 0.70, "bornhuetter_ferguson": 0.30}


def test_negative_ibnr_floor() -> None:
    triangle = pd.DataFrame({1: [1_000.0, 0.0]}, index=[2021, 2022])
    result = cape_cod(
        triangle,
        {2021: 1_000.0, 2022: 1_000.0},
        tail_factor=1.0,
    ).set_index("origin_year")

    assert result.loc[2021, "ultimate"] == 1_000.0
    assert result.loc[2021, "ibnr"] == 0.0


def test_sparse_hrg_fallback() -> None:
    assert method_weights(
        solvency_ii_lob="Other motor insurance",
        claim_type="own_damage_attritional",
        latest_development_year=1,
        sparse=True,
    ) == {"segment_estimate": 0.50, "all_portfolio_selected_factors": 0.50}
    assert apply_sparse_hrg_fallback(100.0, 140.0) == 120.0
