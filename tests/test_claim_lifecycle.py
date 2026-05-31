from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.simulation.synthetic_reality import (
    generate_synthetic_reality,
    load_synthetic_truth_for_diagnostics_only,
)


def test_claim_lifecycle_dates_are_ordered() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=1_000)
    claims = reality.claims
    payments = reality.payments

    assert (pd.to_datetime(claims["report_date"]) >= pd.to_datetime(claims["accident_date"])).all()

    settled = claims["settlement_date"].notna()
    assert (
        pd.to_datetime(claims.loc[settled, "settlement_date"])
        >= pd.to_datetime(claims.loc[settled, "report_date"])
    ).all()

    joined = payments.merge(claims[["claim_id", "accident_date", "report_date"]], on="claim_id", how="left")
    assert (pd.to_datetime(joined["payment_date"]) >= pd.to_datetime(joined["accident_date"])).all()
    assert (pd.to_datetime(joined["payment_date"]) >= pd.to_datetime(joined["report_date"])).all()


def test_settled_claim_payments_equal_insured_ultimate_without_overpayment() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=1_000)
    truth = load_synthetic_truth_for_diagnostics_only(
        reality,
        acknowledge_truth_isolation=True,
    )
    settled = reality.claims.loc[
        (reality.claims["claim_status"] == "settled")
        & (~reality.claims["overpayment_flag"])
    ]
    payment_totals = reality.payments.groupby("claim_id")["paid_amount"].sum()
    check = settled[["claim_id"]].merge(
        truth[["claim_id", "insured_ultimate_amount"]],
        on="claim_id",
        how="left",
    )
    check["paid_amount"] = check["claim_id"].map(payment_totals).fillna(0.0)

    assert check["paid_amount"].sum() > 0
    assert (check["paid_amount"] - check["insured_ultimate_amount"]).abs().max() == pytest.approx(0.0, abs=1e-6)


def test_observed_snapshot_excludes_future_transactions_after_valuation_date() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=1_000)

    assert (pd.to_datetime(reality.payments["payment_date"]) <= reality.valuation_date).all()
    assert (pd.to_datetime(reality.observed_valuation_snapshot["report_date"]) <= reality.valuation_date).all()
    visible_settlement = reality.observed_valuation_snapshot["settlement_date"].notna()
    assert (
        pd.to_datetime(reality.observed_valuation_snapshot.loc[visible_settlement, "settlement_date"])
        <= reality.valuation_date
    ).all()


def test_synthetic_reality_is_deterministically_reproducible() -> None:
    first = generate_synthetic_reality(portfolio_mode="small", policies_per_year=250)
    second = generate_synthetic_reality(portfolio_mode="small", policies_per_year=250)

    pd.testing.assert_frame_equal(first.policies, second.policies)
    pd.testing.assert_frame_equal(first.claims, second.claims)
    pd.testing.assert_frame_equal(first.payments, second.payments)
    pd.testing.assert_frame_equal(first.case_reserves, second.case_reserves)
    pd.testing.assert_frame_equal(first.catastrophe_events, second.catastrophe_events)
    pd.testing.assert_frame_equal(first.observed_valuation_snapshot, second.observed_valuation_snapshot)
