"""Streamlit Home dashboard for MiniInsure Europe NL."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    format_eur_m,
    format_pct,
    page_shell,
    render_empty_state,
    render_error_state,
    render_page_narrative,
    render_status_badge,
)
from miniinsure.qrt.export import generate_qrt_pack
from miniinsure.qrt.validation import validate_qrt_pack, validation_summary
from miniinsure.reporting import calculate_reporting_workflow
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_home_dashboard(
    scenario_name: str,
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
    capital_simulations: int,
) -> dict[str, object]:
    """Run the shared reporting workflow for the Home dashboard."""
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
    qrt_summary = validation_summary(validation)
    kpis = workflow.financial.kpis.set_index("metric")["value"].to_dict()
    return {
        "solvency_ratio": float(workflow.capital.own_funds["solvency_ratio"]),
        "scr": float(workflow.capital.standard_formula.summary["scr"]),
        "mcr": float(workflow.capital.mcr.mcr),
        "eligible_own_funds": float(workflow.capital.own_funds["eligible_own_funds"]),
        "net_technical_provisions": float(
            workflow.capital.technical_provisions.summary["net_technical_provisions"]
        ),
        "combined_ratio": float(kpis["combined_ratio"]),
        "qrt_status": str(qrt_summary["status"]),
        "qrt_error_count": int(qrt_summary["error_count"]),
        "qrt_warning_count": int(qrt_summary["warning_count"]),
        "generated_at": str(workflow.financial.metadata["generation_timestamp"]),
        "validation": validation,
    }


def render_home() -> None:
    """Render the Home executive dashboard."""
    context = page_shell(
        page_title=PROJECT_NAME,
        subtitle="Executive dashboard for the synthetic NL motor insurer scenario.",
        default_portfolio_mode="small",
        show_reserve_risk_simulations=True,
        reserve_risk_default=100,
        reserve_risk_min=50,
        reserve_risk_max=5_000,
        show_capital_simulations=True,
        capital_default=250,
        capital_min=100,
        capital_max=5_000,
    )
    render_page_narrative(
        showing=(
            "A compact executive dashboard for solvency, technical provisions, "
            "combined ratio, QRT validation status, and scenario metadata."
        ),
        assumptions=(
            "The current scenario controls, typed assumptions, master seed, selected "
            "portfolio mode, quick reserve-risk simulations, and capital simulations."
        ),
        test=(
            "Change the scenario name, portfolio mode, seed, and simulation counts, then "
            "check whether capital and reporting indicators move coherently."
        ),
        limitations=(
            "Dashboard outputs are educational, generated from synthetic observed data, "
            "and do not represent real Solvency II filings or real XBRL."
        ),
    )

    if not st.session_state.get("miniinsure_full_workflow_reviewed", False):
        render_empty_state(
            "Full workflow not yet reviewed in this browser session.",
            (
                "Start with Synthetic Data and Risk Engine if you want to inspect inputs "
                "before relying on the dashboard. The dashboard below can still be "
                "generated from the current scenario controls."
            ),
        )

    with st.spinner("Generating executive dashboard from the current scenario..."):
        try:
            dashboard = load_home_dashboard(
                context.scenario_name,
                context.portfolio_mode,
                context.seed,
                int(context.reserve_risk_simulations or 100),
                int(context.capital_simulations or 250),
            )
        except Exception as exc:
            render_error_state("Executive dashboard could not be generated.", exc)
            _render_workflow_guide()
            return

    st.session_state["miniinsure_full_workflow_reviewed"] = True

    st.markdown("### Scenario Snapshot")
    scenario_cols = st.columns(4)
    scenario_cols[0].metric("Scenario name", context.scenario_name)
    scenario_cols[1].metric("Valuation date", context.valuation_date)
    scenario_cols[2].metric("Portfolio mode", context.portfolio_mode)
    scenario_cols[3].metric("Last generated", str(dashboard["generated_at"]))

    st.markdown("**Assumption hash**")
    st.code(context.assumption_hash, language="text")

    st.markdown("### Executive KPIs")
    capital_cols = st.columns(4)
    capital_cols[0].metric("Solvency ratio", format_pct(dashboard["solvency_ratio"]))
    capital_cols[1].metric("SCR", format_eur_m(dashboard["scr"]))
    capital_cols[2].metric("MCR", format_eur_m(dashboard["mcr"]))
    capital_cols[3].metric("Eligible own funds", format_eur_m(dashboard["eligible_own_funds"]))

    reporting_cols = st.columns(4)
    reporting_cols[0].metric(
        "Net technical provisions",
        format_eur_m(dashboard["net_technical_provisions"]),
    )
    reporting_cols[1].metric("Combined ratio", format_pct(dashboard["combined_ratio"]))
    reporting_cols[2].metric("QRT validation status", str(dashboard["qrt_status"]).upper())
    reporting_cols[3].metric(
        "QRT messages",
        f"{dashboard['qrt_error_count']} errors / {dashboard['qrt_warning_count']} warnings",
    )
    render_status_badge(
        "Mock QRT validation",
        str(dashboard["qrt_status"]),
        detail="QRT outputs are mock-shaped only and no real XBRL is produced.",
    )

    st.markdown("### Downloads")
    st.download_button(
        "Download scenario metadata JSON",
        data=context.scenario_state.metadata_json(context.assumptions),
        file_name=f"{context.scenario_name.lower().replace(' ', '_')}_metadata.json",
        mime="application/json",
    )
    validation: pd.DataFrame = dashboard["validation"]  # type: ignore[assignment]
    if validation.empty:
        render_empty_state("No validation report CSV is available because the mock QRT validation has no messages.")
    else:
        st.download_button(
            "Download validation report CSV",
            data=validation.to_csv(index=False),
            file_name=f"{context.scenario_name.lower().replace(' ', '_')}_validation_report.csv",
            mime="text/csv",
        )

    _render_workflow_guide()


def _render_workflow_guide() -> None:
    st.markdown("### Workflow Guide")
    steps = [
        "Generate synthetic data",
        "Validate data",
        "Review pricing",
        "Review reserving and technical provisions",
        "Review capital and ALM",
        "Review financial reporting",
        "Generate mock QRT pack",
        "Generate board report",
    ]
    for index, step in enumerate(steps, start=1):
        st.markdown(f"{index}. {step}")


if __name__ == "__main__":
    render_home()
