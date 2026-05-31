"""Portfolio overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_count, format_eur, page_shell
from miniinsure.charts import exposure_by_year, mix_bar, premium_by_year
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


@st.cache_data(show_spinner=False)
def load_observed_data(portfolio_mode: str, seed: int) -> dict[str, pd.DataFrame]:
    """Generate deterministic observed data."""
    reality = generate_synthetic_reality(portfolio_mode=portfolio_mode, seed=seed)
    return {
        "policies": reality.policies,
        "claims": reality.claims,
        "payments": reality.payments,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
    }


def render_portfolio_overview() -> None:
    """Render portfolio overview charts."""
    context = page_shell(
        page_title="Portfolio Overview",
        subtitle="Portfolio mix, exposure, premium, and observed paid experience for the selected scenario.",
    )

    observed = load_observed_data(context.portfolio_mode, context.seed)
    policies = observed["policies"]
    claims = observed["claims"]
    payments = observed["payments"]
    col_count, col_claims, col_exposure, col_written, col_earned = st.columns(5)
    col_count.metric("Policies", format_count(len(policies)))
    col_claims.metric("Observed claims", format_count(len(claims)))
    col_exposure.metric("Earned exposure", format_count(policies["earned_exposure"].sum()))
    col_written.metric("Written premium", format_eur(policies["written_premium"].sum()))
    col_earned.metric("Earned premium", format_eur(policies["earned_premium"].sum()))

    left, right = st.columns(2)
    left.markdown("### Business Mix")
    left.plotly_chart(mix_bar(policies, "customer_type", "Business Mix"), width="stretch")
    right.markdown("### Solvency II LoB Mix")
    right.plotly_chart(mix_bar(policies, "solvency_ii_lob", "Solvency II LoB Mix"), width="stretch")

    st.markdown("### Exposure By Underwriting Year")
    st.plotly_chart(exposure_by_year(policies), width="stretch")
    st.markdown("### Written And Earned Premium By Underwriting Year")
    st.plotly_chart(premium_by_year(policies), width="stretch")

    st.markdown("### LoB Mix")
    lob_mix = (
        policies.groupby("solvency_ii_lob", as_index=False)
        .agg(
            policy_count=("policy_id", "count"),
            earned_exposure=("earned_exposure", "sum"),
            written_premium=("written_premium", "sum"),
            earned_premium=("earned_premium", "sum"),
        )
        .sort_values("earned_premium", ascending=False)
    )
    st.table(lob_mix)

    st.markdown("### Observed Paid By Year")
    if payments.empty:
        st.info("No observed payments.")
    else:
        paid_by_claim = claims[["claim_id", "accident_year"]].merge(payments, on="claim_id", how="inner")
        paid_by_year = (
            paid_by_claim.groupby("accident_year", as_index=False)
            .agg(paid_amount=("paid_amount", "sum"))
            .sort_values("accident_year")
        )
        st.table(paid_by_year)


if __name__ == "__main__":
    render_portfolio_overview()
