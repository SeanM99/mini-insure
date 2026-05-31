"""Mock QRT Reporting Pack page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.assumptions import PORTFOLIO_MODES
from miniinsure.qrt.export import generate_qrt_pack, qrt_pack_to_excel_bytes, qrt_pack_to_zip_bytes
from miniinsure.qrt.mappings import export_names
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import generate_board_risk_report_markdown, calculate_reporting_workflow
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_qrt_data(scenario_name: str, portfolio_mode: str, seed: int) -> dict[str, object]:
    """Load reporting workflow, QRT pack, and validation for display."""
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
    board_report = generate_board_risk_report_markdown(
        capital=workflow.capital,
        financial=workflow.financial,
        validation_status=str(summary["status"]),
        validation_errors=int(summary["error_count"]),
        validation_warnings=int(summary["warning_count"]),
    )
    metadata_json = workflow.scenario_state.metadata_json(workflow.assumptions)
    return {
        "pack": pack,
        "validation": validation,
        "summary": summary,
        "board_report": board_report,
        "metadata_json": metadata_json,
        "scenario_name": workflow.scenario_state.scenario_name,
    }


def render_qrt_reporting_pack() -> None:
    """Render mock QRT pack outputs."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - QRT Reporting Pack", layout="wide")
    st.title("QRT Reporting Pack")
    st.warning(
        "These are mock QRT-shaped educational outputs only. The app does not create, validate, or export real XBRL."
    )

    controls = st.columns([2, 1, 1])
    scenario_name = controls[0].text_input("Scenario name", value="Base")
    portfolio_mode = controls[1].selectbox("Portfolio mode", options=list(PORTFOLIO_MODES), index=0)
    seed = int(controls[2].number_input("Seed", min_value=1, value=MASTER_SEED, step=1))

    data = load_qrt_data(scenario_name, portfolio_mode, seed)
    pack: dict[str, pd.DataFrame] = data["pack"]  # type: ignore[assignment]
    validation: pd.DataFrame = data["validation"]  # type: ignore[assignment]
    summary = data["summary"]  # type: ignore[assignment]
    names = export_names(str(data["scenario_name"]))

    metric_cols = st.columns(3)
    metric_cols[0].metric("Validation status", str(summary["status"]).upper())
    metric_cols[1].metric("Blocking errors", int(summary["error_count"]))
    metric_cols[2].metric("Warnings", int(summary["warning_count"]))

    st.markdown("### Applicability Matrix")
    st.dataframe(pack["S.01.01.02"], hide_index=True, use_container_width=True)

    st.markdown("### Template Viewer")
    template = st.selectbox("Template", options=list(pack.keys()), index=0)
    st.dataframe(pack[template], hide_index=True, use_container_width=True)

    st.markdown("### Validation Report")
    if validation.empty:
        st.success("No QRT validation messages.")
    else:
        st.dataframe(validation, hide_index=True, use_container_width=True)
        if bool(summary["export_blocked"]):
            st.error("Export is blocked because validation errors are present.")
        else:
            st.warning("Only warnings are present. Export remains available.")

    xlsx_bytes = qrt_pack_to_excel_bytes(pack)
    st.download_button(
        "Download mock QRT Excel",
        data=xlsx_bytes,
        file_name=names.qrt_xlsx,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=bool(summary["export_blocked"]),
    )
    zip_bytes = qrt_pack_to_zip_bytes(
        pack=pack,
        board_report_markdown=str(data["board_report"]),
        scenario_metadata_json=str(data["metadata_json"]),
        scenario_name=str(data["scenario_name"]),
    )
    st.download_button(
        "Download mock QRT ZIP",
        data=zip_bytes,
        file_name=names.qrt_zip,
        mime="application/zip",
        disabled=bool(summary["export_blocked"]),
    )


if __name__ == "__main__":
    render_qrt_reporting_pack()
