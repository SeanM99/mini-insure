"""Correlation aggregation helpers for capital modules."""

from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_with_correlation(charges: dict[str, float], correlation_matrix: pd.DataFrame) -> float:
    """Aggregate capital charges with a square-root correlation formula."""
    if not charges:
        return 0.0
    names = list(charges)
    vector = np.array([max(float(charges[name]), 0.0) for name in names], dtype=float)
    corr = correlation_matrix.loc[names, names].to_numpy(dtype=float)
    return float(np.sqrt(max(vector @ corr @ vector, 0.0)))


def two_lob_correlation_matrix(lob_names: list[str], off_diagonal: float) -> pd.DataFrame:
    """Return a simple LoB correlation matrix with one off-diagonal value."""
    matrix = pd.DataFrame(np.eye(len(lob_names)), index=lob_names, columns=lob_names)
    for left in lob_names:
        for right in lob_names:
            if left != right:
                matrix.loc[left, right] = float(off_diagonal)
    return matrix
