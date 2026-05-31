"""Cash-flow timing and discounting helpers for technical provisions."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

DEFAULT_RISK_FREE_CURVE: dict[float, float] = {
    0.0: 0.018,
    1.0: 0.020,
    2.0: 0.021,
    3.0: 0.022,
    5.0: 0.024,
    10.0: 0.026,
}


def interpolated_annual_rate(
    maturity_years: float,
    curve: Mapping[float, float] | None = None,
) -> float:
    """Return an annual effective risk-free rate by flat extrapolation and linear interpolation."""
    curve = curve or DEFAULT_RISK_FREE_CURVE
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
            if right_maturity == left_maturity:
                return right_rate
            weight = (maturity - left_maturity) / (right_maturity - left_maturity)
            return left_rate + weight * (right_rate - left_rate)
    return points[-1][1]


def discount_factor_for_month(
    month_offset: int | float,
    curve: Mapping[float, float] | None = None,
) -> float:
    """Discount a future monthly cash flow using annual effective rates."""
    maturity_years = max(float(month_offset), 0.0) / 12.0
    if maturity_years == 0.0:
        return 1.0
    rate = interpolated_annual_rate(maturity_years, curve)
    return float(1.0 / np.power(1.0 + rate, maturity_years))


def add_discount_factors(
    cashflows: pd.DataFrame,
    *,
    month_column: str = "month_offset",
    amount_column: str = "cashflow",
    curve: Mapping[float, float] | None = None,
) -> pd.DataFrame:
    """Add discount factor and present-value columns to a monthly cash-flow table."""
    projected = cashflows.copy()
    if projected.empty:
        projected["discount_factor"] = pd.Series(dtype=float)
        projected["present_value"] = pd.Series(dtype=float)
        return projected
    projected["discount_factor"] = projected[month_column].apply(
        lambda month: discount_factor_for_month(month, curve)
    )
    projected["present_value"] = projected[amount_column].astype(float) * projected["discount_factor"]
    return projected


def present_value(
    cashflows: pd.DataFrame,
    *,
    month_column: str = "month_offset",
    amount_column: str = "cashflow",
    curve: Mapping[float, float] | None = None,
) -> float:
    """Return the present value of a monthly cash-flow table."""
    if cashflows.empty:
        return 0.0
    return float(
        add_discount_factors(
            cashflows,
            month_column=month_column,
            amount_column=amount_column,
            curve=curve,
        )["present_value"].sum()
    )
