"""Large bodily injury severity helpers."""

from __future__ import annotations

import numpy as np

LARGE_BI_THRESHOLD = 100_000.0
PARETO_ALPHA = 2.2
PARETO_SCALE = 90_000.0


def simulate_large_bi_gross(
    rng: np.random.Generator,
    size: int,
) -> np.ndarray:
    """Simulate large BI gross severity as threshold plus Pareto excess."""
    excess = rng.pareto(PARETO_ALPHA, size=size) * PARETO_SCALE
    return LARGE_BI_THRESHOLD + excess


def expected_large_bi_gross_mean() -> float:
    """Return the theoretical large BI gross mean."""
    return LARGE_BI_THRESHOLD + PARETO_SCALE / (PARETO_ALPHA - 1.0)
