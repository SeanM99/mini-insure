"""Shared deterministic project utilities."""

from __future__ import annotations

from typing import Any

import numpy as np

PROJECT_NAME = "MiniInsure Europe NL"
APP_VERSION = "0.1.0"
VALUATION_DATE = "2026-12-31"
REPORTING_QUARTER = "2026 Q4"
MASTER_SEED = 20261231


def make_rng(seed: int | None = None) -> np.random.Generator:
    """Create a deterministic NumPy random generator."""
    return np.random.default_rng(MASTER_SEED if seed is None else seed)


def project_metadata() -> dict[str, Any]:
    """Return stable Phase 1 project metadata for UI and audit outputs."""
    return {
        "project_name": PROJECT_NAME,
        "app_version": APP_VERSION,
        "valuation_date": VALUATION_DATE,
        "reporting_quarter": REPORTING_QUARTER,
        "master_seed": MASTER_SEED,
        "educational_only": True,
        "real_xbrl_enabled": False,
    }
