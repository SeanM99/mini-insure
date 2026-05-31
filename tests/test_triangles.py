from __future__ import annotations

import pandas as pd

from miniinsure.reserving.triangles import (
    build_annual_triangles,
    calculate_development_year,
    triangle_to_matrix,
    validate_cumulative_paid_non_decreasing,
)


def observed_claims_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "claim_id": ["C1", "C2", "C3", "C4"],
            "policy_id": ["P1", "P2", "P3", "P4"],
            "accident_year": [2021, 2021, 2022, 2023],
            "accident_date": ["2021-01-10", "2021-06-10", "2022-02-15", "2023-03-20"],
            "report_date": ["2021-02-01", "2021-07-01", "2023-03-01", "2023-04-01"],
            "claim_type": [
                "own_damage_attritional",
                "own_damage_attritional",
                "own_damage_attritional",
                "own_damage_attritional",
            ],
            "solvency_ii_lob": ["Other motor insurance"] * 4,
            "homogeneous_risk_group": ["tpl|retail|small"] * 4,
            "paid_to_date": [100.0, 0.0, 150.0, 50.0],
            "case_reserve": [50.0, 0.0, 150.0, 30.0],
            "latest_case_estimate": [150.0, 0.0, 300.0, 80.0],
            "zero_insured_flag": [False, True, False, False],
        }
    )


def payments_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "payment_id": ["PAY1", "PAY2", "PAYZERO", "PAY3", "PAY4", "PAY5"],
            "claim_id": ["C1", "C1", "C2", "C3", "C3", "C4"],
            "payment_date": [
                "2021-03-01",
                "2022-03-01",
                "2021-08-01",
                "2023-06-01",
                "2024-01-15",
                "2023-05-01",
            ],
            "paid_amount": [40.0, 60.0, 999.0, 120.0, 30.0, 50.0],
        }
    )


def test_golden_fixture_paid_triangle_excludes_zero_insured_payments() -> None:
    triangles = build_annual_triangles(observed_claims_fixture(), payments_fixture())
    matrix = triangle_to_matrix(triangles.paid, "cumulative_paid")

    assert matrix.loc[2021, 1] == 40.0
    assert matrix.loc[2021, 2] == 100.0
    assert matrix.loc[2021, 6] == 100.0
    assert matrix.loc[2022, 1] == 0.0
    assert matrix.loc[2022, 2] == 120.0
    assert matrix.loc[2022, 3] == 150.0
    assert matrix.loc[2023, 1] == 50.0


def test_golden_fixture_incurred_triangle() -> None:
    triangles = build_annual_triangles(observed_claims_fixture(), payments_fixture())
    matrix = triangle_to_matrix(triangles.incurred, "cumulative_incurred")

    assert matrix.loc[2021, 1] == 150.0
    assert matrix.loc[2021, 6] == 150.0
    assert matrix.loc[2022, 1] == 0.0
    assert matrix.loc[2022, 2] == 300.0
    assert matrix.loc[2023, 1] == 80.0


def test_development_year_calculation() -> None:
    assert calculate_development_year(2024, 2021) == 4


def test_non_decreasing_cumulative_paid_validation() -> None:
    paid_triangle = pd.DataFrame(
        {
            "solvency_ii_lob": ["Other motor insurance", "Other motor insurance"],
            "homogeneous_risk_group": ["tpl|retail|small", "tpl|retail|small"],
            "origin_year": [2021, 2021],
            "development_year": [1, 2],
            "cumulative_paid": [100.0, 90.0],
        }
    )

    messages = validate_cumulative_paid_non_decreasing(paid_triangle)

    assert len(messages) == 1
    assert messages[0].rule_id == "DQ007"


def test_zero_insured_claims_remain_in_count_diagnostics() -> None:
    triangles = build_annual_triangles(observed_claims_fixture(), payments_fixture())
    matrix = triangle_to_matrix(triangles.counts, "cumulative_count")

    assert matrix.loc[2021, 1] == 2
