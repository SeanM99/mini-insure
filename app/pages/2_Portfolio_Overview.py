"""Portfolio overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.charts import exposure_by_year, mix_bar, premium_by_year
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_small_observed_data() -> dict[str, pd.DataFrame]:
    """Generate deterministic small-mode observed data."""
    reality = generate_synthetic_reality(portfolio_mode="small")
    return {
        "policies": reality.policies,
        "claims": reality.claims,
        "payments": reality.payments,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
    }


def render_portfolio_overview() -> None:
    """Render portfolio overview charts."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - Portfolio Overview", layout="wide")
    st.title("Portfolio Overview")

    observed = load_small_observed_data()
    policies = observed["policies"]
    claims = observed["claims"]
    payments = observed["payments"]
    col_count, col_claims, col_exposure, col_written, col_earned = st.columns(5)
    col_count.metric("Policies", f"{len(policies):,}")
    col_claims.metric("Observed claims", f"{len(claims):,}")
    col_exposure.metric("Earned exposure", f"{policies['earned_exposure'].sum():,.0f}")
    col_written.metric("Written premium", f"EUR {policies['written_premium'].sum():,.0f}")
    col_earned.metric("Earned premium", f"EUR {policies['earned_premium'].sum():,.0f}")

    left, right = st.columns(2)
    left.markdown("### Business Mix")
    left.plotly_chart(mix_bar(policies, "customer_type", "Business Mix"), use_container_width=True)
    right.markdown("### Solvency II LoB Mix")
    right.plotly_chart(mix_bar(policies, "solvency_ii_lob", "Solvency II LoB Mix"), use_container_width=True)

    st.markdown("### Exposure By Underwriting Year")
    st.plotly_chart(exposure_by_year(policies), use_container_width=True)
    st.markdown("### Written And Earned Premium By Underwriting Year")
    st.plotly_chart(premium_by_year(policies), use_container_width=True)

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
