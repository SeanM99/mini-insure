"""Technical provisions page for deterministic reserving outputs."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

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
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_reserving_data(reserve_risk_seed: int, reserve_risk_simulations: int) -> dict[str, pd.DataFrame]:
    """Generate observed data and deterministic reserving outputs."""
    reality = generate_synthetic_reality(portfolio_mode="small")
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
        seed=reserve_risk_seed,
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
    st.set_page_config(page_title=f"{PROJECT_NAME} - Technical Provisions", layout="wide")
    st.title("Technical Provisions")
    st.info(
        "This page shows deterministic technical provisions and quick-mode one-year reserve risk "
        "from observed valuation data only. Full reserve-risk mode settings will be exposed later."
    )

    control_cols = st.columns(3)
    reserve_risk_seed = int(
        control_cols[0].number_input(
            "Reserve risk seed",
            min_value=1,
            max_value=2_147_483_647,
            value=MASTER_SEED,
            step=1,
        )
    )
    reserve_risk_simulations = int(
        control_cols[1].number_input(
            "Quick-mode reserve simulations",
            min_value=100,
            max_value=5_000,
            value=QUICK_MODE_SIMULATIONS,
            step=100,
        )
    )
    if control_cols[2].button("Rerun reserve risk"):
        st.cache_data.clear()

    data = load_reserving_data(reserve_risk_seed, reserve_risk_simulations)
    paid_triangle = data["paid_triangle"]
    incurred_triangle = data["incurred_triangle"]
    reserving_results = data["reserving_results"]
    provisions_summary = data["technical_provisions_summary"].iloc[0].to_dict()
    reserve_risk_summary = data["reserve_risk_summary"].iloc[0].to_dict()
    reserve_risk_settings = data["reserve_risk_settings"].iloc[0].to_dict()

    validation_messages = data["validation_messages"]
    if validation_messages.empty:
        st.success("Paid triangle validation passed: cumulative paid is non-decreasing.")
    else:
        st.error("Paid triangle validation found blocking issues.")
        st.dataframe(validation_messages, hide_index=True, use_container_width=True)

    st.markdown("### Solvency II-Style Technical Provisions")
    metric_cols = st.columns(6)
    metric_cols[0].metric("Claims provision", f"EUR {provisions_summary['claims_provision']:,.0f}")
    metric_cols[1].metric("Premium provision", f"EUR {provisions_summary['premium_provision']:,.0f}")
    metric_cols[2].metric("Reinsurance recoverables", f"EUR {provisions_summary['reinsurance_recoverables']:,.0f}")
    metric_cols[3].metric("Risk margin", f"EUR {provisions_summary['risk_margin']:,.0f}")
    metric_cols[4].metric(
        "Gross technical provisions",
        f"EUR {provisions_summary['gross_technical_provisions']:,.0f}",
    )
    metric_cols[5].metric(
        "Net technical provisions",
        f"EUR {provisions_summary['net_technical_provisions']:,.0f}",
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
        use_container_width=True,
    )

    st.markdown("### One-Year Reserve Risk Quick Mode")
    risk_cols = st.columns(5)
    risk_cols[0].metric("Reserve capital", f"EUR {reserve_risk_summary['reserve_capital']:,.0f}")
    risk_cols[1].metric("Mean reserve loss", f"EUR {reserve_risk_summary['mean']:,.0f}")
    risk_cols[2].metric("VaR 99.5%", f"EUR {reserve_risk_summary['var_995']:,.0f}")
    risk_cols[3].metric("TVaR 99.5%", f"EUR {reserve_risk_summary['tvar_995']:,.0f}")
    risk_cols[4].metric(
        "Adverse probability",
        f"{reserve_risk_summary['probability_of_adverse_development']:.1%}",
    )
    st.caption(
        f"Quick mode uses {int(reserve_risk_settings['simulation_count']):,} simulations "
        f"with seed {int(reserve_risk_settings['seed'])}. Re-running with the same seed "
        "and simulation count reproduces the same distribution."
    )
    st.dataframe(data["reserve_risk_summary"], hide_index=True, use_container_width=True)
    st.plotly_chart(
        px.histogram(
            data["reserve_risk_simulations"],
            x="reserve_loss",
            nbins=50,
            title="One-Year Reserve Loss Distribution",
        ),
        use_container_width=True,
    )
    st.markdown("### Reserve Risk Components")
    st.dataframe(data["reserve_risk_component_summary"], hide_index=True, use_container_width=True)

    st.markdown("### Paid Triangle")
    st.dataframe(
        triangle_to_matrix(paid_triangle, "cumulative_paid"),
        use_container_width=True,
    )

    st.markdown("### Incurred Triangle")
    st.dataframe(
        triangle_to_matrix(incurred_triangle, "cumulative_incurred"),
        use_container_width=True,
    )

    st.markdown("### Development Factors")
    st.dataframe(data["development_factors"], hide_index=True, use_container_width=True)

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
        use_container_width=True,
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
    st.dataframe(summary, hide_index=True, use_container_width=True)

    st.markdown("### Claims Provision Cash Flows")
    st.dataframe(data["claims_cashflows"].head(60), hide_index=True, use_container_width=True)

    st.markdown("### Reinsurance Recoverables Cash Flows")
    st.dataframe(data["reinsurance_cashflows"], hide_index=True, use_container_width=True)

    st.markdown("### Risk Margin Runoff")
    st.dataframe(data["risk_margin_runoff"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_technical_provisions()
