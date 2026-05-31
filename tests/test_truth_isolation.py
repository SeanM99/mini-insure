from __future__ import annotations

import pytest

from miniinsure.simulation.synthetic_reality import (
    HIDDEN_TRUTH_COLUMNS,
    generate_synthetic_reality,
    load_synthetic_truth_for_diagnostics_only,
    observed_model_inputs,
)


def test_hidden_truth_not_present_in_observed_snapshot() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)

    observed_columns = set(reality.observed_valuation_snapshot.columns)

    assert HIDDEN_TRUTH_COLUMNS.isdisjoint(observed_columns)
    assert not any("ultimate" in column for column in observed_columns)
    assert not any(column.startswith("true_") for column in observed_columns)


def test_observed_model_inputs_do_not_include_hidden_truth_fields() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)
    observed_inputs = observed_model_inputs(reality)

    assert "synthetic_truth" not in observed_inputs
    for table in observed_inputs.values():
        columns = set(table.columns)
        assert HIDDEN_TRUTH_COLUMNS.isdisjoint(columns)
        assert not any(column.startswith("true_") for column in columns)


def test_truth_loader_requires_explicit_diagnostics_acknowledgement() -> None:
    reality = generate_synthetic_reality(portfolio_mode="small", policies_per_year=500)

    with pytest.raises(PermissionError):
        load_synthetic_truth_for_diagnostics_only(reality)

    truth = load_synthetic_truth_for_diagnostics_only(
        reality,
        acknowledge_truth_isolation=True,
    )
    assert HIDDEN_TRUTH_COLUMNS.issubset(set(truth.columns))
