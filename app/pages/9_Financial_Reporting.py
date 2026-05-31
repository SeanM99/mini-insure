"""Financial Reporting page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.assumptions import PORTFOLIO_MODES
from miniinsure.reporting import ReportingWorkflowResult, calculate_reporting_workflow
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_reporting_data(
    scenario_name: str,
    portfolio_mode: str,
    seed: int,
) -> ReportingWorkflowResult:
    """Load the cached reporting workflow."""
    return calculate_reporting_workflow(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=250,
        capital_simulations=500,
        seed=seed,
    )


def _format_amount_table(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "amount" in result.columns:
        result["amount"] = result["amount"].map(lambda value: f"EUR {float(value):,.0f}")
    return result


def render_financial_reporting() -> None:
    """Render financial reporting outputs."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - Financial Reporting", layout="wide")
    st.title("Financial Reporting")
    st.info(
        "This page shows educational management reporting and a Solvency II-style balance sheet. "
        "It is not a statutory account or regulatory filing."
    )

    controls = st.columns([2, 1, 1])
    scenario_name = controls[0].text_input("Scenario name", value="Base")
    portfolio_mode = controls[1].selectbox("Portfolio mode", options=list(PORTFOLIO_MODES), index=0)
    seed = int(controls[2].number_input("Seed", min_value=1, value=MASTER_SEED, step=1))

    workflow = load_reporting_data(scenario_name, portfolio_mode, seed)
    financial = workflow.financial
    income = financial.income_statement.set_index("line_item")["amount"].to_dict()
    kpis = financial.kpis.set_index("metric")["value"].to_dict()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Gross earned premium", f"EUR {income['gross_earned_premium']:,.0f}")
    metric_cols[1].metric("Net claims incurred", f"EUR {income['net_claims_incurred']:,.0f}")
    metric_cols[2].metric("Expenses", f"EUR {income['expenses']:,.0f}")
    metric_cols[3].metric("Combined ratio", f"{kpis['combined_ratio']:.1%}")
    metric_cols[4].metric("Return on capital", f"{kpis['return_on_capital']:.1%}")

    st.markdown("### Management Income Statement")
    st.dataframe(_format_amount_table(financial.income_statement), hide_index=True, use_container_width=True)

    st.markdown("### KPIs")
    kpi_display = financial.kpis.copy()
    kpi_display["value"] = kpi_display.apply(
        lambda row: f"{float(row['value']):.1%}",
        axis=1,
    )
    st.dataframe(kpi_display, hide_index=True, use_container_width=True)

    st.markdown("### Solvency II-Style Balance Sheet")
    st.dataframe(_format_amount_table(financial.balance_sheet), hide_index=True, use_container_width=True)

    st.markdown("### Reconciliation Checks")
    st.dataframe(financial.reconciliations, hide_index=True, use_container_width=True)

    if (financial.reconciliations["status"] == "fail").any():
        st.error("One or more reporting reconciliations failed.")
    else:
        st.success("Reporting reconciliations passed.")


if __name__ == "__main__":
    render_financial_reporting()
