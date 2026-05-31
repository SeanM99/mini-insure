"""Board Risk Report page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.assumptions import PORTFOLIO_MODES
from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.mappings import export_names
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow, generate_board_risk_report_markdown
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_board_report(scenario_name: str, portfolio_mode: str, seed: int) -> dict[str, object]:
    """Load board report markdown and validation status."""
    workflow = calculate_reporting_workflow(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=250,
        capital_simulations=500,
        seed=seed,
    )
    pack = generate_qrt_pack(
        capital=workflow.capital,
        financial=workflow.financial,
        assumptions=workflow.assumptions,
        scenario_name=workflow.scenario_state.scenario_name,
    )
    validation = validate_qrt_pack(pack, capital=workflow.capital, financial=workflow.financial)
    summary = validation_summary(validation)
    report = generate_board_risk_report_markdown(
        capital=workflow.capital,
        financial=workflow.financial,
        validation_status=str(summary["status"]),
        validation_errors=int(summary["error_count"]),
        validation_warnings=int(summary["warning_count"]),
    )
    return {
        "report": report,
        "validation": validation,
        "summary": summary,
        "scenario_name": workflow.scenario_state.scenario_name,
    }


def render_board_risk_report() -> None:
    """Render the board risk report preview."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - Board Risk Report", layout="wide")
    st.title("Board Risk Report")
    st.info("This Markdown report is generated from the educational model outputs and mock validation status.")

    controls = st.columns([2, 1, 1])
    scenario_name = controls[0].text_input("Scenario name", value="Base")
    portfolio_mode = controls[1].selectbox("Portfolio mode", options=list(PORTFOLIO_MODES), index=0)
    seed = int(controls[2].number_input("Seed", min_value=1, value=MASTER_SEED, step=1))

    data = load_board_report(scenario_name, portfolio_mode, seed)
    validation: pd.DataFrame = data["validation"]  # type: ignore[assignment]
    summary = data["summary"]  # type: ignore[assignment]
    names = export_names(str(data["scenario_name"]))

    metric_cols = st.columns(3)
    metric_cols[0].metric("Validation status", str(summary["status"]).upper())
    metric_cols[1].metric("Blocking errors", int(summary["error_count"]))
    metric_cols[2].metric("Warnings", int(summary["warning_count"]))

    if not validation.empty:
        st.markdown("### Validation Messages")
        st.dataframe(validation, hide_index=True, use_container_width=True)

    st.markdown("### Markdown Preview")
    st.markdown(str(data["report"]))
    st.download_button(
        "Download board risk report Markdown",
        data=str(data["report"]),
        file_name=names.board_report_md,
        mime="text/markdown",
    )


if __name__ == "__main__":
    render_board_risk_report()
