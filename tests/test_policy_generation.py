from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.simulation.policy_generator import (
    BASE_DISTRIBUTIONS,
    REQUIRED_POLICY_COLUMNS,
    conditional_distribution,
    generate_policy_data,
)


def test_policy_generation_is_deterministic_for_fixed_seed() -> None:
    first = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=100,
        seed=20261231,
    )
    second = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=100,
        seed=20261231,
    )

    pd.testing.assert_frame_equal(first, second)


def test_required_policy_columns_exist() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=25,
        seed=20261231,
    )

    assert set(REQUIRED_POLICY_COLUMNS).issubset(policies.columns)


def test_base_distributions_within_tolerance_for_10000_generated_policies() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=10_000,
        seed=20261231,
        include_pricing=False,
    )

    country_share = policies["country_group"].value_counts(normalize=True).to_dict()
    age_share = policies["driver_age_band"].value_counts(normalize=True).to_dict()

    for category, expected in BASE_DISTRIBUTIONS["country_group"].items():
        assert country_share[category] == pytest.approx(expected, abs=0.015)
    for category, expected in BASE_DISTRIBUTIONS["driver_age_band"].items():
        assert age_share[category] == pytest.approx(expected, abs=0.015)


def test_conditional_dependency_behavior() -> None:
    young_channel = conditional_distribution(
        "distribution_channel",
        {"driver_age_band": "18-24"},
    )
    premium_coverage = conditional_distribution(
        "coverage_type",
        {"vehicle_segment": "premium"},
    )
    electric_coverage = conditional_distribution(
        "coverage_type",
        {"vehicle_segment": "electric"},
    )
    van_customer = conditional_distribution(
        "customer_type",
        {"vehicle_segment": "van"},
    )
    prior_claims_bonus_malus = conditional_distribution(
        "bonus_malus_class",
        {"prior_claims_band": "2+"},
    )
    urban_mileage = conditional_distribution(
        "mileage_band",
        {"urbanicity": "urban"},
    )
    nordics_vehicle = conditional_distribution(
        "vehicle_segment",
        {"country_group": "Nordics"},
    )

    assert young_channel["aggregator"] == pytest.approx(0.45 / 1.16)
    assert young_channel["affinity"] == pytest.approx(0.05 / 1.16)
    assert premium_coverage["comprehensive"] == pytest.approx(0.85)
    assert electric_coverage["comprehensive"] == pytest.approx(0.85)
    assert van_customer["small_commercial"] == pytest.approx(0.45)
    assert prior_claims_bonus_malus["high"] == pytest.approx(0.65)
    assert urban_mileage["high"] == pytest.approx(0.28)
    assert nordics_vehicle["electric"] == pytest.approx(0.15)


def test_small_mode_generates_10000_policies_per_year() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2021, 2022),
        seed=20261231,
        include_pricing=False,
    )

    counts = policies.groupby("underwriting_year")["policy_id"].count().to_dict()

    assert counts == {2021: 10_000, 2022: 10_000}
