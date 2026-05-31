"""Technical provisions page for deterministic reserving outputs."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import format_eur, format_percent, page_shell, render_validation_badges
from miniinsure.reserving.deterministic_methods import (
    TAIL_FACTORS,
    deterministic_reserving_results,
    paid_chain_ladder,
)
from miniinsure.reserving.triangles import (
    build_annual_triangles,
    triangle_to_matrix,
    validate_cumulative_paid_non_decreasing,
)
from miniinsure.reserving.reserve_risk import QUICK_MODE_SIMULATIONS, simulate_reserve_risk_quick
from miniinsure.reserving.technical_provisions import calculate_technical_provisions
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality


@st.cache_data(show_spinner=False)
def load_reserving_data(
    portfolio_mode: str,
    seed: int,
    reserve_risk_simulations: int,
) -> dict[str, pd.DataFrame]:
    """Generate observed data and deterministic reserving outputs."""
    reality = generate_synthetic_reality(portfolio_mode=portfolio_mode, seed=seed)
    triangles = build_annual_triangles(
        reality.observed_valuation_snapshot,
        reality.payments,
        valuation_date=reality.valuation_date,
    )
    results = deterministic_reserving_results(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
    )
    paid_cl = paid_chain_ladder(
        triangles.paid,
        tail_factor=sum(TAIL_FACTORS.values()) / len(TAIL_FACTORS),
    )
    validation_messages = validate_cumulative_paid_non_decreasing(triangles.paid)
    provisions = calculate_technical_provisions(
        results,
        reality.policies,
        valuation_date=reality.valuation_date,
    )
    reserve_risk = simulate_reserve_risk_quick(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
        results,
        n_simulations=reserve_risk_simulations,
        seed=seed,
    )
    return {
        "paid_triangle": triangles.paid,
        "incurred_triangle": triangles.incurred,
        "count_triangle": triangles.counts,
        "average_cost_triangle": triangles.average_cost,
        "reserving_results": results,
        "development_factors": paid_cl.factors,
        "validation_messages": pd.DataFrame([message.to_dict() for message in validation_messages]),
        "technical_provisions_summary": pd.DataFrame([provisions.summary]),
        "claims_cashflows": provisions.claims_provision.cashflows,
        "premium_cashflows": provisions.premium_provision.cashflows,
        "reinsurance_cashflows": provisions.reinsurance_recoverables.cashflows,
        "risk_margin_runoff": provisions.risk_margin.runoff,
        "reserve_risk_summary": reserve_risk.summary,
        "reserve_risk_simulations": reserve_risk.simulations,
        "reserve_risk_component_summary": reserve_risk.component_summary,
        "reserve_risk_settings": pd.DataFrame([reserve_risk.settings]),
    }


def render_technical_provisions() -> None:
    """Render deterministic reserving results."""
    context = page_shell(
        page_title="Technical Provisions",
        subtitle=(
            "Deterministic technical provisions and quick-mode one-year reserve risk from "
            "observed valuation data only."
        ),
        show_reserve_risk_simulations=True,
        reserve_risk_default=QUICK_MODE_SIMULATIONS,
        reserve_risk_min=100,
        reserve_risk_max=5_000,
    )

    if st.button("Rerun reserve risk"):
        st.cache_data.clear()

    data = load_reserving_data(
        context.portfolio_mode,
        context.seed,
        int(context.reserve_risk_simulations or QUICK_MODE_SIMULATIONS),
    )
    paid_triangle = data["paid_triangle"]
    incurred_triangle = data["incurred_triangle"]
    reserving_results = data["reserving_results"]
    provisions_summary = data["technical_provisions_summary"].iloc[0].to_dict()
    reserve_risk_summary = data["reserve_risk_summary"].iloc[0].to_dict()
    reserve_risk_settings = data["reserve_risk_settings"].iloc[0].to_dict()

    validation_messages = data["validation_messages"]
    if validation_messages.empty:
        render_validation_badges(status="pass", label="Paid triangle validation")
    else:
        render_validation_badges(
            status="blocked",
            error_count=len(validation_messages),
            label="Paid triangle validation",
        )
        st.dataframe(validation_messages, hide_index=True, width="stretch")

    st.markdown("### Solvency II-Style Technical Provisions")
    metric_cols = st.columns(6)
    metric_cols[0].metric("Claims provision", format_eur(provisions_summary["claims_provision"]))
    metric_cols[1].metric("Premium provision", format_eur(provisions_summary["premium_provision"]))
    metric_cols[2].metric("Reinsurance recoverables", format_eur(provisions_summary["reinsurance_recoverables"]))
    metric_cols[3].metric("Risk margin", format_eur(provisions_summary["risk_margin"]))
    metric_cols[4].metric(
        "Gross technical provisions",
        format_eur(provisions_summary["gross_technical_provisions"]),
    )
    metric_cols[5].metric(
        "Net technical provisions",
        format_eur(provisions_summary["net_technical_provisions"]),
    )

    if provisions_summary["reconciliation_status"] == "pass":
        st.success(
            "Reconciliation status: PASS. Gross technical provisions less discounted "
            "recoverables reconciles to net technical provisions within tolerance."
        )
    else:
        st.error("Reconciliation status: FAIL. Review the gross-to-net provision bridge.")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "claims_provision": provisions_summary["claims_provision"],
                    "premium_provision": provisions_summary["premium_provision"],
                    "gross_best_estimate": provisions_summary["gross_best_estimate"],
                    "reinsurance_recoverables": provisions_summary["reinsurance_recoverables"],
                    "net_best_estimate": provisions_summary["net_best_estimate"],
                    "risk_margin": provisions_summary["risk_margin"],
                    "gross_technical_provisions": provisions_summary["gross_technical_provisions"],
                    "net_technical_provisions": provisions_summary["net_technical_provisions"],
                    "reconciliation_difference": provisions_summary["reconciliation_difference"],
                    "valuation_tolerance": provisions_summary["valuation_tolerance"],
                    "reconciliation_status": provisions_summary["reconciliation_status"],
                }
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    st.markdown("### One-Year Reserve Risk Quick Mode")
    risk_cols = st.columns(5)
    risk_cols[0].metric("Reserve capital", format_eur(reserve_risk_summary["reserve_capital"]))
    risk_cols[1].metric("Mean reserve loss", format_eur(reserve_risk_summary["mean"]))
    risk_cols[2].metric("VaR 99.5%", format_eur(reserve_risk_summary["var_995"]))
    risk_cols[3].metric("TVaR 99.5%", format_eur(reserve_risk_summary["tvar_995"]))
    risk_cols[4].metric(
        "Adverse probability",
        format_percent(reserve_risk_summary["probability_of_adverse_development"]),
    )
    st.caption(
        f"Quick mode uses {int(reserve_risk_settings['simulation_count']):,} simulations "
        f"with seed {int(reserve_risk_settings['seed'])}. Re-running with the same seed "
        "and simulation count reproduces the same distribution."
    )
    st.dataframe(data["reserve_risk_summary"], hide_index=True, width="stretch")
    st.plotly_chart(
        px.histogram(
            data["reserve_risk_simulations"],
            x="reserve_loss",
            nbins=50,
            title="One-Year Reserve Loss Distribution",
        ),
        width="stretch",
    )
    st.markdown("### Reserve Risk Components")
    st.dataframe(data["reserve_risk_component_summary"], hide_index=True, width="stretch")

    st.markdown("### Paid Triangle")
    st.dataframe(
        triangle_to_matrix(paid_triangle, "cumulative_paid"),
        width="stretch",
    )

    st.markdown("### Incurred Triangle")
    st.dataframe(
        triangle_to_matrix(incurred_triangle, "cumulative_incurred"),
        width="stretch",
    )

    st.markdown("### Development Factors")
    st.dataframe(data["development_factors"], hide_index=True, width="stretch")

    st.markdown("### Selected Deterministic Reserve")
    display_columns = [
        "solvency_ii_lob",
        "homogeneous_risk_group",
        "origin_year",
        "claim_type_basis",
        "selected_method",
        "latest_paid",
        "latest_incurred",
        "selected_ultimate",
        "ibnr",
        "selected_reserve",
    ]
    st.dataframe(
        reserving_results[display_columns].sort_values(
            ["solvency_ii_lob", "homogeneous_risk_group", "origin_year"]
        ),
        hide_index=True,
        width="stretch",
    )

    st.markdown("### Selected Reserve By LoB And HRG")
    summary = (
        reserving_results.groupby(["solvency_ii_lob", "homogeneous_risk_group"], as_index=False)
        .agg(
            ultimate=("selected_ultimate", "sum"),
            ibnr=("ibnr", "sum"),
            selected_reserve=("selected_reserve", "sum"),
        )
        .sort_values(["solvency_ii_lob", "homogeneous_risk_group"])
    )
    st.dataframe(summary, hide_index=True, width="stretch")

    st.markdown("### Claims Provision Cash Flows")
    st.dataframe(data["claims_cashflows"].head(60), hide_index=True, width="stretch")

    st.markdown("### Reinsurance Recoverables Cash Flows")
    st.dataframe(data["reinsurance_cashflows"], hide_index=True, width="stretch")

    st.markdown("### Risk Margin Runoff")
    st.dataframe(data["risk_margin_runoff"], hide_index=True, width="stretch")


if __name__ == "__main__":
    render_technical_provisions()
