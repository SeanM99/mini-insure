"""Board Risk Report page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_count, page_shell, render_empty_state, render_error_state, render_validation_badges
from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.mappings import export_names
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow, generate_board_risk_report_markdown


@st.cache_data(show_spinner=False)
def load_board_report(
    scenario_name: str,
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
    capital_simulations: int,
) -> dict[str, object]:
    """Load board report markdown and validation status."""
    workflow = calculate_reporting_workflow(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
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
    context = page_shell(
        page_title="Board Risk Report",
        subtitle=(
            "Markdown board pack generated from educational model outputs and mock "
            "validation status."
        ),
        show_reserve_risk_simulations=True,
        reserve_risk_default=250,
        reserve_risk_min=50,
        reserve_risk_max=5_000,
        show_capital_simulations=True,
        capital_default=500,
        capital_min=100,
        capital_max=5_000,
    )

    try:
        with st.spinner("Generating board risk report..."):
            data = load_board_report(
                context.scenario_name,
                context.portfolio_mode,
                context.seed,
                int(context.reserve_risk_simulations or 250),
                int(context.capital_simulations or 500),
            )
    except Exception as exc:
        render_error_state("Board risk report generation failed.", exc)
        st.stop()
    validation: pd.DataFrame = data["validation"]  # type: ignore[assignment]
    summary = data["summary"]  # type: ignore[assignment]
    names = export_names(str(data["scenario_name"]))

    metric_cols = st.columns(3)
    metric_cols[0].metric("Validation status", str(summary["status"]).upper())
    metric_cols[1].metric("Blocking errors", format_count(int(summary["error_count"]), "errors"))
    metric_cols[2].metric("Warnings", format_count(int(summary["warning_count"]), "warnings"))
    render_validation_badges(
        status=str(summary["status"]),
        error_count=int(summary["error_count"]),
        warning_count=int(summary["warning_count"]),
        label="Board pack validation",
    )

    if not validation.empty:
        st.markdown("### Validation Messages")
        st.dataframe(validation, hide_index=True, width="stretch")
    else:
        render_empty_state("No board pack validation messages.")

    st.markdown("### Markdown Preview")
    if str(data["report"]).strip():
        st.markdown(str(data["report"]))
    else:
        render_empty_state("The board risk report preview is empty.")
    st.download_button(
        "Download board risk report Markdown",
        data=str(data["report"]),
        file_name=names.board_report_md,
        mime="text/markdown",
    )


if __name__ == "__main__":
    render_board_risk_report()
