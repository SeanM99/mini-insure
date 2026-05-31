"""Streamlit Home page for MiniInsure Europe NL."""

from __future__ import annotations

import streamlit as st

from miniinsure.assumptions import (
    PORTFOLIO_MODES,
    ScenarioState,
    load_effective_assumptions,
    stable_assumption_hash,
)
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_assumption_snapshot(scenario_name: str, portfolio_mode: str) -> dict[str, str]:
    """Load effective assumptions for UI display and downloads."""
    scenario_state = ScenarioState(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
    )
    assumptions = load_effective_assumptions(
        ui_overrides=scenario_state.ui_assumption_overrides()
    )
    return {
        "scenario_name": scenario_state.scenario_name,
        "portfolio_mode": assumptions.portfolio_mode,
        "valuation_date": assumptions.valuation_date.isoformat(),
        "reporting_quarter": assumptions.primary_reporting_quarter,
        "assumption_hash": stable_assumption_hash(assumptions),
        "metadata_json": scenario_state.metadata_json(assumptions),
    }


def render_home() -> None:
    """Render the Home page."""
    st.set_page_config(page_title=PROJECT_NAME, layout="wide")

    st.markdown(
        """
        <style>
        main .block-container {
            padding-top: 4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(PROJECT_NAME)
    st.subheader("Educational Solvency II-style platform for a synthetic NL motor insurer")

    st.info(
        "This app is educational only. It does not produce real Solvency II filings, "
        "real QRT submissions, or real XBRL."
    )

    st.markdown("### Scenario Setup")
    col_scenario, col_portfolio = st.columns([2, 1])
    scenario_name = col_scenario.text_input("Scenario name", value="Base")
    portfolio_mode = col_portfolio.segmented_control(
        "Portfolio mode",
        options=list(PORTFOLIO_MODES),
        default="medium",
    )

    snapshot = load_assumption_snapshot(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode or "medium",
    )

    col_valuation, col_quarter, col_mode = st.columns(3)
    col_valuation.metric("Valuation date", snapshot["valuation_date"])
    col_quarter.metric("Reporting quarter", snapshot["reporting_quarter"])
    col_mode.metric("Portfolio mode", snapshot["portfolio_mode"])

    st.markdown("### Assumption Hash")
    st.code(snapshot["assumption_hash"], language="text")

    st.download_button(
        "Download scenario metadata JSON",
        data=snapshot["metadata_json"],
        file_name=f"{snapshot['scenario_name'].lower().replace(' ', '_')}_metadata.json",
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
