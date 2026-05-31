"""Shared Streamlit UI components for MiniInsure."""

from app.components.badges import render_status_badge, render_validation_badges
from app.components.formatting import format_count, format_eur, format_percent
from app.components.layout import PageContext, page_shell, render_last_run_metadata

__all__ = [
    "PageContext",
    "format_count",
    "format_eur",
    "format_percent",
    "page_shell",
    "render_last_run_metadata",
    "render_status_badge",
    "render_validation_badges",
]
