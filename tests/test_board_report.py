from __future__ import annotations

from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow, generate_board_risk_report_markdown


def test_board_report_contains_required_sections() -> None:
    workflow = calculate_reporting_workflow(
        scenario_name="Board Scenario",
        portfolio_mode="small",
        policies_per_year=500,
        reserve_risk_simulations=25,
        capital_simulations=25,
    )
    pack = generate_qrt_pack(
        capital=workflow.capital,
        financial=workflow.financial,
        assumptions=workflow.assumptions,
        scenario_name=workflow.scenario_state.scenario_name,
    )
    validation = validate_qrt_pack(pack, capital=workflow.capital, financial=workflow.financial)
    summary = validation_summary(validation)
    report = generate_board_risk_report_markdown(
        capital=workflow.capital,
        financial=workflow.financial,
        validation_status=str(summary["status"]),
        validation_errors=int(summary["error_count"]),
        validation_warnings=int(summary["warning_count"]),
    )

    for heading in [
        "Executive Summary",
        "Valuation Date And Scenario",
        "Own Funds And Capital Requirements",
        "Technical Provisions",
        "Reserve Risk Summary",
        "Risk Commentary",
        "Traffic-Light KRIs",
        "Validation Status",
        "Limitations",
    ]:
        assert heading in report
    assert "Board Scenario" in report
    assert "Assumption hash" in report
    assert "Generated timestamp" in report
    assert "does not create real XBRL" in report
