"""Streamlit Home page for MiniInsure Europe NL."""

from __future__ import annotations

import streamlit as st

from app.components.layout import page_shell
from miniinsure.utils import PROJECT_NAME


def render_home() -> None:
    """Render the Home page."""
    context = page_shell(
        page_title=PROJECT_NAME,
        subtitle="Educational Solvency II-style platform for a synthetic NL motor insurer.",
        default_portfolio_mode="medium",
    )

    col_valuation, col_quarter, col_mode = st.columns(3)
    col_valuation.metric("Valuation date", context.valuation_date)
    col_quarter.metric("Reporting quarter", context.reporting_quarter)
    col_mode.metric("Portfolio mode", context.portfolio_mode)

    st.markdown("### Assumption Hash")
    st.code(context.assumption_hash, language="text")

    st.download_button(
        "Download scenario metadata JSON",
        data=context.scenario_state.metadata_json(context.assumptions),
        file_name=f"{context.scenario_name.lower().replace(' ', '_')}_metadata.json",
        mime="application/json",
    )

    st.markdown("### Scope Summary")
    st.write(
        "MiniInsure Europe NL is a modular monolith foundation for a synthetic "
        "Netherlands-based motor insurer. Later phases can add auditable actuarial "
        "modules under the `miniinsure` package while keeping Streamlit pages focused "
        "on presentation, scenario state, cached calls, charts, formatting, and downloads."
    )

    st.warning(
        "Regulatory filing is out of scope. Future QRT-style outputs, if added, must "
        "be mock/QRT-shaped only and must not use or imply real XBRL submission."
    )


if __name__ == "__main__":
    render_home()
