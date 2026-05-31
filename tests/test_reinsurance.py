from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.simulation.reinsurance_simulation import (
    ReinsuranceProgram,
    aggregate_stop_loss_recovery,
    apply_default_reinsurance_program,
    default_adjusted_recoverable,
    gross_to_net_reconciliation,
    per_risk_xol_recovery,
)
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


def simple_claims() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "claim_id": ["C1", "C2"],
            "accident_year": [2026, 2026],
            "latest_case_estimate": [2_000_000.0, 100_000.0],
        }
    )


def simple_policies() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "policy_id": ["P1", "P2"],
            "accident_year": [2026, 2026],
            "earned_premium": [500_000.0, 500_000.0],
        }
    )


def test_per_risk_recovery_formula() -> None:
    recovery = per_risk_xol_recovery(
        pd.Series([100_000.0, 500_000.0, 2_000_000.0]),
        retention=250_000.0,
        limit=1_000_000.0,
    )

    assert recovery.tolist() == [0.0, 250_000.0, 1_000_000.0]


def test_aggregate_stop_loss_formula() -> None:
    recovery = aggregate_stop_loss_recovery(
        annual_loss=1_200_000.0,
        earned_premium=1_000_000.0,
        attachment_loss_ratio=0.90,
        limit=10_000_000.0,
    )

    assert recovery == 300_000.0


def test_treaty_ordering_quota_share_then_per_risk_then_aggregate() -> None:
    result = apply_default_reinsurance_program(simple_claims(), simple_policies())
    annual = result.annual_level.iloc[0]

    assert annual["quota_share_ceded_loss"] == 0.0
    assert annual["per_risk_xol_recovery"] == 1_000_000.0
    assert annual["net_loss_before_aggregate"] == 1_100_000.0
    assert annual["aggregate_stop_loss_recovery"] == 200_000.0
    assert annual["net_loss"] == 900_000.0


def test_quota_share_disabled_by_default() -> None:
    program = ReinsuranceProgram()
    result = apply_default_reinsurance_program(simple_claims(), simple_policies(), program=program)

    assert not program.quota_share_enabled
    assert result.claim_level["quota_share_ceded_loss"].sum() == 0.0


def test_quota_share_enabled_behavior() -> None:
    program = ReinsuranceProgram(quota_share_enabled=True, quota_share_ceded_pct=0.20)
    result = apply_default_reinsurance_program(simple_claims(), simple_policies(), program=program)
    annual = result.annual_level.iloc[0]

    assert result.claim_level.loc[0, "quota_share_ceded_loss"] == 400_000.0
    assert result.claim_level.loc[0, "loss_after_quota_share"] == 1_600_000.0
    assert annual["quota_share_ceded_loss"] == 420_000.0
    assert annual["quota_share_ceded_premium"] == 200_000.0
    assert annual["quota_share_ceding_commission"] == 40_000.0
    assert annual["aggregate_stop_loss_recovery"] == 0.0
    assert annual["net_loss"] == 680_000.0


def test_recovery_never_exceeds_eligible_loss() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)
    result = apply_default_reinsurance_program(
        reality.observed_valuation_snapshot,
        reality.policies,
    )

    assert (result.claim_level["per_risk_xol_recovery"] <= result.claim_level["loss_after_quota_share"]).all()
    assert (result.annual_level["total_recovery"] <= result.annual_level["gross_loss"]).all()
    assert (result.annual_level["net_loss"] >= 0).all()


def test_default_adjusted_recoverable() -> None:
    adjusted = default_adjusted_recoverable(1_000_000.0, pd_=0.005, lgd=0.50)

    assert adjusted == 997_500.0


def test_deterministic_output_for_generated_fixture_data() -> None:
    first_reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)
    second_reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)

    first = apply_default_reinsurance_program(
        first_reality.observed_valuation_snapshot,
        first_reality.policies,
    )
    second = apply_default_reinsurance_program(
        second_reality.observed_valuation_snapshot,
        second_reality.policies,
    )

    pd.testing.assert_frame_equal(first.claim_level, second.claim_level)
    pd.testing.assert_frame_equal(first.annual_level, second.annual_level)
    assert gross_to_net_reconciliation(first).equals(gross_to_net_reconciliation(second))
    assert first.summary == pytest.approx(second.summary)
