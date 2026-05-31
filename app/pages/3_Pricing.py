"""Pricing page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.pricing import segment_profitability
from miniinsure.simulation.policy_generator import generate_policy_data
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_small_policy_data() -> pd.DataFrame:
    """Generate deterministic small-mode policies."""
    return generate_policy_data(portfolio_mode="small")


def render_pricing_page() -> None:
    """Render transparent deterministic pricing outputs."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - Pricing", layout="wide")
    st.title("Pricing")
    st.info("GLM diagnostics will be added after deterministic pricing is stable.")

    policies = load_small_policy_data()
    average_technical = policies["technical_premium"].mean()
    average_charged = policies["charged_premium"].mean()
    rate_adequacy = policies["charged_premium"].sum() / policies["technical_premium"].sum()

    col_technical, col_charged, col_adequacy = st.columns(3)
    col_technical.metric("Average technical premium", f"EUR {average_technical:,.2f}")
    col_charged.metric("Average charged premium", f"EUR {average_charged:,.2f}")
    col_adequacy.metric("Rate adequacy", f"{rate_adequacy:.1%}")

    st.markdown("### Segment Profitability")
    profitability = segment_profitability(policies)
    st.table(
        profitability[
            [
                "homogeneous_risk_group",
                "policy_count",
                "earned_exposure",
                "loss_cost",
                "technical_premium",
                "charged_premium",
                "rate_adequacy",
                "expected_loss_ratio",
            ]
        ].head(25)
    )


if __name__ == "__main__":
    render_pricing_page()
