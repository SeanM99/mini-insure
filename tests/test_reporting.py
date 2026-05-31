from __future__ import annotations

import pytest

from miniinsure.reporting import calculate_reporting_workflow


@pytest.fixture(scope="module")
def workflow():
    return calculate_reporting_workflow(
        scenario_name="Reporting Test",
        portfolio_mode="small",
        policies_per_year=500,
        reserve_risk_simulations=25,
        capital_simulations=25,
    )


def test_management_income_statement_formulas(workflow) -> None:
    income = workflow.financial.income_statement.set_index("line_item")["amount"].to_dict()

    assert income["gross_claims_incurred"] == pytest.approx(
        income["paid_claims"] + income["change_in_gross_claims_provision"]
    )
    assert income["net_claims_incurred"] == pytest.approx(
        income["gross_claims_incurred"]
        - income["ceded_recoveries"]
        + income["reinsurance_premium_cost"]
    )
    assert income["tax"] == pytest.approx(0.0)
    assert income["profit_after_tax"] == pytest.approx(income["profit_before_tax"])


def test_reporting_kpis(workflow) -> None:
    income = workflow.financial.income_statement.set_index("line_item")["amount"].to_dict()
    kpis = workflow.financial.kpis.set_index("metric")["value"].to_dict()

    assert kpis["combined_ratio"] == pytest.approx(
        (income["net_claims_incurred"] + income["expenses"]) / income["net_earned_premium"]
    )
    assert kpis["return_on_capital"] == pytest.approx(
        income["profit_before_tax"] / workflow.capital.standard_formula.summary["scr"]
    )


def test_solvency_ii_style_balance_sheet_excess_and_tier(workflow) -> None:
    balance = workflow.financial.balance_sheet.set_index("line_item")["amount"].to_dict()

    assert balance["excess_assets_over_liabilities"] == pytest.approx(
        balance["total_assets"] - balance["total_liabilities"]
    )
    assert balance["tier_1_unrestricted"] == pytest.approx(balance["excess_assets_over_liabilities"])


def test_reporting_reconciliations_pass(workflow) -> None:
    assert set(workflow.financial.reconciliations["status"]) == {"pass"}
