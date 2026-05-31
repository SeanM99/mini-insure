from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.reserving.cashflow_projection import discount_factor_for_month, present_value
from miniinsure.reserving.claims_provision import calculate_claims_provision
from miniinsure.reserving.premium_provision import calculate_premium_provision
from miniinsure.reserving.technical_provisions import (
    calculate_reinsurance_recoverables,
    calculate_technical_provisions,
    valuation_reconciles,
)
from miniinsure.simulation.reinsurance_simulation import ReinsuranceProgram


FLAT_ZERO_CURVE = {0.0: 0.0, 10.0: 0.0}
FLAT_FIVE_PERCENT_CURVE = {0.0: 0.05, 10.0: 0.05}


def reserving_fixture(selected_reserve: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "solvency_ii_lob": ["Other motor insurance"],
            "homogeneous_risk_group": ["tpl|retail|small"],
            "origin_year": [2026],
            "claim_type_basis": ["own_damage_attritional"],
            "claim_count": [10],
            "latest_development_year": [1],
            "sparse_hrg_fallback": [False],
            "selected_method": ["Paid chain ladder 80%, Bornhuetter-Ferguson 20%"],
            "latest_paid": [0.0],
            "latest_incurred": [0.0],
            "selected_ultimate": [selected_reserve],
            "ibnr": [selected_reserve],
            "selected_reserve": [selected_reserve],
        }
    )


def policies_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "policy_id": ["P1"],
            "accident_year": [2026],
            "underwriting_year": [2026],
            "inception_date": ["2026-07-01"],
            "expiry_date": ["2027-07-01"],
            "written_exposure": [1.0],
            "earned_exposure": [1.0],
            "charged_premium": [1_200.0],
            "earned_premium": [1_200.0],
            "loss_cost": [20.0],
        }
    )


def test_golden_fixture_claims_provision_and_expenses() -> None:
    result = calculate_claims_provision(reserving_fixture(100.0), risk_free_curve=FLAT_ZERO_CURVE)

    assert result.summary["undiscounted_loss_payments"] == pytest.approx(100.0)
    assert result.summary["allocated_loss_adjustment_expense"] == pytest.approx(4.0)
    assert result.summary["unallocated_loss_adjustment_expense"] == pytest.approx(2.0)
    assert result.summary["present_value"] == pytest.approx(106.0)


def test_discounting_calculation() -> None:
    cashflows = pd.DataFrame({"month_offset": [12], "cashflow": [105.0]})

    assert discount_factor_for_month(12, FLAT_FIVE_PERCENT_CURVE) == pytest.approx(1.0 / 1.05)
    assert present_value(cashflows, curve=FLAT_FIVE_PERCENT_CURVE) == pytest.approx(100.0)


def test_premium_provision_allows_negative_value() -> None:
    result = calculate_premium_provision(
        policies_fixture(),
        valuation_date=pd.Timestamp("2026-12-31"),
        risk_free_curve=FLAT_ZERO_CURVE,
    )

    assert result.summary["in_force_policy_count"] == 1.0
    assert result.summary["future_premium_inflows"] > result.summary["future_claims"]
    assert result.summary["present_value"] < 0.0


def test_reinsurance_recoverables_reconcile_gross_to_net() -> None:
    program = ReinsuranceProgram(
        per_risk_retention=50.0,
        per_risk_limit=1_000.0,
        aggregate_stop_loss_enabled=False,
    )
    recoverables = calculate_reinsurance_recoverables(
        reserving_fixture(200.0),
        policies_fixture(),
        program=program,
        risk_free_curve=FLAT_ZERO_CURVE,
    )

    assert recoverables.summary["present_value"] == pytest.approx(149.625)
    assert recoverables.reinsurance_result.summary["gross_loss"] == pytest.approx(200.0)
    assert recoverables.reinsurance_result.summary["net_loss"] == pytest.approx(50.0)


def test_technical_provisions_equal_best_estimate_plus_risk_margin() -> None:
    result = calculate_technical_provisions(
        reserving_fixture(200.0),
        policies_fixture(),
        valuation_date=pd.Timestamp("2026-12-31"),
        risk_free_curve=FLAT_ZERO_CURVE,
        reinsurance_program=ReinsuranceProgram(
            per_risk_retention=50.0,
            per_risk_limit=1_000.0,
            aggregate_stop_loss_enabled=False,
        ),
    )
    summary = result.summary

    assert summary["gross_technical_provisions"] == pytest.approx(
        summary["gross_best_estimate"] + summary["risk_margin"]
    )
    assert summary["net_technical_provisions"] == pytest.approx(
        summary["net_best_estimate"] + summary["risk_margin"]
    )
    assert summary["reconciliation_status"] == "pass"


def test_valuation_tolerance_behavior() -> None:
    assert valuation_reconciles(100.004, 100.0, tolerance=0.01)
    assert not valuation_reconciles(100.02, 100.0, tolerance=0.01)
