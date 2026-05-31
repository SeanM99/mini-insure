from __future__ import annotations

import miniinsure


def test_package_imports_with_phase_1_metadata() -> None:
    assert miniinsure.PROJECT_NAME == "MiniInsure Europe NL"
    assert miniinsure.VALUATION_DATE == "2026-12-31"
    assert miniinsure.REPORTING_QUARTER == "2026 Q4"
    assert miniinsure.MASTER_SEED == 20261231


def test_make_rng_is_deterministic() -> None:
    first = miniinsure.make_rng().integers(0, 1_000_000, size=5)
    second = miniinsure.make_rng().integers(0, 1_000_000, size=5)

    assert first.tolist() == second.tolist()
