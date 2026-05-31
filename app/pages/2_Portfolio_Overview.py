"""Portfolio overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    format_count,
    format_eur_m,
    page_shell,
    render_empty_state,
    render_error_state,
    render_page_narrative,
)
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
    render_page_narrative(
        showing="Portfolio size, observed claim counts, exposure, premium, business mix, LoB mix, and observed paid experience.",
        assumptions="Policy generation mix, market cycle factors, pricing outputs, and observed claims generated from the selected scenario.",
        test="Switch portfolio mode and seed, then confirm mix proportions and earned premium remain directionally coherent.",
        limitations="This is a synthetic management view and does not use hidden ultimate truth.",
    )

    try:
        with st.spinner("Loading observed portfolio data..."):
            observed = load_observed_data(context.portfolio_mode, context.seed)
    except Exception as exc:
        render_error_state("Observed portfolio data could not be loaded.", exc)
        st.stop()
    policies = observed["policies"]
    claims = observed["claims"]
    payments = observed["payments"]
    if policies.empty:
        render_empty_state("No policies are available for this scenario.")
        st.stop()

    col_count, col_claims, col_exposure, col_written, col_earned = st.columns(5)
    col_count.metric("Policies", format_count(len(policies), "policies"))
    col_claims.metric("Observed claims", format_count(len(claims), "claims"))
    col_exposure.metric("Earned exposure", format_count(policies["earned_exposure"].sum(), "exposure-years"))
    col_written.metric("Written premium", format_eur_m(policies["written_premium"].sum()))
    col_earned.metric("Earned premium", format_eur_m(policies["earned_premium"].sum()))

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
    if lob_mix.empty:
        render_empty_state("No LoB mix is available for this scenario.")
    else:
        st.dataframe(lob_mix, hide_index=True, width="stretch")

    st.markdown("### Observed Paid By Year")
    if payments.empty:
        render_empty_state("No observed payments are available yet.")
    else:
        paid_by_claim = claims[["claim_id", "accident_year"]].merge(payments, on="claim_id", how="inner")
        paid_by_year = (
            paid_by_claim.groupby("accident_year", as_index=False)
            .agg(paid_amount=("paid_amount", "sum"))
            .sort_values("accident_year")
        )
        if paid_by_year.empty:
            render_empty_state("No paid amounts are available by accident year.")
        else:
            st.dataframe(paid_by_year, hide_index=True, width="stretch")


if __name__ == "__main__":
    render_portfolio_overview()
