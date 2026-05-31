"""Consistent status badges for Streamlit pages."""

from __future__ import annotations

import streamlit as st


def render_status_badge(label: str, status: str, *, detail: str | None = None) -> None:
    """Render a compact status badge using Streamlit status colors."""
    normalized = str(status).strip().lower()
    text = f"{label}: {normalized.upper()}"
    if detail:
        text = f"{text}. {detail}"
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
    columns[1].metric("Blocking errors", int(error_count))
    columns[2].metric("Warnings", int(warning_count))
    if int(error_count) > 0:
        render_status_badge(label, "blocked", detail="Errors block export and reporting actions.")
    elif int(warning_count) > 0:
        render_status_badge(label, "warning", detail="Warnings are visible but do not block export.")
    else:
        render_status_badge(label, "pass")
