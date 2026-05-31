"""Capital model page for one-year economic capital and simplified Standard Formula."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import (
    format_eur_m,
    format_pct,
    page_shell,
    render_empty_state,
    render_error_state,
    render_page_narrative,
)
from miniinsure.risk_engine.capital_workflow import calculate_capital_workflow


@st.cache_data(show_spinner=False)
def load_capital_model_data(
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
    capital_simulations: int,
) -> dict[str, pd.DataFrame]:
    """Load the deterministic capital workflow for display."""
    result = calculate_capital_workflow(
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
        seed=seed,
    )
    capital_summary = result.one_year_capital.summary.copy()
    capital_summary["reserve_risk_contribution"] = result.one_year_capital.simulations["reserve_loss"].quantile(0.995)
    capital_summary["premium_risk_contribution"] = result.one_year_capital.simulations["premium_risk_loss"].quantile(0.995)
    capital_summary["market_risk_contribution"] = result.one_year_capital.simulations["market_risk_loss"].quantile(0.995)
    capital_summary["operational_risk"] = result.one_year_capital.simulations["operational_loss"].iloc[0]
    capital_summary["standard_formula_scr"] = result.standard_formula.summary["scr"]
    capital_summary["mcr"] = result.mcr.mcr
    capital_summary["solvency_ratio"] = result.own_funds["solvency_ratio"]
    return {
        "capital_summary": capital_summary,
        "one_year_simulations": result.one_year_capital.simulations,
        "standard_formula_modules": result.standard_formula.module_charges,
        "standard_formula_by_lob": result.standard_formula.non_life_by_lob,
        "market_stresses": result.standard_formula.market,
        "mcr": pd.DataFrame([result.mcr.__dict__]),
        "own_funds": pd.DataFrame([result.own_funds]),
        "stress_summaries": result.stress_summaries,
    }


def render_capital_model() -> None:
    """Render one-year capital and simplified Standard Formula results."""
    context = page_shell(
        page_title="Capital Model",
        subtitle=(
            "One-year economic capital and a simplified educational Standard Formula. "
            "This is not a regulatory SCR calculation."
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
        showing="One-year economic capital, one-year loss distribution, capital contributions, simplified Standard Formula SCR, MCR, and stresses.",
        assumptions="Opening balance sheet, reserve-risk quick mode, premium risk approximation, market stresses, own funds, MCR formula, and simulation counts.",
        test="Rerun with different seeds and simulation counts and compare economic capital against simplified Standard Formula SCR.",
        limitations="This is a simplified educational capital model, not a regulatory SCR engine.",
    )

    try:
        with st.spinner("Running capital model simulations..."):
            data = load_capital_model_data(
                context.portfolio_mode,
                context.seed,
                int(context.reserve_risk_simulations or 250),
                int(context.capital_simulations or 500),
            )
    except Exception as exc:
        render_error_state("Capital model results could not be calculated.", exc)
        st.stop()
    summary = data["capital_summary"].iloc[0].to_dict()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Economic capital", format_eur_m(summary["economic_capital"]))
    metric_cols[1].metric("VaR 99.5%", format_eur_m(summary["var_995"]))
    metric_cols[2].metric("TVaR 99.5%", format_eur_m(summary["tvar_995"]))
    metric_cols[3].metric("Standard Formula SCR", format_eur_m(summary["standard_formula_scr"]))
    metric_cols[4].metric("MCR", format_eur_m(summary["mcr"]))
    metric_cols[5].metric("Solvency ratio", format_pct(summary["solvency_ratio"]))

    st.markdown("### One-Year Loss Distribution")
    if data["one_year_simulations"].empty:
        render_empty_state("No one-year loss simulations are available.")
    else:
        st.plotly_chart(
            px.histogram(
                data["one_year_simulations"],
                x="one_year_loss",
                nbins=50,
                title="One-Year Own Funds Loss",
            ),
            width="stretch",
        )

    st.markdown("### Capital Contributions")
    contributions = pd.DataFrame(
        [
            {"component": "reserve risk", "amount": summary["reserve_risk_contribution"]},
            {"component": "premium risk", "amount": summary["premium_risk_contribution"]},
            {"component": "market risk", "amount": summary["market_risk_contribution"]},
            {"component": "operational risk", "amount": summary["operational_risk"]},
        ]
    )
    contribution_cols = st.columns(4)
    contribution_cols[0].metric(
        "Reserve risk contribution",
        format_eur_m(summary["reserve_risk_contribution"]),
    )
    contribution_cols[1].metric(
        "Premium risk contribution",
        format_eur_m(summary["premium_risk_contribution"]),
    )
    contribution_cols[2].metric(
        "Market risk contribution",
        format_eur_m(summary["market_risk_contribution"]),
    )
    contribution_cols[3].metric(
        "Operational risk",
        format_eur_m(summary["operational_risk"]),
    )
    if contributions.empty:
        render_empty_state("No capital contribution rows are available.")
    else:
        st.plotly_chart(
            px.bar(contributions, x="component", y="amount", title="One-Year Capital Contributions"),
            width="stretch",
        )
        st.dataframe(contributions, hide_index=True, width="stretch")

    st.markdown("### Simplified Standard Formula SCR")
    st.dataframe(data["standard_formula_modules"], hide_index=True, width="stretch")

    st.markdown("### Non-Life Premium And Reserve Risk By LoB")
    st.dataframe(data["standard_formula_by_lob"], hide_index=True, width="stretch")

    st.markdown("### MCR")
    st.dataframe(data["mcr"], hide_index=True, width="stretch")

    st.markdown("### Stress Summaries")
    st.dataframe(data["stress_summaries"], hide_index=True, width="stretch")


if __name__ == "__main__":
    render_capital_model()
