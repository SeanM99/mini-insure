from __future__ import annotations

import pytest

from miniinsure.own_funds import one_year_own_funds_movement, opening_balance_sheet, own_funds_summary


def test_own_funds_movement_formula() -> None:
    of1 = one_year_own_funds_movement(
        of0=100.0,
        nep=50.0,
        net_claims=20.0,
        reserve_loss=5.0,
        expenses=10.0,
        investment_result=7.0,
        operational_loss=3.0,
        credit_loss=2.0,
    )

    assert of1 == pytest.approx(117.0)


def test_opening_balance_sheet_reconciles() -> None:
    balance_sheet = opening_balance_sheet(technical_provisions=1_000.0, other_liabilities=100.0, scr=500.0)

    assert balance_sheet.summary["liabilities"] == pytest.approx(1_100.0)
    assert balance_sheet.summary["own_funds"] == pytest.approx(700.0)
    assert balance_sheet.summary["assets"] == pytest.approx(1_800.0)
    assert balance_sheet.summary["reconciliation_status"] == "pass"
    assert balance_sheet.own_funds_tiers.loc[0, "tier"] == "Tier 1 unrestricted"


def test_own_funds_equal_excess_assets_over_liabilities() -> None:
    summary = own_funds_summary(assets=1_800.0, liabilities=1_100.0, scr=500.0, mcr=400.0)

    assert summary["excess_assets_over_liabilities"] == pytest.approx(700.0)
    assert summary["eligible_own_funds"] == pytest.approx(700.0)
    assert summary["tier_1_unrestricted"] == pytest.approx(700.0)


def test_solvency_ratio_calculation() -> None:
    summary = own_funds_summary(assets=1_800.0, liabilities=1_100.0, scr=500.0, mcr=400.0)

    assert summary["solvency_ratio"] == pytest.approx(1.4)
    assert summary["mcr_ratio"] == pytest.approx(1.75)
