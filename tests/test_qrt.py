from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.validation import has_blocking_errors, validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow


@pytest.fixture(scope="module")
def workflow():
    return calculate_reporting_workflow(
        scenario_name="QRT Test",
        portfolio_mode="small",
        policies_per_year=500,
        reserve_risk_simulations=25,
        capital_simulations=25,
    )


@pytest.fixture(scope="module")
def qrt_pack(workflow) -> dict[str, pd.DataFrame]:
    return generate_qrt_pack(
        capital=workflow.capital,
        financial=workflow.financial,
        assumptions=workflow.assumptions,
        scenario_name=workflow.scenario_state.scenario_name,
    )


def test_qrt_pack_contains_required_templates(qrt_pack) -> None:
    assert {
        "S.01.01.02",
        "S.01.02.01",
        "S.02.01.02",
        "S.05.01.02",
        "S.06.02.01",
        "S.06.03.01",
        "S.08.01.01",
        "S.17.01.02",
        "S.23.01.01",
        "S.28.01.01",
        "Mappings",
    }.issubset(qrt_pack)


def test_not_applicable_templates_are_flagged(qrt_pack) -> None:
    matrix = qrt_pack["S.01.01.02"].set_index("template")["status"].to_dict()

    assert matrix["S.12.01.02"] == "not applicable"
    assert matrix["S.28.02.01"] == "not applicable"


def test_mapping_layer_is_traceable(qrt_pack) -> None:
    mappings = qrt_pack["Mappings"]

    assert {"template", "qrt_field", "source_field"}.issubset(mappings.columns)
    assert (mappings["source_field"].str.len() > 0).all()


def test_valid_qrt_pack_has_no_blocking_errors(workflow, qrt_pack) -> None:
    validation = validate_qrt_pack(qrt_pack, capital=workflow.capital, financial=workflow.financial)
    summary = validation_summary(validation)

    assert summary["error_count"] == 0
    assert not has_blocking_errors(validation)


def test_dnb006_is_warning_not_blocking(workflow, qrt_pack) -> None:
    broken = {name: frame.copy() for name, frame in qrt_pack.items()}
    broken["S.05.01.02"].loc[0, "gross_written_premium"] += 10_000.0

    validation = validate_qrt_pack(broken, capital=workflow.capital, financial=workflow.financial)
    dnb006 = validation.loc[validation["rule_id"] == "DNB006"]

    assert not dnb006.empty
    assert set(dnb006["severity"]) == {"warning"}
    assert not has_blocking_errors(dnb006)


def test_qrt_blocking_validation_rule(workflow, qrt_pack) -> None:
    broken = {name: frame.copy() for name, frame in qrt_pack.items()}
    mask = broken["S.02.01.02"]["item"] == "total_assets"
    broken["S.02.01.02"].loc[mask, "amount"] += 10_000.0

    validation = validate_qrt_pack(broken, capital=workflow.capital, financial=workflow.financial)

    assert "DNB003" in set(validation["rule_id"])
    assert has_blocking_errors(validation)


def test_dnb008_requires_eur_and_rounding(workflow, qrt_pack) -> None:
    broken = {name: frame.copy() for name, frame in qrt_pack.items()}
    broken["S.06.02.01"].loc[0, "market_value"] = 12.34

    validation = validate_qrt_pack(broken, capital=workflow.capital, financial=workflow.financial)

    assert "DNB008" in set(validation["rule_id"])
    assert has_blocking_errors(validation)
