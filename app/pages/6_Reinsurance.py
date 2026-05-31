"""Reinsurance page for the fixed default treaty program."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from miniinsure.simulation.reinsurance_simulation import (
    ReinsuranceProgram,
    apply_default_reinsurance_program,
    gross_to_net_reconciliation,
)
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality
from miniinsure.utils import PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_small_observed_data() -> dict[str, pd.DataFrame]:
    """Generate deterministic observed data for reinsurance calculations."""
    reality = generate_synthetic_reality(portfolio_mode="small")
    return {
        "policies": reality.policies,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
    }


def render_reinsurance_page() -> None:
    """Render fixed reinsurance program outputs."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - Reinsurance", layout="wide")
    st.title("Reinsurance")
    st.info(
        "This page applies the fixed default reinsurance program directly to observed "
        "claim estimates. Treaty order is deductibles and policy limits, quota share, "
        "per-risk XOL, then aggregate stop loss."
    )

    quota_share_enabled = st.toggle("Enable quota share", value=False)
    ceded_pct = st.slider(
        "Quota share ceded percentage",
        min_value=0,
        max_value=40,
        value=0,
        step=5,
        disabled=not quota_share_enabled,
    )

    program = ReinsuranceProgram(
        quota_share_enabled=quota_share_enabled,
        quota_share_ceded_pct=ceded_pct / 100.0 if quota_share_enabled else 0.0,
    )
    data = load_small_observed_data()
    result = apply_default_reinsurance_program(
        data["observed_valuation_snapshot"],
        data["policies"],
        program=program,
    )
    reconciliation = gross_to_net_reconciliation(result)

    col_gross, col_ceded, col_recoveries, col_default, col_net = st.columns(5)
    col_gross.metric("Gross losses", f"EUR {result.summary['gross_loss']:,.0f}")
    col_ceded.metric("Ceded losses", f"EUR {result.summary['quota_share_ceded_loss']:,.0f}")
    col_recoveries.metric("Recoveries", f"EUR {result.summary['total_recovery']:,.0f}")
    col_default.metric(
        "Default-adjusted recoverables",
        f"EUR {result.summary['default_adjusted_recoverable']:,.0f}",
    )
    col_net.metric("Net losses", f"EUR {result.summary['net_loss']:,.0f}")

    st.markdown("### Gross-To-Net Reconciliation")
    st.table(reconciliation)

    chart_data = reconciliation.melt(
        id_vars="accident_year",
        value_vars=["gross_loss", "net_loss", "default_adjusted_recoverable"],
        var_name="measure",
        value_name="amount",
    )
    st.plotly_chart(
        px.bar(
            chart_data,
            x="accident_year",
            y="amount",
            color="measure",
            barmode="group",
            title="Gross And Net Reinsurance Results",
        ),
        use_container_width=True,
    )

    st.markdown("### Claim-Level Per-Risk XOL Audit")
    st.dataframe(
        result.claim_level[
            [
                "claim_id",
                "accident_year",
                "gross_loss",
                "quota_share_ceded_loss",
                "loss_after_quota_share",
                "per_risk_xol_recovery",
                "net_loss_before_aggregate",
                "per_risk_default_adjusted_recoverable",
            ]
        ].sort_values("gross_loss", ascending=False).head(25),
        hide_index=True,
        use_container_width=True,
    )


if __name__ == "__main__":
    render_reinsurance_page()
