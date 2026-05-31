"""Synthetic data validation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import format_count, page_shell, render_validation_badges
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

    reality = load_synthetic_reality(context.portfolio_mode, context.seed)
    policies = reality["policies"]
    claims = reality["claims"]
    payments = reality["payments"]
    case_reserves = reality["case_reserves"]
    catastrophe_events = reality["catastrophe_events"]
    observed_snapshot = reality["observed_valuation_snapshot"]
    summary = reality["validation"]

    top_cols = st.columns(6)
    top_cols[0].metric("Policy count", format_count(len(policies)))
    top_cols[1].metric("Claim count", format_count(len(claims)))
    top_cols[2].metric("Payment count", format_count(len(payments)))
    top_cols[3].metric("Case reserve count", format_count(len(case_reserves)))
    top_cols[4].metric("Catastrophe event count", format_count(len(catastrophe_events)))
    top_cols[5].metric("Observed snapshot count", format_count(len(observed_snapshot)))

    render_validation_badges(
        status=str(summary["status"]),
        error_count=int(summary["error_count"]),
        warning_count=int(summary["warning_count"]),
    )

    st.markdown("### Counts By Underwriting Year")
    counts_by_year = (
        policies.groupby("underwriting_year", as_index=False)
        .agg(policy_count=("policy_id", "count"))
        .sort_values("underwriting_year")
    )
    st.table(counts_by_year)

    st.markdown("### Observed Valuation Snapshot")
    st.dataframe(
        observed_snapshot.head(20),
        hide_index=True,
        width="stretch",
    )

    st.markdown("### Sample Policies")
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
        st.table(pd.DataFrame(error_rows))
    else:
        st.success("No errors.")

    st.markdown("### Warnings")
    if warning_rows:
        st.table(pd.DataFrame(warning_rows))
    else:
        st.info("No warnings.")


if __name__ == "__main__":
    render_validation_page()
