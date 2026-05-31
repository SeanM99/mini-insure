from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from miniinsure.simulation.claim_severity import (
    apply_deductible_and_limit,
    expected_gross_severity_mean,
    simulate_claim_severity,
)
from miniinsure.simulation.synthetic_reality import derive_module_seed


def test_severity_distribution_tolerance() -> None:
    size = 20_000
    claim_stubs = pd.DataFrame(
        {
            "claim_id": [f"C{i:05d}" for i in range(size)],
            "policy_id": [f"P{i:05d}" for i in range(size)],
            "claim_type": "own_damage_attritional",
            "coverage_type": "partial_casco",
            "country_group": "Netherlands",
            "vehicle_segment": "medium",
            "deductible_band": "none",
            "sum_insured": 1_000_000.0,
            "catastrophe_event_id": pd.NA,
        }
    )

    _, truth = simulate_claim_severity(
        claim_stubs,
        rng=np.random.default_rng(derive_module_seed(20261231, "claim_severity")),
    )

    assert truth["gross_ultimate_amount"].mean() == pytest.approx(
        expected_gross_severity_mean("own_damage_attritional"),
        rel=0.04,
    )


def test_deductible_and_limit_application_order() -> None:
    insured = apply_deductible_and_limit(
        gross_amount=np.array([100.0, 1_000.0, 10_000.0]),
        deductible_amount=np.array([250.0, 250.0, 250.0]),
        policy_limit_amount=np.array([500.0, 500.0, 8_000.0]),
    )

    assert insured.tolist() == [0.0, 500.0, 8_000.0]
