"""Experience analysis page using observed modelling inputs only."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import render_empty_state, render_error_state, page_shell
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


@st.cache_data(show_spinner=False)
def load_observed_data(portfolio_mode: str, seed: int) -> dict[str, pd.DataFrame]:
    """Generate deterministic observed data without loading hidden truth."""
    reality = generate_synthetic_reality(portfolio_mode=portfolio_mode, seed=seed)
    return {
        "policies": reality.policies,
        "claims": reality.claims,
        "payments": reality.payments,
        "case_reserves": reality.case_reserves,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
    }


def render_experience_analysis() -> None:
    """Render observed experience analysis."""
    context = page_shell(
        page_title="Experience Analysis",
        subtitle="Observed experience analysis using valuation data only; hidden synthetic truth is not loaded.",
    )
    st.info("Experience views use observed valuation data only. Hidden synthetic truth is not loaded.")

    try:
        with st.spinner("Loading observed experience data..."):
            observed = load_observed_data(context.portfolio_mode, context.seed)
    except Exception as exc:
        render_error_state("Observed experience data could not be loaded.", exc)
        st.stop()
    policies = observed["policies"]
    claims = observed["claims"]
    payments = observed["payments"]
    snapshot = observed["observed_valuation_snapshot"]
    if policies.empty:
        render_empty_state("No policy data is available for experience analysis.")
        st.stop()

    st.markdown("### Frequency By Year")
    exposure = policies.groupby("accident_year", as_index=False).agg(earned_exposure=("earned_exposure", "sum"))
    claim_counts = claims.groupby("accident_year", as_index=False).agg(claim_count=("claim_id", "count"))
    frequency = exposure.merge(claim_counts, on="accident_year", how="left").fillna({"claim_count": 0})
    frequency["observed_frequency"] = frequency["claim_count"] / frequency["earned_exposure"]
    if frequency.empty:
        render_empty_state("No frequency rows are available.")
    else:
        st.plotly_chart(
            px.bar(frequency, x="accident_year", y="observed_frequency", title="Frequency By Year"),
            width="stretch",
        )
        st.dataframe(frequency, hide_index=True, width="stretch")

    st.markdown("### Severity By Claim Type")
    severity = (
        claims.groupby("claim_type", as_index=False)
        .agg(
            claim_count=("claim_id", "count"),
            average_observed_estimate=("latest_case_estimate", "mean"),
            paid_to_date=("paid_to_date", "sum"),
            case_reserve=("case_reserve", "sum"),
        )
        .sort_values("average_observed_estimate", ascending=False)
    )
    if severity.empty:
        render_empty_state("No severity rows are available.")
    else:
        st.plotly_chart(
            px.bar(severity, x="claim_type", y="average_observed_estimate", title="Severity By Claim Type"),
            width="stretch",
        )
        st.dataframe(severity, hide_index=True, width="stretch")

    st.markdown("### Loss Ratio By Year")
    premium = policies.groupby("accident_year", as_index=False).agg(earned_premium=("earned_premium", "sum"))
    observed_loss = (
        snapshot.groupby("accident_year", as_index=False)
        .agg(observed_loss=("paid_to_date", "sum"), case_reserve=("case_reserve", "sum"))
    )
    loss_ratio = premium.merge(observed_loss, on="accident_year", how="left").fillna(0.0)
    loss_ratio["incurred_observed_loss"] = loss_ratio["observed_loss"] + loss_ratio["case_reserve"]
    loss_ratio["loss_ratio"] = loss_ratio["incurred_observed_loss"] / loss_ratio["earned_premium"]
    if loss_ratio.empty:
        render_empty_state("No loss ratio rows are available.")
    else:
        st.plotly_chart(
            px.line(loss_ratio, x="accident_year", y="loss_ratio", markers=True, title="Loss Ratio By Year"),
            width="stretch",
        )
        st.dataframe(loss_ratio, hide_index=True, width="stretch")

    st.markdown("### Paid Emergence View")
    if payments.empty:
        render_empty_state("No observed payments are available.")
    else:
        paid = payments.merge(claims[["claim_id", "accident_year", "accident_date"]], on="claim_id", how="left")
        paid["development_month"] = (
            (pd.to_datetime(paid["payment_date"]) - pd.to_datetime(paid["accident_date"]))
            .dt.days.clip(lower=0)
            // 30
            + 1
        )
        emergence = (
            paid.groupby(["accident_year", "development_month"], as_index=False)
            .agg(incremental_paid=("paid_amount", "sum"))
            .sort_values(["accident_year", "development_month"])
        )
        emergence["cumulative_paid"] = emergence.groupby("accident_year")["incremental_paid"].cumsum()
        st.plotly_chart(
            px.line(
                emergence,
                x="development_month",
                y="cumulative_paid",
                color="accident_year",
                markers=True,
                title="Paid Emergence View",
            ),
            width="stretch",
        )
        if emergence.empty:
            render_empty_state("No paid emergence rows are available.")
        else:
            st.dataframe(emergence.head(40), hide_index=True, width="stretch")


if __name__ == "__main__":
    render_experience_analysis()
