"""Display formatting helpers for Streamlit pages."""

from __future__ import annotations

import math
from typing import Any


def _number_or_none(value: Any) -> float | None:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(amount) or math.isinf(amount):
        return None
    return amount


def _trim_decimal(value: float, *, decimals: int = 1) -> str:
    text = f"{value:.{decimals}f}"
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def format_eur_m(value: float | int | None, *, decimals: int = 1) -> str:
    """Format a EUR amount in millions for KPI cards."""
    amount = _number_or_none(value)
    if amount is None:
        return "EUR n/a"
    return f"EUR {_trim_decimal(amount / 1_000_000, decimals=decimals)}m"


def format_eur_k(value: float | int | None, *, decimals: int = 0) -> str:
    """Format a EUR amount in thousands for compact displays."""
    amount = _number_or_none(value)
    if amount is None:
        return "EUR n/a"
    return f"EUR {_trim_decimal(amount / 1_000, decimals=decimals)}k"


def format_eur_raw(value: float | int | None, *, decimals: int = 0) -> str:
    """Format a raw EUR amount with thousands separators."""
    amount = _number_or_none(value)
    if amount is None:
        return "EUR n/a"
    return f"EUR {amount:,.{decimals}f}"


def format_pct(value: float | int | None, *, decimals: int = 1) -> str:
    """Format a ratio as a percentage."""
    ratio = _number_or_none(value)
    if ratio is None:
        return "n/a"
    return f"{ratio:.{decimals}%}"


def format_count(value: int | float | None, label: str | None = None) -> str:
    """Format a count, optionally with a display label."""
    amount = _number_or_none(value)
    text = "n/a" if amount is None else f"{int(round(amount)):,}"
    if label:
        return f"{text} {label}"
    return text


def format_eur(value: float | int | None, *, decimals: int = 0) -> str:
    """Backward-compatible raw EUR formatter."""
    return format_eur_raw(value, decimals=decimals)


def format_percent(value: float | int | None, *, decimals: int = 1) -> str:
    """Backward-compatible percentage formatter."""
    return format_pct(value, decimals=decimals)
