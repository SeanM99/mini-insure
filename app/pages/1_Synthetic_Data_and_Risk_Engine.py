"""Synthetic data validation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import (
    format_count,
    page_shell,
    render_empty_state,
    render_error_state,
    render_validation_badges,
)
from miniinsure.simulation.synthetic_reality import (
    generate_synthetic_reality,
    validation_summary_dict,
)


@st.cache_data(show_spinner=False)
def load_synthetic_reality(portfolio_mode: str, seed: int) -> dict[str, pd.DataFrame | dict[str, object]]:
    """Generate deterministic policies, claims, and observed snapshot."""
    reality = generate_synthetic_reality(portfolio_mode=portfolio_mode, seed=seed)
    return {
        "policies": reality.policies,
        "claims": reality.claims,
        "payments": reality.payments,
        "case_reserves": reality.case_reserves,
        "catastrophe_events": reality.catastrophe_events,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
        "validation": validation_summary_dict(reality),
    }


def render_validation_page() -> None:
    """Render the fixture validation page."""
    context = page_shell(
        page_title="Synthetic Data And Risk Engine",
        subtitle=(
        "This page generates deterministic scenario-mode policies, claims, payments, "
        "case reserves, catastrophe events, and an observed valuation snapshot. Hidden "
        "synthetic truth is isolated from app modelling inputs."
        ),
    )

    try:
        with st.spinner("Generating deterministic synthetic data..."):
            reality = load_synthetic_reality(context.portfolio_mode, context.seed)
    except Exception as exc:
        render_error_state("Synthetic data generation failed.", exc)
        st.stop()
    policies = reality["policies"]
    claims = reality["claims"]
    payments = reality["payments"]
    case_reserves = reality["case_reserves"]
    catastrophe_events = reality["catastrophe_events"]
    observed_snapshot = reality["observed_valuation_snapshot"]
    summary = reality["validation"]

    top_cols = st.columns(6)
    top_cols[0].metric("Policy count", format_count(len(policies), "policies"))
    top_cols[1].metric("Claim count", format_count(len(claims), "claims"))
    top_cols[2].metric("Payment count", format_count(len(payments), "payments"))
    top_cols[3].metric("Case reserve count", format_count(len(case_reserves), "reserves"))
    top_cols[4].metric("Catastrophe event count", format_count(len(catastrophe_events), "events"))
    top_cols[5].metric("Observed snapshot count", format_count(len(observed_snapshot), "rows"))

    render_validation_badges(
        status=str(summary["status"]),
        error_count=int(summary["error_count"]),
        warning_count=int(summary["warning_count"]),
    )

    st.markdown("### Counts By Underwriting Year")
    if policies.empty:
        render_empty_state("No policies were generated for this scenario.")
    else:
        counts_by_year = (
            policies.groupby("underwriting_year", as_index=False)
            .agg(policy_count=("policy_id", "count"))
            .sort_values("underwriting_year")
        )
        st.dataframe(counts_by_year, hide_index=True, width="stretch")

    st.markdown("### Observed Valuation Snapshot")
    if observed_snapshot.empty:
        render_empty_state("No observed valuation snapshot rows are available.")
    else:
        st.dataframe(
            observed_snapshot.head(20),
            hide_index=True,
            width="stretch",
        )

    st.markdown("### Sample Policies")
    if policies.empty:
        render_empty_state("No sample policies are available.")
    else:
        st.dataframe(
            policies.head(20)[
                [
                    "policy_id",
                    "underwriting_year",
                    "country_group",
                    "coverage_type",
                    "driver_age_band",
                    "vehicle_segment",
                    "technical_premium",
                    "charged_premium",
                ]
            ],
            hide_index=True,
            width="stretch",
        )

    error_rows = list(summary["errors"])
    warning_rows = list(summary["warnings"])

    st.markdown("### Errors")
    if error_rows:
        st.dataframe(pd.DataFrame(error_rows), hide_index=True, width="stretch")
    else:
        render_empty_state("No validation errors.")

    st.markdown("### Warnings")
    if warning_rows:
        st.dataframe(pd.DataFrame(warning_rows), hide_index=True, width="stretch")
    else:
        render_empty_state("No validation warnings.")


if __name__ == "__main__":
    render_validation_page()
