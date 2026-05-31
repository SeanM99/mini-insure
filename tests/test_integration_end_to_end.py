from __future__ import annotations

from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow


def test_end_to_end_reporting_sequence() -> None:
    workflow = calculate_reporting_workflow(
        scenario_name="End To End",
        portfolio_mode="small",
        policies_per_year=500,
        reserve_risk_simulations=25,
        capital_simulations=25,
    )

    assert len(workflow.capital.policies) > 0
    assert not workflow.capital.reserving_results.empty
    assert workflow.capital.technical_provisions.summary["reconciliation_status"] == "pass"
    assert not workflow.capital.reserve_risk.summary.empty
    assert not workflow.capital.one_year_capital.summary.empty
    assert workflow.capital.standard_formula.summary["scr"] > 0.0
    assert workflow.capital.mcr.mcr > 0.0
    assert workflow.capital.own_funds["eligible_own_funds"] > 0.0

    pack = generate_qrt_pack(
        capital=workflow.capital,
        financial=workflow.financial,
        assumptions=workflow.assumptions,
        scenario_name=workflow.scenario_state.scenario_name,
    )
    validation = validate_qrt_pack(pack, capital=workflow.capital, financial=workflow.financial)
    summary = validation_summary(validation)

    assert "S.28.01.01" in pack
    assert summary["error_count"] == 0
