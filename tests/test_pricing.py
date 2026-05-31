from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from miniinsure.pricing import price_policies, round_to_nearest_eur_5
from miniinsure.simulation.policy_generator import generate_policy_data


def test_10_policy_golden_fixture_pricing_outputs() -> None:
    features = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=10,
        seed=20261231,
        include_pricing=False,
    )

    priced = price_policies(features, seed=20261231)

    expected_technical = np.array(
        [
            305.470253,
            804.377737,
            222.247937,
            479.896476,
            319.710421,
            426.849193,
            836.898459,
            600.281893,
            1914.088194,
            413.690855,
        ]
    )
    expected_charged = np.array(
        [285.0, 745.0, 225.0, 515.0, 295.0, 415.0, 870.0, 710.0, 1825.0, 390.0]
    )

    np.testing.assert_allclose(
        priced["technical_premium"].to_numpy(),
        expected_technical,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        priced["charged_premium"].to_numpy(),
        expected_charged,
        atol=0.0,
    )
    np.testing.assert_allclose(
        priced["written_premium"].to_numpy(),
        expected_charged,
        atol=0.0,
    )
    np.testing.assert_allclose(
        priced["earned_premium"].to_numpy(),
        expected_charged,
        atol=0.0,
    )


def test_minimum_premium_is_applied() -> None:
    policy = pd.DataFrame(
        {
            "policy_id": ["P_MIN"],
            "underwriting_year": [2026],
            "earned_exposure": [0.01],
            "written_exposure": [1.0],
            "country_group": ["Nordics"],
            "driver_age_band": ["50-64"],
            "vehicle_segment": ["small"],
            "urbanicity": ["rural"],
            "mileage_band": ["low"],
            "prior_claims_band": ["0"],
            "bonus_malus_class": ["low"],
            "coverage_type": ["tpl"],
            "customer_type": ["retail"],
            "deductible_band": ["eur1000"],
            "market_cycle_factor": [1.0],
        }
    )

    priced = price_policies(policy, competitive_factors=1.0)

    assert priced.loc[0, "charged_premium"] == 150.0


def test_nearest_eur_5_rounding() -> None:
    rounded = round_to_nearest_eur_5(np.array([152.49, 152.50, 157.49, 157.50]))

    assert rounded.tolist() == [150.0, 155.0, 155.0, 160.0]


def test_no_negative_premiums() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=1000,
        seed=20261231,
    )

    premium_columns = [
        "technical_premium",
        "charged_premium",
        "written_premium",
        "earned_premium",
    ]
    assert (policies[premium_columns] >= 0).all().all()


def test_charged_premium_is_rounded_to_nearest_5() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=100,
        seed=20261231,
    )

    assert (policies["charged_premium"] % 5 == 0).all()
