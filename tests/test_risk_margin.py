from __future__ import annotations

import pytest

from miniinsure.risk_margin import RUNOFF_FACTORS, calculate_risk_margin, non_hedgeable_scr_components


FLAT_ZERO_CURVE = {0.0: 0.0, 10.0: 0.0}


def test_risk_margin_calculation() -> None:
    result = calculate_risk_margin(
        claims_provision=1_000.0,
        premium_provision=-100.0,
        reinsurance_recoverables=200.0,
        gross_best_estimate=900.0,
        risk_free_curve=FLAT_ZERO_CURVE,
    )

    expected_components = {
        "reserve_risk": 100.0,
        "premium_provision_risk": 8.0,
        "reinsurance_counterparty_risk": 0.5,
        "operational_risk": 27.0,
    }
    expected_base_scr = sum(expected_components.values())
    expected_risk_margin = 0.06 * expected_base_scr * sum(RUNOFF_FACTORS.values())

    assert result.scr_components == pytest.approx(expected_components)
    assert result.base_scr == pytest.approx(expected_base_scr)
    assert result.risk_margin == pytest.approx(expected_risk_margin)
    assert len(result.runoff) == 10


def test_non_hedgeable_scr_components_include_required_risks() -> None:
    components = non_hedgeable_scr_components(
        claims_provision=1_000.0,
        premium_provision=250.0,
        reinsurance_recoverables=100.0,
        gross_best_estimate=1_250.0,
    )

    assert set(components) == {
        "reserve_risk",
        "premium_provision_risk",
        "reinsurance_counterparty_risk",
        "operational_risk",
    }
    assert all(value >= 0 for value in components.values())
