"""Shared Streamlit page shell and scenario controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import streamlit as st

from .badges import render_badge_row
from miniinsure.assumptions import (
    PORTFOLIO_MODES,
    Assumptions,
    ScenarioState,
    load_effective_assumptions,
    stable_assumption_hash,
)
from miniinsure.utils import MASTER_SEED, PROJECT_NAME


@dataclass(frozen=True)
class PageContext:
    """Scenario context returned by the shared page shell."""

    scenario_state: ScenarioState
    assumptions: Assumptions
    assumption_hash: str
    valuation_date: str
    reporting_quarter: str
    reserve_risk_simulations: int | None
    capital_simulations: int | None
    generated_at: str

    @property
    def scenario_name(self) -> str:
        return self.scenario_state.scenario_name

    @property
    def portfolio_mode(self) -> str:
        return self.scenario_state.portfolio_mode

    @property
    def seed(self) -> int:
        return self.scenario_state.seed


def page_shell(
    *,
    page_title: str,
    subtitle: str,
    show_reserve_risk_simulations: bool = False,
    reserve_risk_default: int = 250,
    reserve_risk_min: int = 25,
    reserve_risk_max: int = 5_000,
    show_capital_simulations: bool = False,
    capital_default: int = 500,
    capital_min: int = 25,
    capital_max: int = 5_000,
    default_portfolio_mode: str = "small",
) -> PageContext:
    """Render the standard page frame and return shared scenario controls."""
    browser_title = PROJECT_NAME if page_title == PROJECT_NAME else f"{PROJECT_NAME} - {page_title}"
    st.set_page_config(page_title=browser_title, layout="wide")
    _inject_css()
    _render_sidebar_intro()

    with st.sidebar:
        st.markdown("### Scenario")
        scenario_name = st.text_input("Scenario name", value="Base", key="global_scenario_name")
        portfolio_index = list(PORTFOLIO_MODES).index(default_portfolio_mode)
        portfolio_mode = st.selectbox(
            "Portfolio mode",
            options=list(PORTFOLIO_MODES),
            index=portfolio_index,
            key="global_portfolio_mode",
        )
        seed = int(
            st.number_input(
                "Seed",
                min_value=1,
                max_value=2_147_483_647,
                value=MASTER_SEED,
                step=1,
                key="global_seed",
            )
        )
        reserve_risk_simulations = None
        if show_reserve_risk_simulations:
            reserve_risk_simulations = int(
                st.number_input(
                    "Reserve-risk simulations",
                    min_value=reserve_risk_min,
                    max_value=reserve_risk_max,
                    value=reserve_risk_default,
                    step=25 if reserve_risk_default < 100 else 50,
                    key="global_reserve_risk_simulations",
                )
            )
        capital_simulations = None
        if show_capital_simulations:
            capital_simulations = int(
                st.number_input(
                    "Capital simulations",
                    min_value=capital_min,
                    max_value=capital_max,
                    value=capital_default,
                    step=25 if capital_default < 100 else 100,
                    key="global_capital_simulations",
                )
            )

    scenario_state = ScenarioState(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        seed=seed,
    )
    assumptions = load_effective_assumptions(
        ui_overrides=scenario_state.ui_assumption_overrides()
    )
    assumption_hash = stable_assumption_hash(assumptions)
    context = PageContext(
        scenario_state=scenario_state,
        assumptions=assumptions,
        assumption_hash=assumption_hash,
        valuation_date=assumptions.valuation_date.isoformat(),
        reporting_quarter=assumptions.primary_reporting_quarter,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    with st.sidebar:
        render_last_run_metadata(context)

    st.title(page_title)
    st.caption(subtitle)
    badges = ["MOCK ONLY", "OBSERVED DATA ONLY"]
    if show_reserve_risk_simulations:
        badges.append("QUICK MODE")
    render_badge_row(badges)
    render_mock_only_notice()
    return context


def render_last_run_metadata(context: PageContext) -> None:
    """Render the shared last-run metadata block."""
    st.markdown("### Last Run Metadata")
    st.text(f"Scenario: {context.scenario_name}")
    st.text(f"Portfolio mode: {context.portfolio_mode}")
    st.text(f"Seed: {context.seed}")
    st.text(f"Valuation date: {context.valuation_date}")
    st.text(f"Reporting quarter: {context.reporting_quarter}")
    if context.reserve_risk_simulations is not None:
        st.text(f"Reserve-risk sims: {context.reserve_risk_simulations:,}")
    if context.capital_simulations is not None:
        st.text(f"Capital sims: {context.capital_simulations:,}")
    st.text("Assumption hash:")
    st.code(context.assumption_hash, language="text")


def render_mock_only_notice() -> None:
    """Render the standard educational and mock-reporting notice."""
    st.warning(
        "Educational outputs only. QRT outputs are mock-shaped only, no real XBRL is "
        "produced, and hidden synthetic truth is not used in model or reporting pages."
    )


def render_page_narrative(
    *,
    showing: str,
    assumptions: str,
    test: str,
    limitations: str,
) -> None:
    """Render a consistent four-part page narrative card row."""
    st.markdown("### Page Guide")
    columns = st.columns(4)
    items = [
        ("What is this page showing?", showing),
        ("What assumptions drive it?", assumptions),
        ("What should the user test here?", test),
        ("What are the limitations?", limitations),
    ]
    for column, (title, body) in zip(columns, items, strict=True):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)


def render_empty_state(title: str, detail: str | None = None) -> None:
    """Render a friendly empty-state message."""
    message = title if detail is None else f"{title} {detail}"
    st.info(message)


def render_error_state(title: str, error: Exception | str) -> None:
    """Render a friendly error-state message without a raw traceback."""
    st.error(f"{title} Please review the scenario settings and try again.")
    st.caption(str(error))


def _render_sidebar_intro() -> None:
    with st.sidebar:
        st.markdown(f"## {PROJECT_NAME}")
        st.caption("Synthetic NL motor insurer")
        st.markdown("### Workflow Navigation")
        st.markdown(
            """
            **Data**  
            1. Synthetic Data and Risk Engine  
            2. Experience Analysis

            **Pricing**  
            3. Portfolio Overview  
            4. Pricing

            **Reserving**  
            5. Technical Provisions

            **Reinsurance**  
            6. Reinsurance

            **Capital / ALM**  
            7. Capital Model  
            8. ALM  
            9. Solvency II Balance Sheet

            **Financial Reporting**  
            10. Financial Reporting

            **QRT Reporting**  
            11. QRT Reporting Pack

            **Board Report**  
            12. Board Risk Report

            **Governance**  
            README, audit trail, and user testing docs
            """
        )


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        main .block-container {
            padding-top: 3rem;
        }
        [data-testid="stSidebar"] code {
            white-space: normal;
            word-break: break-all;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
