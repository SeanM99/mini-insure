"""ALM page for economic assumptions, assets, and dependency validation."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from miniinsure.alm import alm_summary, combine_liability_cashflows
from miniinsure.reserving.deterministic_methods import deterministic_reserving_results
from miniinsure.reserving.reserve_risk import simulate_reserve_risk_quick
from miniinsure.reserving.technical_provisions import calculate_technical_provisions
from miniinsure.reserving.triangles import build_annual_triangles
from miniinsure.risk_engine.dependency import fixed_correlation_matrix, validate_dependency_matrix
from miniinsure.simulation.economic_scenarios import risk_free_curve_frame
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@st.cache_data(show_spinner=False)
def load_alm_data() -> dict[str, pd.DataFrame]:
    """Generate deterministic liabilities, reserve capital proxy, and ALM tables."""
    reality = generate_synthetic_reality(portfolio_mode="small")
    triangles = build_annual_triangles(
        reality.observed_valuation_snapshot,
        reality.payments,
        valuation_date=reality.valuation_date,
    )
    reserving_results = deterministic_reserving_results(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
    )
    provisions = calculate_technical_provisions(
        reserving_results,
        reality.policies,
        valuation_date=reality.valuation_date,
    )
    reserve_risk = simulate_reserve_risk_quick(
        triangles.paid,
        triangles.incurred,
        reality.policies,
        reality.observed_valuation_snapshot,
        reserving_results,
        n_simulations=250,
        seed=MASTER_SEED,
    )
    liability_cashflows = combine_liability_cashflows(
        claims_cashflows=provisions.claims_provision.cashflows,
        premium_cashflows=provisions.premium_provision.cashflows,
        reinsurance_cashflows=provisions.reinsurance_recoverables.cashflows,
    )
    opening_liabilities = float(provisions.summary["net_technical_provisions"])
    scr = float(reserve_risk.summary.iloc[0]["reserve_capital"])
    summary = alm_summary(
        opening_liabilities=opening_liabilities,
        scr=scr,
        liability_cashflows=liability_cashflows,
    )
    dependency_matrix = fixed_correlation_matrix()
    dependency_validation = validate_dependency_matrix(dependency_matrix, raise_on_blocking=False)
    return {
        "risk_free_curve": risk_free_curve_frame(),
        "asset_allocation": summary.asset_allocation,
        "liability_cashflow_profile": summary.liability_cashflow_profile,
        "liquidity_gap": summary.liquidity_gap,
        "duration_gap": summary.duration_gap,
        "market_stresses": summary.market_stresses,
        "dependency_matrix": dependency_matrix.reset_index(names="driver"),
        "dependency_validation": pd.DataFrame([dependency_validation.to_dict()]),
        "calibration": pd.DataFrame(
            [
                {
                    "opening_liabilities": opening_liabilities,
                    "scr": scr,
                    "opening_assets": opening_liabilities + 1.40 * scr,
                    "reserve_risk_simulations_for_scr_proxy": 250,
                }
            ]
        ),
    }


def render_alm_page() -> None:
    """Render ALM summaries."""
    st.set_page_config(page_title=f"{PROJECT_NAME} - ALM", layout="wide")
    st.title("ALM")
    st.info(
        "This page shows educational ALM summaries from deterministic liabilities, a quick-mode "
        "reserve capital proxy, and the fixed Gaussian copula dependency model."
    )

    data = load_alm_data()
    validation = data["dependency_validation"].iloc[0].to_dict()
    if validation["status"] == "pass":
        st.success(
            f"Dependency matrix validation: PASS. Minimum eigenvalue "
            f"{validation['minimum_eigenvalue']:.6f}."
        )
    else:
        st.error(
            f"Dependency matrix validation: FAIL. Minimum eigenvalue "
            f"{validation['minimum_eigenvalue']:.6f}."
        )

    col_assets, col_scr, col_opening = st.columns(3)
    calibration = data["calibration"].iloc[0].to_dict()
    col_assets.metric("Opening assets", f"EUR {calibration['opening_assets']:,.0f}")
    col_scr.metric("SCR proxy", f"EUR {calibration['scr']:,.0f}")
    col_opening.metric("Opening liabilities", f"EUR {calibration['opening_liabilities']:,.0f}")

    st.markdown("### Risk-Free Curve")
    st.dataframe(data["risk_free_curve"], hide_index=True, use_container_width=True)

    st.markdown("### Asset Allocation")
    st.plotly_chart(
        px.pie(
            data["asset_allocation"],
            names="asset_class",
            values="market_value",
            title="Opening Asset Allocation",
        ),
        use_container_width=True,
    )
    st.dataframe(data["asset_allocation"], hide_index=True, use_container_width=True)

    st.markdown("### Liability Cash-Flow Profile")
    st.dataframe(data["liability_cashflow_profile"], hide_index=True, use_container_width=True)

    st.markdown("### Liquidity Gap")
    st.dataframe(data["liquidity_gap"], hide_index=True, use_container_width=True)

    st.markdown("### Duration Gap")
    st.dataframe(data["duration_gap"], hide_index=True, use_container_width=True)

    st.markdown("### Simple Market Stresses")
    st.dataframe(data["market_stresses"], hide_index=True, use_container_width=True)

    st.markdown("### Dependency Matrix Validation")
    st.dataframe(data["dependency_validation"], hide_index=True, use_container_width=True)
    st.dataframe(data["dependency_matrix"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_alm_page()
