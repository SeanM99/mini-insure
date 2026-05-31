"""Solvency II-style balance sheet page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_eur_m, format_pct, page_shell, render_empty_state, render_error_state, render_status_badge
from miniinsure.risk_engine.capital_workflow import calculate_capital_workflow


@st.cache_data(show_spinner=False)
def load_balance_sheet_data(
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
    capital_simulations: int,
) -> dict[str, pd.DataFrame]:
    """Load the shared capital workflow for balance sheet display."""
    result = calculate_capital_workflow(
        portfolio_mode=portfolio_mode,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
        seed=seed,
    )
    balance = dict(result.balance_sheet.summary)
    balance.update(result.own_funds)
    balance["mcr"] = result.mcr.mcr
    balance["mcr_linear"] = result.mcr.mcr_linear
    balance["mcr_combined"] = result.mcr.mcr_combined
    balance["scr"] = result.standard_formula.summary["scr"]
    balance["solvency_ratio"] = result.own_funds["solvency_ratio"]
    balance["mcr_ratio"] = result.own_funds["mcr_ratio"]
    return {
        "balance_sheet": pd.DataFrame([balance]),
        "own_funds_tiers": result.balance_sheet.own_funds_tiers,
        "standard_formula_modules": result.standard_formula.module_charges,
    }


def render_balance_sheet() -> None:
    """Render Solvency II-style balance sheet."""
    context = page_shell(
        page_title="Solvency II Balance Sheet",
        subtitle="Educational Solvency II-style balance sheet for the selected scenario.",
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
        with st.spinner("Building the Solvency II-style balance sheet..."):
            data = load_balance_sheet_data(
                context.portfolio_mode,
                context.seed,
                int(context.reserve_risk_simulations or 250),
                int(context.capital_simulations or 500),
            )
    except Exception as exc:
        render_error_state("Balance sheet outputs could not be built.", exc)
        st.stop()
    if data["balance_sheet"].empty:
        render_empty_state("No balance sheet rows are available.")
        st.stop()
    balance = data["balance_sheet"].iloc[0].to_dict()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Assets", format_eur_m(balance["assets"]))
    metric_cols[1].metric("Liabilities", format_eur_m(balance["liabilities"]))
    metric_cols[2].metric("Technical provisions", format_eur_m(balance["technical_provisions"]))
    metric_cols[3].metric("Own funds", format_eur_m(balance["own_funds"]))
    metric_cols[4].metric("SCR", format_eur_m(balance["scr"]))
    metric_cols[5].metric("MCR", format_eur_m(balance["mcr"]))

    ratio_cols = st.columns(3)
    ratio_cols[0].metric("Eligible own funds", format_eur_m(balance["eligible_own_funds"]))
    ratio_cols[1].metric("Solvency ratio", format_pct(balance["solvency_ratio"]))
    ratio_cols[2].metric("MCR ratio", format_pct(balance["mcr_ratio"]))

    render_status_badge(
        "Balance sheet reconciliation",
        str(balance["reconciliation_status"]),
        detail="Assets equal liabilities plus own funds within tolerance.",
    )

    st.markdown("### Balance Sheet")
    st.dataframe(
        data["balance_sheet"][
            [
                "assets",
                "liabilities",
                "technical_provisions",
                "other_liabilities",
                "own_funds",
                "eligible_own_funds",
                "scr",
                "mcr",
                "solvency_ratio",
                "mcr_ratio",
                "reconciliation_difference",
                "reconciliation_status",
            ]
        ],
        hide_index=True,
        width="stretch",
    )

    st.markdown("### Own Funds")
    if data["own_funds_tiers"].empty:
        render_empty_state("No own funds tier rows are available.")
    else:
        st.dataframe(data["own_funds_tiers"], hide_index=True, width="stretch")

    st.markdown("### Capital Requirements")
    if data["standard_formula_modules"].empty:
        render_empty_state("No capital requirement rows are available.")
    else:
        st.dataframe(data["standard_formula_modules"], hide_index=True, width="stretch")


if __name__ == "__main__":
    render_balance_sheet()
