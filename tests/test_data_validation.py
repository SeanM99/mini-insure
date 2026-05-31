from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from miniinsure.dnb_validation import (
    SMALL_PORTFOLIO_FIXTURE_DIR,
    load_fixture_tables,
    validate_fixture_tables,
)
from miniinsure.reserving.validation import validate_paid_triangle


def rule_ids(summary_or_messages: object) -> set[str]:
    if hasattr(summary_or_messages, "messages"):
        return {message.rule_id for message in summary_or_messages.messages}
    return {message.rule_id for message in summary_or_messages}


def fixture_tables() -> dict[str, pd.DataFrame]:
    return load_fixture_tables(SMALL_PORTFOLIO_FIXTURE_DIR)


def test_valid_fixture_passes_expected_summary() -> None:
    expected_path = Path(SMALL_PORTFOLIO_FIXTURE_DIR) / "expected_validation_summary.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    summary = validate_fixture_tables(fixture_tables())

    assert summary.to_dict() == expected


def test_dq001_policy_premiums_non_negative() -> None:
    tables = fixture_tables()
    tables["policies"].loc[0, "written_premium"] = -1

    summary = validate_fixture_tables(tables)

    assert "DQ001" in rule_ids(summary)
    assert summary.export_blocked


def test_dq002_exposure_in_unit_interval() -> None:
    tables = fixture_tables()
    tables["policies"].loc[0, "exposure"] = 0

    summary = validate_fixture_tables(tables)

    assert "DQ002" in rule_ids(summary)


def test_dq003_claim_ultimate_non_negative() -> None:
    tables = fixture_tables()
    tables["claims"].loc[0, "ultimate_claim"] = -10

    summary = validate_fixture_tables(tables)

    assert "DQ003" in rule_ids(summary)


def test_dq004_payment_date_after_accident_date() -> None:
    tables = fixture_tables()
    tables["payments"].loc[0, "payment_date"] = "2026-03-01"

    summary = validate_fixture_tables(tables)

    assert "DQ004" in rule_ids(summary)


def test_dq005_report_date_after_accident_date() -> None:
    tables = fixture_tables()
    tables["claims"].loc[0, "report_date"] = "2026-03-01"

    summary = validate_fixture_tables(tables)

    assert "DQ005" in rule_ids(summary)


def test_dq006_settlement_date_after_report_date() -> None:
    tables = fixture_tables()
    tables["claims"].loc[1, "settlement_date"] = "2026-04-01"

    summary = validate_fixture_tables(tables)

    assert "DQ006" in rule_ids(summary)


def test_dq007_cumulative_paid_triangle_non_decreasing() -> None:
    triangle = pd.DataFrame(
        {
            "origin_year": [2026, 2026, 2026],
            "development_period": [1, 2, 3],
            "cumulative_paid": [100.0, 90.0, 120.0],
        }
    )

    messages = validate_paid_triangle(triangle)

    assert "DQ007" in rule_ids(messages)


def test_dq008_case_reserve_non_negative() -> None:
    tables = fixture_tables()
    tables["case_reserves"].loc[0, "case_reserve"] = -1

    summary = validate_fixture_tables(tables)

    assert "DQ008" in rule_ids(summary)


def test_dq009_reinsurance_recovery_limited_by_treaty_terms() -> None:
    tables = fixture_tables()
    tables["reinsurance_recoveries"].loc[0, "recovery_amount"] = 250000

    summary = validate_fixture_tables(tables)

    assert "DQ009" in rule_ids(summary)


def test_dq010_asset_weights_sum_to_one() -> None:
    tables = fixture_tables()
    tables["asset_portfolio"].loc[0, "portfolio_weight"] = 0.36

    summary = validate_fixture_tables(tables)

    assert "DQ010" in rule_ids(summary)


def test_primary_key_failure_blocks_export() -> None:
    tables = fixture_tables()
    tables["policies"] = pd.concat(
        [tables["policies"], tables["policies"].iloc[[0]]],
        ignore_index=True,
    )

    summary = validate_fixture_tables(tables)

    assert "PK001" in rule_ids(summary)
    assert summary.export_blocked


def test_claim_policy_foreign_key_failure() -> None:
    tables = fixture_tables()
    tables["claims"].loc[0, "policy_id"] = "P9999"

    summary = validate_fixture_tables(tables)

    assert "FK001" in rule_ids(summary)


def test_payment_claim_foreign_key_failure() -> None:
    tables = fixture_tables()
    tables["payments"].loc[0, "claim_id"] = "C9999"

    summary = validate_fixture_tables(tables)

    assert "FK001" in rule_ids(summary)


def test_missing_column_failure() -> None:
    tables = fixture_tables()
    tables["policies"] = tables["policies"].drop(columns=["exposure"])

    summary = validate_fixture_tables(tables)

    assert "SCHEMA001" in rule_ids(summary)
    assert summary.export_blocked
