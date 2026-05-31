"""Display formatting helpers for Streamlit pages."""

from __future__ import annotations

import math


def format_eur(value: float, *, decimals: int = 0) -> str:
    """Format an amount in EUR."""
    amount = float(value)
    if math.isnan(amount):
        return "EUR n/a"
    return f"EUR {amount:,.{decimals}f}"


def format_percent(value: float, *, decimals: int = 1) -> str:
    """Format a ratio as a percentage."""
    ratio = float(value)
    if math.isnan(ratio):
        return "n/a"
    return f"{ratio:.{decimals}%}"


def format_count(value: int | float) -> str:
    """Format a count without decimals."""
    return f"{int(value):,}"
