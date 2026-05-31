"""Gaussian copula dependency model validation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.risk_engine.risk_drivers import DRIVER_CODES

PSD_TOLERANCE = -1e-8


class BlockingDependencyValidationError(ValueError):
    """Raised when the dependency matrix fails a blocking validation rule."""


@dataclass(frozen=True)
class DependencyValidationResult:
    """Dependency matrix validation result."""

    status: str
    minimum_eigenvalue: float
    message: str
    blocking: bool

    def to_dict(self) -> dict[str, float | str | bool]:
        return {
            "status": self.status,
            "minimum_eigenvalue": self.minimum_eigenvalue,
            "message": self.message,
            "blocking": self.blocking,
        }


def fixed_correlation_matrix() -> pd.DataFrame:
    """Return the fixed whitepaper-style Gaussian copula correlation matrix."""
    codes = list(DRIVER_CODES)
    matrix = pd.DataFrame(np.eye(len(codes)), index=codes, columns=codes)

    pairs = {
        ("PF", "PS"): 0.35,
        ("PF", "RD"): 0.25,
        ("PF", "CI"): 0.30,
        ("PF", "CAT"): 0.20,
        ("PF", "EQ"): -0.10,
        ("PF", "IR"): 0.05,
        ("PF", "SP"): 0.15,
        ("PF", "EX"): 0.20,
        ("PF", "LV"): -0.25,
        ("PF", "RDf"): 0.10,
        ("PS", "RD"): 0.30,
        ("PS", "CI"): 0.45,
        ("PS", "CAT"): 0.25,
        ("PS", "EQ"): -0.10,
        ("PS", "IR"): 0.05,
        ("PS", "SP"): 0.20,
        ("PS", "EX"): 0.30,
        ("PS", "LV"): -0.10,
        ("PS", "RDf"): 0.10,
        ("RD", "CI"): 0.40,
        ("RD", "CAT"): 0.25,
        ("RD", "EQ"): -0.15,
        ("RD", "IR"): 0.10,
        ("RD", "SP"): 0.25,
        ("RD", "EX"): 0.25,
        ("RD", "LV"): -0.15,
        ("RD", "RDf"): 0.20,
        ("CI", "CAT"): 0.20,
        ("CI", "EQ"): -0.05,
        ("CI", "IR"): 0.15,
        ("CI", "SP"): 0.20,
        ("CI", "EX"): 0.50,
        ("CI", "LV"): -0.05,
        ("CI", "RDf"): 0.10,
        ("CAT", "EQ"): -0.05,
        ("CAT", "IR"): 0.00,
        ("CAT", "SP"): 0.15,
        ("CAT", "EX"): 0.10,
        ("CAT", "LV"): -0.05,
        ("CAT", "RDf"): 0.25,
        ("EQ", "IR"): -0.25,
        ("EQ", "SP"): -0.40,
        ("EQ", "EX"): -0.10,
        ("EQ", "LV"): 0.25,
        ("EQ", "RDf"): -0.30,
        ("IR", "SP"): 0.35,
        ("IR", "EX"): 0.20,
        ("IR", "LV"): -0.10,
        ("IR", "RDf"): 0.10,
        ("SP", "EX"): 0.20,
        ("SP", "LV"): -0.20,
        ("SP", "RDf"): 0.40,
        ("EX", "LV"): -0.10,
        ("EX", "RDf"): 0.10,
        ("LV", "RDf"): -0.10,
    }
    for (left, right), value in pairs.items():
        matrix.loc[left, right] = value
        matrix.loc[right, left] = value
    validate_dependency_matrix(matrix, raise_on_blocking=True)
    return matrix


def validate_dependency_matrix(
    matrix: pd.DataFrame,
    *,
    raise_on_blocking: bool = True,
) -> DependencyValidationResult:
    """Validate symmetry, unit diagonal, and positive semidefiniteness."""
    numeric = matrix.astype(float)
    if list(numeric.index) != list(numeric.columns):
        raise BlockingDependencyValidationError("dependency matrix rows and columns must use the same driver order")
    if not np.allclose(numeric.values, numeric.values.T, atol=1e-12):
        raise BlockingDependencyValidationError("dependency matrix must be symmetric")
    if not np.allclose(np.diag(numeric.values), 1.0, atol=1e-12):
        raise BlockingDependencyValidationError("dependency matrix diagonal must be 1.0")
    if (np.abs(numeric.values) > 1.0 + 1e-12).any():
        raise BlockingDependencyValidationError("dependency correlations must be between -1 and 1")

    eigenvalues = np.linalg.eigvalsh(numeric.values)
    minimum = float(eigenvalues.min())
    if minimum < PSD_TOLERANCE:
        result = DependencyValidationResult(
            status="fail",
            minimum_eigenvalue=minimum,
            message="blocking validation error: dependency matrix is not positive semidefinite",
            blocking=True,
        )
        if raise_on_blocking:
            raise BlockingDependencyValidationError(result.message)
        return result

    return DependencyValidationResult(
        status="pass",
        minimum_eigenvalue=minimum,
        message="dependency matrix is positive semidefinite",
        blocking=False,
    )


def gaussian_copula_drivers(
    *,
    n: int,
    seed: int,
    correlation_matrix: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate standard-normal Gaussian copula drivers."""
    matrix = correlation_matrix if correlation_matrix is not None else fixed_correlation_matrix()
    validate_dependency_matrix(matrix, raise_on_blocking=True)
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(
        mean=np.zeros(len(matrix)),
        cov=matrix.to_numpy(dtype=float),
        size=n,
    )
    return pd.DataFrame(draws, columns=matrix.columns)
