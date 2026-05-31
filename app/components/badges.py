"""Consistent status badges for Streamlit pages."""

from __future__ import annotations

import streamlit as st

from .formatting import format_count


BADGE_STYLES = {
    "PASS": ("#0f766e", "#ccfbf1"),
    "WARNING": ("#92400e", "#fef3c7"),
    "BLOCKED": ("#991b1b", "#fee2e2"),
    "MOCK ONLY": ("#5b21b6", "#ede9fe"),
    "QUICK MODE": ("#1d4ed8", "#dbeafe"),
    "OBSERVED DATA ONLY": ("#166534", "#dcfce7"),
}


def render_badge(label: str, *, status: str | None = None) -> None:
    """Render one color-coded badge."""
    normalized = (status or label).strip().upper()
    fg, bg = BADGE_STYLES.get(normalized, ("#374151", "#f3f4f6"))
    st.markdown(
        (
            f"<span style='display:inline-block;padding:0.22rem 0.55rem;"
            f"border-radius:999px;background:{bg};color:{fg};font-size:0.78rem;"
            f"font-weight:700;letter-spacing:0.02em;margin:0 0.35rem 0.35rem 0;'>"
            f"{label.upper()}</span>"
        ),
        unsafe_allow_html=True,
    )


def render_badge_row(labels: list[str]) -> None:
    """Render a compact row of standard badges."""
    pieces = []
    for label in labels:
        normalized = label.strip().upper()
        fg, bg = BADGE_STYLES.get(normalized, ("#374151", "#f3f4f6"))
        pieces.append(
            f"<span style='display:inline-block;padding:0.22rem 0.55rem;"
            f"border-radius:999px;background:{bg};color:{fg};font-size:0.78rem;"
            f"font-weight:700;letter-spacing:0.02em;margin:0 0.35rem 0.35rem 0;'>"
            f"{normalized}</span>"
        )
    st.markdown("".join(pieces), unsafe_allow_html=True)


def render_status_badge(label: str, status: str, *, detail: str | None = None) -> None:
    """Render a compact status badge using Streamlit status colors."""
    normalized = str(status).strip().lower()
    badge_status = {
        "pass": "PASS",
        "passed": "PASS",
        "ok": "PASS",
        "green": "PASS",
        "warning": "WARNING",
        "warn": "WARNING",
        "amber": "WARNING",
        "fail": "BLOCKED",
        "failed": "BLOCKED",
        "error": "BLOCKED",
        "blocked": "BLOCKED",
        "red": "BLOCKED",
    }.get(normalized, normalized.upper())
    text = f"{label}: {normalized.upper()}"
    if detail:
        text = f"{text}. {detail}"
    render_badge(badge_status)
    if normalized in {"pass", "passed", "ok", "green"}:
        st.success(text)
    elif normalized in {"warning", "warn", "amber"}:
        st.warning(text)
    elif normalized in {"fail", "failed", "error", "blocked", "red"}:
        st.error(text)
    else:
        st.info(text)


def render_validation_badges(
    *,
    status: str,
    error_count: int = 0,
    warning_count: int = 0,
    label: str = "Validation",
) -> None:
    """Render the standard validation summary strip."""
    columns = st.columns(3)
    columns[0].metric(f"{label} status", str(status).upper())
    columns[1].metric("Blocking errors", format_count(int(error_count), "errors"))
    columns[2].metric("Warnings", format_count(int(warning_count), "warnings"))
    if int(error_count) > 0:
        render_status_badge(label, "blocked", detail="Errors block export and reporting actions.")
    elif int(warning_count) > 0:
        render_status_badge(label, "warning", detail="Warnings are visible but do not block export.")
    else:
        render_status_badge(label, "pass")
