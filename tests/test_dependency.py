from __future__ import annotations

import pandas as pd
import pytest

from miniinsure.risk_engine.dependency import (
    BlockingDependencyValidationError,
    fixed_correlation_matrix,
    gaussian_copula_drivers,
    validate_dependency_matrix,
)
from miniinsure.risk_engine.risk_drivers import DRIVER_CODES, risk_driver_frame


def test_fixed_matrix_psd_validation_passes() -> None:
    matrix = fixed_correlation_matrix()
    result = validate_dependency_matrix(matrix)

    assert list(matrix.index) == list(DRIVER_CODES)
    assert result.status == "pass"
    assert not result.blocking
    assert result.minimum_eigenvalue >= -1e-8


def test_invalid_matrix_triggers_blocking_error() -> None:
    invalid = pd.DataFrame(
        [[1.0, 1.0, 1.0], [1.0, 1.0, -1.0], [1.0, -1.0, 1.0]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )

    with pytest.raises(BlockingDependencyValidationError):
        validate_dependency_matrix(invalid)

    result = validate_dependency_matrix(invalid, raise_on_blocking=False)
    assert result.status == "fail"
    assert result.blocking
    assert result.minimum_eigenvalue < -1e-8


def test_gaussian_copula_driver_output_shape() -> None:
    drivers = gaussian_copula_drivers(n=5, seed=20261231)

    assert list(drivers.columns) == list(DRIVER_CODES)
    assert len(drivers) == 5


def test_risk_driver_metadata() -> None:
    drivers = risk_driver_frame()

    assert set(drivers["driver"]) == set(DRIVER_CODES)
    assert "premium frequency" in set(drivers["name"])
