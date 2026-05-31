from __future__ import annotations

import numpy as np
import pytest

from miniinsure.simulation.economic_scenarios import (
    bond_return,
    cash_return,
    deterministic_equity_return,
    discount_factor_for_month,
    equity_return,
    interpolate_risk_free_rate,
)


def test_curve_interpolation() -> None:
    assert interpolate_risk_free_rate(1.0) == 0.025
    assert interpolate_risk_free_rate(4.0) == pytest.approx(0.028)
    assert interpolate_risk_free_rate(7.5) == pytest.approx(0.030)


def test_monthly_discounting_uses_annual_effective_rates() -> None:
    assert discount_factor_for_month(12) == pytest.approx(1.0 / 1.025)


def test_cash_return() -> None:
    assert cash_return() == 0.020


def test_bond_return_calculation() -> None:
    result = bond_return(
        yield_rate=0.03,
        duration=2.0,
        interest_rate_change=0.01,
        spread_change=0.005,
    )

    assert result == pytest.approx(0.03 - 2.0 * 0.01 - 0.8 * 2.0 * 0.005)


def test_equity_return_truncation() -> None:
    assert deterministic_equity_return(-1.20) == -0.80
    rng = np.random.default_rng(1)
    draws = [equity_return(rng=rng, expected_return=-1.0, volatility=0.01) for _ in range(10)]
    assert all(draw >= -0.80 for draw in draws)
