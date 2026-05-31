"""Pricing page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_eur_raw, format_pct, page_shell, render_empty_state, render_error_state
from miniinsure.pricing import segment_profitability
from miniinsure.simulation.policy_generator import generate_policy_data


@st.cache_data(show_spinner=False)
def load_policy_data(portfolio_mode: str, seed: int) -> pd.DataFrame:
    """Generate deterministic policies."""
    return generate_policy_data(portfolio_mode=portfolio_mode, seed=seed)


def render_pricing_page() -> None:
    """Render transparent deterministic pricing outputs."""
    context = page_shell(
        page_title="Pricing",
        subtitle="Transparent deterministic pricing outputs for the selected scenario.",
    )
    st.info("GLM diagnostics will be added after deterministic pricing is stable.")

    try:
        with st.spinner("Generating priced policy records..."):
            policies = load_policy_data(context.portfolio_mode, context.seed)
    except Exception as exc:
        render_error_state("Pricing data could not be generated.", exc)
        st.stop()
    if policies.empty:
        render_empty_state("No priced policies are available for this scenario.")
        st.stop()

    average_technical = policies["technical_premium"].mean()
    average_charged = policies["charged_premium"].mean()
    rate_adequacy = policies["charged_premium"].sum() / policies["technical_premium"].sum()

    col_technical, col_charged, col_adequacy = st.columns(3)
    col_technical.metric("Average technical premium", format_eur_raw(average_technical, decimals=0))
    col_charged.metric("Average charged premium", format_eur_raw(average_charged, decimals=0))
    col_adequacy.metric("Rate adequacy", format_pct(rate_adequacy))

    st.markdown("### Segment Profitability")
    profitability = segment_profitability(policies)
    display_columns = [
        "homogeneous_risk_group",
        "policy_count",
        "earned_exposure",
        "loss_cost",
        "technical_premium",
        "charged_premium",
        "rate_adequacy",
        "expected_loss_ratio",
    ]
    if profitability.empty:
        render_empty_state("No segment profitability rows are available.")
    else:
        st.dataframe(profitability[display_columns].head(25), hide_index=True, width="stretch")


if __name__ == "__main__":
    render_pricing_page()
