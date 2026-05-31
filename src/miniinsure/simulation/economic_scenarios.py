"""Economic assumptions and simple scenario return formulas."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

RISK_FREE_CURVE: dict[float, float] = {
    1.0: 0.025,
    2.0: 0.026,
    3.0: 0.027,
    5.0: 0.029,
    10.0: 0.031,
}

CASH_RETURN = 0.020
EQUITY_EXPECTED_RETURN = 0.065
EQUITY_VOLATILITY = 0.18
EQUITY_RETURN_FLOOR = -0.80


def interpolate_risk_free_rate(
    maturity_years: float,
    curve: Mapping[float, float] | None = None,
) -> float:
    """Linearly interpolate annual effective risk-free rates."""
    curve = curve or RISK_FREE_CURVE
    points = sorted((float(maturity), float(rate)) for maturity, rate in curve.items())
    if not points:
        raise ValueError("risk-free curve must contain at least one point")

    maturity = max(float(maturity_years), 0.0)
    if maturity <= points[0][0]:
        return points[0][1]
    if maturity >= points[-1][0]:
        return points[-1][1]

    for (left_maturity, left_rate), (right_maturity, right_rate) in zip(points[:-1], points[1:], strict=False):
        if left_maturity <= maturity <= right_maturity:
            weight = (maturity - left_maturity) / (right_maturity - left_maturity)
            return float(left_rate + weight * (right_rate - left_rate))
    return points[-1][1]


def discount_factor_for_month(
    month_offset: int | float,
    curve: Mapping[float, float] | None = None,
) -> float:
    """Discount monthly-timed cash flows using annual effective rates."""
    maturity_years = max(float(month_offset), 0.0) / 12.0
    if maturity_years == 0.0:
        return 1.0
    rate = interpolate_risk_free_rate(maturity_years, curve)
    return float(1.0 / np.power(1.0 + rate, maturity_years))


def cash_return() -> float:
    """Cash return deterministic at 2.0%."""
    return CASH_RETURN


def bond_return(
    *,
    yield_rate: float,
    duration: float,
    interest_rate_change: float,
    spread_change: float,
) -> float:
    """Bond return = yield - duration * IR change - 0.8 * duration * spread change."""
    return float(yield_rate - duration * interest_rate_change - 0.8 * duration * spread_change)


def equity_return(
    *,
    rng: np.random.Generator,
    expected_return: float = EQUITY_EXPECTED_RETURN,
    volatility: float = EQUITY_VOLATILITY,
) -> float:
    """Equity return as a normal return truncated below -80%."""
    return float(max(rng.normal(expected_return, volatility), EQUITY_RETURN_FLOOR))


def deterministic_equity_return(raw_return: float) -> float:
    """Apply the equity return floor to an externally supplied return."""
    return float(max(float(raw_return), EQUITY_RETURN_FLOOR))


def risk_free_curve_frame(curve: Mapping[float, float] | None = None) -> pd.DataFrame:
    """Return the economic risk-free curve as a table."""
    curve = curve or RISK_FREE_CURVE
    return pd.DataFrame(
        [
            {"maturity_years": float(maturity), "annual_effective_rate": float(rate)}
            for maturity, rate in sorted(curve.items())
        ]
    )
