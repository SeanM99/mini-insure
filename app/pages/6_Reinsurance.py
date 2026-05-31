"""Reinsurance page for the fixed default treaty program."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import format_eur, page_shell
from miniinsure.simulation.reinsurance_simulation import (
    ReinsuranceProgram,
    apply_default_reinsurance_program,
    gross_to_net_reconciliation,
)
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


@st.cache_data(show_spinner=False)
def load_observed_data(portfolio_mode: str, seed: int) -> dict[str, pd.DataFrame]:
    """Generate deterministic observed data for reinsurance calculations."""
    reality = generate_synthetic_reality(portfolio_mode=portfolio_mode, seed=seed)
    return {
        "policies": reality.policies,
        "observed_valuation_snapshot": reality.observed_valuation_snapshot,
    }


def render_reinsurance_page() -> None:
    """Render fixed reinsurance program outputs."""
    context = page_shell(
        page_title="Reinsurance",
        subtitle=(
            "Fixed default reinsurance program applied directly to observed claim estimates. "
            "Treaty order is deductibles and policy limits, quota share, per-risk XOL, then aggregate stop loss."
        ),
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
    data = load_observed_data(context.portfolio_mode, context.seed)
    result = apply_default_reinsurance_program(
        data["observed_valuation_snapshot"],
        data["policies"],
        program=program,
    )
    reconciliation = gross_to_net_reconciliation(result)

    col_gross, col_ceded, col_recoveries, col_default, col_net = st.columns(5)
    col_gross.metric("Gross losses", format_eur(result.summary["gross_loss"]))
    col_ceded.metric("Ceded losses", format_eur(result.summary["quota_share_ceded_loss"]))
    col_recoveries.metric("Recoveries", format_eur(result.summary["total_recovery"]))
    col_default.metric(
        "Default-adjusted recoverables",
        format_eur(result.summary["default_adjusted_recoverable"]),
    )
    col_net.metric("Net losses", format_eur(result.summary["net_loss"]))

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
        width="stretch",
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
        width="stretch",
    )


if __name__ == "__main__":
    render_reinsurance_page()
