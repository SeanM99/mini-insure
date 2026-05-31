"""Capital model page for one-year economic capital and simplified Standard Formula."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from miniinsure.risk_engine.capital_workflow import calculate_capital_workflow
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_capital_model_data(seed: int, reserve_risk_simulations: int, capital_simulations: int) -> dict[str, pd.DataFrame]:
    """Load the deterministic capital workflow for display."""
    result = calculate_capital_workflow(
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
    st.set_page_config(page_title=f"{PROJECT_NAME} - Capital Model", layout="wide")
    st.title("Capital Model")
    st.info(
        "This page shows one-year economic capital and a simplified educational Standard Formula. "
        "It is not a regulatory SCR calculation."
    )

    controls = st.columns(3)
    seed = int(controls[0].number_input("Capital model seed", min_value=1, value=MASTER_SEED, step=1))
    reserve_sims = int(controls[1].number_input("Reserve risk simulations", min_value=50, max_value=1_000, value=250, step=50))
    capital_sims = int(controls[2].number_input("One-year simulations", min_value=100, max_value=2_000, value=500, step=100))
    data = load_capital_model_data(seed, reserve_sims, capital_sims)
    summary = data["capital_summary"].iloc[0].to_dict()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Economic capital", f"EUR {summary['economic_capital']:,.0f}")
    metric_cols[1].metric("VaR 99.5%", f"EUR {summary['var_995']:,.0f}")
    metric_cols[2].metric("TVaR 99.5%", f"EUR {summary['tvar_995']:,.0f}")
    metric_cols[3].metric("Standard Formula SCR", f"EUR {summary['standard_formula_scr']:,.0f}")
    metric_cols[4].metric("MCR", f"EUR {summary['mcr']:,.0f}")
    metric_cols[5].metric("Solvency ratio", f"{summary['solvency_ratio']:.1%}")

    st.markdown("### One-Year Loss Distribution")
    st.plotly_chart(
        px.histogram(
            data["one_year_simulations"],
            x="one_year_loss",
            nbins=50,
            title="One-Year Own Funds Loss",
        ),
        use_container_width=True,
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
        f"EUR {summary['reserve_risk_contribution']:,.0f}",
    )
    contribution_cols[1].metric(
        "Premium risk contribution",
        f"EUR {summary['premium_risk_contribution']:,.0f}",
    )
    contribution_cols[2].metric(
        "Market risk contribution",
        f"EUR {summary['market_risk_contribution']:,.0f}",
    )
    contribution_cols[3].metric(
        "Operational risk",
        f"EUR {summary['operational_risk']:,.0f}",
    )
    st.plotly_chart(
        px.bar(contributions, x="component", y="amount", title="One-Year Capital Contributions"),
        use_container_width=True,
    )
    st.dataframe(contributions, hide_index=True, use_container_width=True)

    st.markdown("### Simplified Standard Formula SCR")
    st.dataframe(data["standard_formula_modules"], hide_index=True, use_container_width=True)

    st.markdown("### Non-Life Premium And Reserve Risk By LoB")
    st.dataframe(data["standard_formula_by_lob"], hide_index=True, use_container_width=True)

    st.markdown("### MCR")
    st.dataframe(data["mcr"], hide_index=True, use_container_width=True)

    st.markdown("### Stress Summaries")
    st.dataframe(data["stress_summaries"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_capital_model()
