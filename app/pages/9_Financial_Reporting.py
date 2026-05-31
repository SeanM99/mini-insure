"""Financial Reporting page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
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

    kpi_display = financial.kpis.copy()
    kpi_display["value"] = kpi_display.apply(
        lambda row: format_pct(float(row["value"])),
        axis=1,
    )
    lob_reporting = financial.lob_income_statement.copy()
    premium_mix = (
        lob_reporting.groupby("solvency_ii_lob", as_index=False)
        .agg(gross_earned_premium=("gross_earned_premium", "sum"))
        if not lob_reporting.empty
        else pd.DataFrame()
    )
    premium_by_year = (
        workflow.capital.policies.groupby("accident_year", as_index=False)
        .agg(earned_premium=("earned_premium", "sum"))
        if not workflow.capital.policies.empty
        else pd.DataFrame()
    )
    selected_loss_by_year = (
        workflow.capital.reserving_results.groupby("origin_year", as_index=False)
        .agg(selected_ultimate=("selected_ultimate", "sum"))
        .rename(columns={"origin_year": "accident_year"})
        if not workflow.capital.reserving_results.empty
        else pd.DataFrame()
    )
    loss_ratio_trend = premium_by_year.merge(selected_loss_by_year, on="accident_year", how="left").fillna(0.0)
    if not loss_ratio_trend.empty:
        loss_ratio_trend["loss_ratio"] = loss_ratio_trend["selected_ultimate"] / loss_ratio_trend["earned_premium"]

    tabs = st.tabs(["Overview", "Income Statement", "Balance Sheet", "KPI Reconciliations", "LoB Reporting", "Audit"])
    with tabs[0]:
        metric_cols = st.columns(5)
        metric_cols[0].metric("Gross earned premium", format_eur_m(income["gross_earned_premium"]))
        metric_cols[1].metric("Net claims incurred", format_eur_m(income["net_claims_incurred"]))
        metric_cols[2].metric("Expenses", format_eur_m(income["expenses"]))
        metric_cols[3].metric("Combined ratio", format_pct(kpis["combined_ratio"]))
        metric_cols[4].metric("Return on capital", format_pct(kpis["return_on_capital"]))
        chart_cols = st.columns(2)
        with chart_cols[0]:
            if premium_mix.empty:
                render_empty_state("No premium mix data is available.")
            else:
                st.plotly_chart(
                    px.pie(
                        premium_mix,
                        names="solvency_ii_lob",
                        values="gross_earned_premium",
                        title="Premium Mix By LoB",
                    ),
                    width="stretch",
                )
        with chart_cols[1]:
            if loss_ratio_trend.empty:
                render_empty_state("No loss ratio trend data is available.")
            else:
                st.plotly_chart(
                    px.line(
                        loss_ratio_trend,
                        x="accident_year",
                        y="loss_ratio",
                        markers=True,
                        title="Selected Ultimate Loss Ratio Trend",
                    ),
                    width="stretch",
                )
        if financial.reconciliations.empty:
            render_status_badge("Reporting reconciliations", "warning")
        elif (financial.reconciliations["status"] == "fail").any():
            render_status_badge("Reporting reconciliations", "fail")
        else:
            render_status_badge("Reporting reconciliations", "pass")

    with tabs[1]:
        st.markdown("### Management Income Statement")
        if financial.income_statement.empty:
            render_empty_state("No income statement rows are available.")
        else:
            st.dataframe(_format_amount_table(financial.income_statement), hide_index=True, width="stretch")

    with tabs[2]:
        st.markdown("### Solvency II-Style Balance Sheet")
        if financial.balance_sheet.empty:
            render_empty_state("No balance sheet rows are available.")
        else:
            st.dataframe(_format_amount_table(financial.balance_sheet), hide_index=True, width="stretch")

    with tabs[3]:
        st.markdown("### KPIs")
        if kpi_display.empty:
            render_empty_state("No KPI rows are available.")
        else:
            st.dataframe(kpi_display, hide_index=True, width="stretch")
        st.markdown("### Reconciliation Checks")
        if financial.reconciliations.empty:
            render_empty_state("No reconciliation rows are available.")
        else:
            st.dataframe(financial.reconciliations, hide_index=True, width="stretch")

    with tabs[4]:
        st.markdown("### LoB Reporting")
        if lob_reporting.empty:
            render_empty_state("No LoB reporting rows are available.")
        else:
            st.dataframe(lob_reporting, hide_index=True, width="stretch")

    with tabs[5]:
        st.markdown("### Audit")
        with st.expander("Scenario metadata", expanded=True):
            st.dataframe(pd.DataFrame([financial.metadata]), hide_index=True, width="stretch")
        with st.expander("Raw loss ratio trend"):
            st.dataframe(loss_ratio_trend, hide_index=True, width="stretch")


if __name__ == "__main__":
    render_financial_reporting()
