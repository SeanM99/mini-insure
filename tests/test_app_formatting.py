"""Tests for shared Streamlit display formatting helpers."""

from __future__ import annotations

from app.components.formatting import (
    format_count,
    format_eur_k,
    format_eur_m,
    format_eur_raw,
    format_pct,
)


def test_compact_eur_formatting_examples() -> None:
    assert format_eur_m(1_200_000) == "EUR 1.2m"
    assert format_eur_k(45_000) == "EUR 45k"
    assert format_eur_raw(1_234_567) == "EUR 1,234,567"
    assert format_eur_m(10_000_000, decimals=0) == "EUR 10m"


def test_percentage_and_count_formatting_examples() -> None:
    assert format_pct(0.684) == "68.4%"
    assert format_count(60_000, label="policies") == "60,000 policies"
