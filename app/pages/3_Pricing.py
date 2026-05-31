"""Pricing page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_eur, format_percent, page_shell
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

    policies = load_policy_data(context.portfolio_mode, context.seed)
    average_technical = policies["technical_premium"].mean()
    average_charged = policies["charged_premium"].mean()
    rate_adequacy = policies["charged_premium"].sum() / policies["technical_premium"].sum()

    col_technical, col_charged, col_adequacy = st.columns(3)
    col_technical.metric("Average technical premium", format_eur(average_technical, decimals=2))
    col_charged.metric("Average charged premium", format_eur(average_charged, decimals=2))
    col_adequacy.metric("Rate adequacy", format_percent(rate_adequacy))

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
