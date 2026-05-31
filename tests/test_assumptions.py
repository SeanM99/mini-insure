from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from miniinsure.assumptions import (
    BASE_ASSUMPTIONS_PATH,
    REGULATORY_ASSUMPTIONS_PATH,
    load_effective_assumptions,
    load_yaml_file,
    scenario_metadata,
    stable_assumption_hash,
)


def test_base_regulatory_merge_order() -> None:
    base = load_yaml_file(BASE_ASSUMPTIONS_PATH)
    regulatory = load_yaml_file(REGULATORY_ASSUMPTIONS_PATH)

    assumptions = load_effective_assumptions()

    assert base["supervisor"] != regulatory["supervisor"]
    assert assumptions.supervisor == regulatory["supervisor"]
    assert assumptions.validation_tolerances.monetary_abs == regulatory[
        "validation_tolerances"
    ]["monetary_abs"]


def test_override_transformation_modes() -> None:
    assumptions = load_effective_assumptions(
        scenario_overrides={
            "portfolio_mode": {"mode": "replace", "value": "small"},
            "policy_counts_by_year": {
                2026: {"mode": "multiply", "value": 2},
            },
            "market_cycle_factors": {
                "claims_inflation_cycle": {
                    "mode": "additive_percentage_point",
                    "value": 0.025,
                },
            },
            "validation_tolerances": {
                "monetary_abs": {"mode": "additive_amount", "value": 0.10},
            },
        }
    )

    assert assumptions.portfolio_mode == "small"
    assert assumptions.policy_counts_by_year[2026] == 48000
    assert assumptions.market_cycle_factors["claims_inflation_cycle"] == pytest.approx(1.025)
    assert assumptions.validation_tolerances.monetary_abs == pytest.approx(0.105)


def test_stable_hash_for_identical_assumptions() -> None:
    first = load_effective_assumptions()
    second = load_effective_assumptions()

    assert stable_assumption_hash(first) == stable_assumption_hash(second)


def test_changed_hash_when_assumptions_change() -> None:
    base = load_effective_assumptions()
    changed = load_effective_assumptions(ui_overrides={"portfolio_mode": "full"})

    assert stable_assumption_hash(base) != stable_assumption_hash(changed)


def test_validation_fails_if_real_xbrl_is_enabled() -> None:
    with pytest.raises(ValidationError):
        load_effective_assumptions(ui_overrides={"real_xbrl_disabled": False})


def test_master_seed_equals_required_value() -> None:
    assumptions = load_effective_assumptions()

    assert assumptions.master_seed == 20261231


def test_fixed_company_profile_fields_are_present() -> None:
    assumptions = load_effective_assumptions()

    assert assumptions.legal_entity.name == "MiniInsure Europe NL Synthetic N.V."
    assert assumptions.supervisor == "De Nederlandsche Bank"
    assert assumptions.jurisdiction == "Netherlands"
    assert assumptions.reporting_framework == "Educational Solvency II-style mock framework"
    assert assumptions.business_type == "Non-life insurance"
    assert assumptions.product == "Motor insurance"
    assert assumptions.reporting_currency == "EUR"


def test_scenario_metadata_contains_reproducibility_fields() -> None:
    assumptions = load_effective_assumptions()
    metadata = scenario_metadata(
        scenario_name="Base",
        assumptions=assumptions,
        generated_at=datetime(2026, 12, 31, 12, 0, tzinfo=UTC),
    )

    assert metadata["scenario_name"] == "Base"
    assert metadata["seed"] == 20261231
    assert metadata["valuation_date"] == "2026-12-31"
    assert metadata["assumption_hash"] == stable_assumption_hash(assumptions)
    assert metadata["app_version"] == "0.1.0"
    assert metadata["generation_timestamp"] == "2026-12-31T12:00:00Z"
