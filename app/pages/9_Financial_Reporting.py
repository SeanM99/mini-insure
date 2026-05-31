"""Financial Reporting page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_eur, format_percent, page_shell, render_status_badge
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
        result["amount"] = result["amount"].map(lambda value: f"EUR {float(value):,.0f}")
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

    workflow = load_reporting_data(
        context.scenario_name,
        context.portfolio_mode,
        context.seed,
        int(context.reserve_risk_simulations or 250),
        int(context.capital_simulations or 500),
    )
    financial = workflow.financial
    income = financial.income_statement.set_index("line_item")["amount"].to_dict()
    kpis = financial.kpis.set_index("metric")["value"].to_dict()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Gross earned premium", format_eur(income["gross_earned_premium"]))
    metric_cols[1].metric("Net claims incurred", format_eur(income["net_claims_incurred"]))
    metric_cols[2].metric("Expenses", format_eur(income["expenses"]))
    metric_cols[3].metric("Combined ratio", format_percent(kpis["combined_ratio"]))
    metric_cols[4].metric("Return on capital", format_percent(kpis["return_on_capital"]))

    st.markdown("### Management Income Statement")
    st.dataframe(_format_amount_table(financial.income_statement), hide_index=True, width="stretch")

    st.markdown("### KPIs")
    kpi_display = financial.kpis.copy()
    kpi_display["value"] = kpi_display.apply(
        lambda row: format_percent(float(row["value"])),
        axis=1,
    )
    st.dataframe(kpi_display, hide_index=True, width="stretch")

    st.markdown("### Solvency II-Style Balance Sheet")
    st.dataframe(_format_amount_table(financial.balance_sheet), hide_index=True, width="stretch")

    st.markdown("### Reconciliation Checks")
    st.dataframe(financial.reconciliations, hide_index=True, width="stretch")

    if (financial.reconciliations["status"] == "fail").any():
        render_status_badge("Reporting reconciliations", "fail")
    else:
        render_status_badge("Reporting reconciliations", "pass")


if __name__ == "__main__":
    render_financial_reporting()
