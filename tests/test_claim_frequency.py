from __future__ import annotations

import numpy as np

from miniinsure.simulation.claim_frequency import (
    CLAIM_TYPES,
    expected_claim_frequency_by_type,
    simulate_claim_frequency,
)
from miniinsure.simulation.policy_generator import generate_policy_data
from miniinsure.simulation.synthetic_reality import derive_module_seed


def test_frequency_distribution_tolerance() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=20_000,
        seed=20261231,
        include_pricing=False,
    )
    expected = expected_claim_frequency_by_type(policies)
    claims = simulate_claim_frequency(
        policies,
        rng=np.random.default_rng(derive_module_seed(20261231, "claim_frequency")),
    )

    expected_total = expected.to_numpy().sum()

    assert len(claims) == expected_total.__round__() or abs(len(claims) - expected_total) / expected_total < 0.15
    assert set(claims["claim_type"].unique()).issubset(set(CLAIM_TYPES))


def test_claim_frequency_is_deterministic() -> None:
    policies = generate_policy_data(
        portfolio_mode="small",
        years=(2026,),
        policies_per_year=1_000,
        seed=20261231,
        include_pricing=False,
    )
    first = simulate_claim_frequency(
        policies,
        rng=np.random.default_rng(derive_module_seed(20261231, "claim_frequency")),
    )
    second = simulate_claim_frequency(
        policies,
        rng=np.random.default_rng(derive_module_seed(20261231, "claim_frequency")),
    )

    assert first.equals(second)
