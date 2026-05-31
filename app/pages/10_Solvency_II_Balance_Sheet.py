"""Solvency II-style balance sheet page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.risk_engine.capital_workflow import calculate_capital_workflow
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_balance_sheet_data() -> dict[str, pd.DataFrame]:
    """Load the shared capital workflow for balance sheet display."""
    result = calculate_capital_workflow(
        reserve_risk_simulations=250,
        capital_simulations=500,
        seed=MASTER_SEED,
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
    st.set_page_config(page_title=f"{PROJECT_NAME} - Solvency II Balance Sheet", layout="wide")
    st.title("Solvency II Balance Sheet")
    st.info(
        "This page shows an educational Solvency II-style balance sheet. It is not a regulatory filing."
    )

    data = load_balance_sheet_data()
    balance = data["balance_sheet"].iloc[0].to_dict()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Assets", f"EUR {balance['assets']:,.0f}")
    metric_cols[1].metric("Liabilities", f"EUR {balance['liabilities']:,.0f}")
    metric_cols[2].metric("Technical provisions", f"EUR {balance['technical_provisions']:,.0f}")
    metric_cols[3].metric("Own funds", f"EUR {balance['own_funds']:,.0f}")
    metric_cols[4].metric("SCR", f"EUR {balance['scr']:,.0f}")
    metric_cols[5].metric("MCR", f"EUR {balance['mcr']:,.0f}")

    ratio_cols = st.columns(3)
    ratio_cols[0].metric("Eligible own funds", f"EUR {balance['eligible_own_funds']:,.0f}")
    ratio_cols[1].metric("Solvency ratio", f"{balance['solvency_ratio']:.1%}")
    ratio_cols[2].metric("MCR ratio", f"{balance['mcr_ratio']:.1%}")

    if balance["reconciliation_status"] == "pass":
        st.success("Reconciliation status: PASS. Assets equal liabilities plus own funds within tolerance.")
    else:
        st.error("Reconciliation status: FAIL. Balance sheet does not reconcile.")

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
        use_container_width=True,
    )

    st.markdown("### Own Funds")
    st.dataframe(data["own_funds_tiers"], hide_index=True, use_container_width=True)

    st.markdown("### Capital Requirements")
    st.dataframe(data["standard_formula_modules"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_balance_sheet()
