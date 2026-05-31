"""Financial Reporting page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    format_eur_m,
    format_eur_raw,
    format_pct,
    page_shell,
    render_empty_state,
    render_error_state,
    render_page_narrative,
    render_status_badge,
)
from miniinsure.reporting import ReportingWorkflowResult, calculate_reporting_workflow


@st.cache_data(show_spinner=False)
def load_reporting_data(
    scenario_name: str,
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
    capital_simulations: int,
) -> ReportingWorkflowResult:
    """Load the cached reporting workflow."""
    return calculate_reporting_workflow(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
        seed=seed,
    )


def _format_amount_table(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "amount" in result.columns:
        result["amount"] = result["amount"].map(format_eur_raw)
    return result


def render_financial_reporting() -> None:
    """Render financial reporting outputs."""
    context = page_shell(
        page_title="Financial Reporting",
        subtitle=(
            "Educational management reporting and a Solvency II-style balance sheet. "
            "This is not a statutory account or regulatory filing."
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
    render_page_narrative(
        showing="Management income statement, KPIs, Solvency II-style balance sheet lines, and reconciliation checks.",
        assumptions="The shared reporting workflow, technical provisions, reinsurance, capital model, expenses, commissions, and investment result.",
        test="Review combined ratio, return on capital, and reconciliation statuses for the selected scenario.",
        limitations="Outputs are educational management/reporting views, not audited accounts or statutory submissions.",
    )

    try:
        with st.spinner("Building financial reporting outputs..."):
            workflow = load_reporting_data(
                context.scenario_name,
                context.portfolio_mode,
                context.seed,
                int(context.reserve_risk_simulations or 250),
                int(context.capital_simulations or 500),
            )
    except Exception as exc:
        render_error_state("Financial reporting outputs could not be built.", exc)
        st.stop()
    financial = workflow.financial
    income = financial.income_statement.set_index("line_item")["amount"].to_dict()
    kpis = financial.kpis.set_index("metric")["value"].to_dict()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Gross earned premium", format_eur_m(income["gross_earned_premium"]))
    metric_cols[1].metric("Net claims incurred", format_eur_m(income["net_claims_incurred"]))
    metric_cols[2].metric("Expenses", format_eur_m(income["expenses"]))
    metric_cols[3].metric("Combined ratio", format_pct(kpis["combined_ratio"]))
    metric_cols[4].metric("Return on capital", format_pct(kpis["return_on_capital"]))

    st.markdown("### Management Income Statement")
    if financial.income_statement.empty:
        render_empty_state("No income statement rows are available.")
    else:
        st.dataframe(_format_amount_table(financial.income_statement), hide_index=True, width="stretch")

    st.markdown("### KPIs")
    kpi_display = financial.kpis.copy()
    kpi_display["value"] = kpi_display.apply(
        lambda row: format_pct(float(row["value"])),
        axis=1,
    )
    if kpi_display.empty:
        render_empty_state("No KPI rows are available.")
    else:
        st.dataframe(kpi_display, hide_index=True, width="stretch")

    st.markdown("### Solvency II-Style Balance Sheet")
    if financial.balance_sheet.empty:
        render_empty_state("No balance sheet rows are available.")
    else:
        st.dataframe(_format_amount_table(financial.balance_sheet), hide_index=True, width="stretch")

    st.markdown("### Reconciliation Checks")
    if financial.reconciliations.empty:
        render_empty_state("No reconciliation rows are available.")
    else:
        st.dataframe(financial.reconciliations, hide_index=True, width="stretch")

    if financial.reconciliations.empty:
        render_status_badge("Reporting reconciliations", "warning")
    elif (financial.reconciliations["status"] == "fail").any():
        render_status_badge("Reporting reconciliations", "fail")
    else:
        render_status_badge("Reporting reconciliations", "pass")


if __name__ == "__main__":
    render_financial_reporting()
