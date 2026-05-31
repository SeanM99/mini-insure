"""Synthetic data validation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from miniinsure.simulation.synthetic_reality import (
    generate_synthetic_reality,
    validation_summary_dict,
)
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_small_synthetic_reality() -> dict[str, pd.DataFrame | dict[str, object]]:
    """Generate deterministic small-mode policies, claims, and observed snapshot."""
    reality = generate_synthetic_reality(portfolio_mode="small")
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
    st.set_page_config(page_title=f"{PROJECT_NAME} - Synthetic Data", layout="wide")

    st.title("Synthetic Data And Risk Engine")
    st.info(
        "This phase generates deterministic small-mode policies, claims, payments, "
        "case reserves, catastrophe events, and an observed valuation snapshot. Hidden "
        "synthetic truth is isolated from app modelling inputs."
    )

    reality = load_small_synthetic_reality()
    policies = reality["policies"]
    claims = reality["claims"]
    payments = reality["payments"]
    case_reserves = reality["case_reserves"]
    catastrophe_events = reality["catastrophe_events"]
    observed_snapshot = reality["observed_valuation_snapshot"]
    summary = reality["validation"]
    status = str(summary["status"]).upper()

    top_cols = st.columns(6)
    top_cols[0].metric("Policy count", f"{len(policies):,}")
    top_cols[1].metric("Claim count", f"{len(claims):,}")
    top_cols[2].metric("Payment count", f"{len(payments):,}")
    top_cols[3].metric("Case reserve count", f"{len(case_reserves):,}")
    top_cols[4].metric("Catastrophe event count", f"{len(catastrophe_events):,}")
    top_cols[5].metric("Observed snapshot count", f"{len(observed_snapshot):,}")

    status_cols = st.columns(3)
    status_cols[0].metric("Validation status", status)
    status_cols[1].metric("Errors", int(summary["error_count"]))
    status_cols[2].metric("Warnings", int(summary["warning_count"]))

    if int(summary["error_count"]) > 0:
        st.error("Validation errors are export-blocking.")
    else:
        st.success("No validation errors found. Future export actions would not be blocked.")

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
        use_container_width=True,
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
        use_container_width=True,
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
