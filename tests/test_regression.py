from __future__ import annotations

import zipfile

import pytest

from miniinsure.assumptions import load_effective_assumptions, stable_assumption_hash
from miniinsure.qrt.export import export_qrt_pack_to_zip, generate_qrt_pack, qrt_pack_to_zip_bytes
from miniinsure.qrt.mappings import export_names
from miniinsure.reporting import calculate_reporting_workflow, generate_board_risk_report_markdown
from miniinsure.simulation.synthetic_reality import HIDDEN_TRUTH_COLUMNS, generate_synthetic_reality, observed_model_inputs


@pytest.fixture(scope="module")
def workflow():
    return calculate_reporting_workflow(
        scenario_name="Regression Scenario",
        portfolio_mode="small",
        policies_per_year=500,
        reserve_risk_simulations=25,
        capital_simulations=25,
    )


@pytest.fixture(scope="module")
def qrt_pack(workflow):
    return generate_qrt_pack(
        capital=workflow.capital,
        financial=workflow.financial,
        assumptions=workflow.assumptions,
        scenario_name=workflow.scenario_state.scenario_name,
    )


def test_scenario_hash_stability() -> None:
    assumptions = load_effective_assumptions()

    assert stable_assumption_hash(assumptions) == stable_assumption_hash(assumptions)


def test_export_naming_regression() -> None:
    names = export_names("Regression Scenario")

    assert names.qrt_xlsx == "miniinsure_europe_nl_qrt_mock_2026Q4_regression_scenario.xlsx"
    assert names.qrt_zip == "miniinsure_europe_nl_qrt_mock_2026Q4_regression_scenario.zip"
    assert names.board_report_md == "miniinsure_europe_nl_board_risk_report_regression_scenario.md"
    assert names.metadata_json == "scenario_metadata.json"


def test_no_real_xbrl_output_in_zip(workflow, qrt_pack) -> None:
    report = generate_board_risk_report_markdown(capital=workflow.capital, financial=workflow.financial)
    payload = qrt_pack_to_zip_bytes(
        pack=qrt_pack,
        board_report_markdown=report,
        scenario_metadata_json=workflow.scenario_state.metadata_json(workflow.assumptions),
        scenario_name=workflow.scenario_state.scenario_name,
    )

    zip_path = workflow.scenario_state.scenario_name
    assert zip_path
    with zipfile.ZipFile(__import__("io").BytesIO(payload)) as archive:
        names = archive.namelist()
    assert any(name.endswith(".xlsx") for name in names)
    assert "scenario_metadata.json" in names
    assert not any(name.lower().endswith((".xbrl", ".xml")) for name in names)


def test_hidden_truth_not_in_reporting_inputs() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=200)

    for table in observed_model_inputs(reality).values():
        assert HIDDEN_TRUTH_COLUMNS.isdisjoint(table.columns)
        assert not any(column.startswith("true_") for column in table.columns)


def test_key_balance_sheet_reconciliations(workflow) -> None:
    balance = workflow.financial.balance_sheet.set_index("line_item")["amount"].to_dict()
    tp = workflow.capital.technical_provisions.summary

    assert balance["total_assets"] - balance["total_liabilities"] == pytest.approx(
        balance["excess_assets_over_liabilities"]
    )
    assert tp["gross_technical_provisions"] - tp["reinsurance_recoverables"] == pytest.approx(
        tp["net_technical_provisions"]
    )


def test_qrt_validation_blocks_export(tmp_path, workflow, qrt_pack) -> None:
    broken = {name: frame.copy() for name, frame in qrt_pack.items()}
    mask = broken["S.23.01.01"]["item"] == "eligible_own_funds_to_meet_scr"
    broken["S.23.01.01"].loc[mask, "amount"] = 1.0

    with pytest.raises(ValueError, match="blocked"):
        export_qrt_pack_to_zip(
            pack=broken,
            board_report_markdown="mock",
            scenario_metadata_json="{}",
            scenario_name=workflow.scenario_state.scenario_name,
            output_dir=tmp_path,
            capital=workflow.capital,
            financial=workflow.financial,
        )
