"""Shared capital model workflow for Streamlit pages."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from miniinsure.mcr import MCRResult, calculate_mcr
from miniinsure.own_funds import BalanceSheetResult, opening_balance_sheet, own_funds_summary
from miniinsure.reserving.deterministic_methods import deterministic_reserving_results
from miniinsure.reserving.reserve_risk import ReserveRiskResult, simulate_reserve_risk_quick
from miniinsure.reserving.technical_provisions import TechnicalProvisionsResult, calculate_technical_provisions
from miniinsure.reserving.triangles import build_annual_triangles
from miniinsure.risk_engine.one_year_engine import OneYearCapitalResult, simulate_one_year_economic_capital
from miniinsure.simulation.synthetic_reality import generate_synthetic_reality
from miniinsure.standard_formula import StandardFormulaResult, simplified_standard_formula_with_opening_assets
from miniinsure.utils import MASTER_SEED

OTHER_LIABILITIES_RATIO_OF_NEP = 0.02


@dataclass(frozen=True)
class CapitalWorkflowResult:
    """Common capital model and balance sheet output."""

    policies: pd.DataFrame
    reserving_results: pd.DataFrame
    technical_provisions: TechnicalProvisionsResult
    reserve_risk: ReserveRiskResult
    standard_formula: StandardFormulaResult
    mcr: MCRResult
    balance_sheet: BalanceSheetResult
    own_funds: dict[str, float]
    one_year_capital: OneYearCapitalResult
    stress_summaries: pd.DataFrame


def calculate_capital_workflow(
    *,
    portfolio_mode: str = "small",
    policies_per_year: int | None = None,
    reserve_risk_simulations: int = 250,
    capital_simulations: int = 500,
    seed: int = MASTER_SEED,
) -> CapitalWorkflowResult:
    """Calculate the full phase capital and balance-sheet workflow."""
    reality = generate_synthetic_reality(
        portfolio_mode=portfolio_mode,
        seed=seed,
        policies_per_year=policies_per_year,
    )
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
        n_simulations=reserve_risk_simulations,
        seed=seed,
    )
    nep = float(reality.policies["earned_premium"].sum())
    other_liabilities = OTHER_LIABILITIES_RATIO_OF_NEP * nep
    opening_liabilities = float(provisions.summary["net_technical_provisions"]) + other_liabilities
    nep_by_lob = reality.policies.groupby("solvency_ii_lob")["earned_premium"].sum().to_dict()
    net_claims_be_by_lob = reserving_results.groupby("solvency_ii_lob")["selected_reserve"].sum().to_dict()
    net_catastrophe_losses = reserve_risk.simulations["reserve_loss"].clip(lower=0.0) * 0.20
    standard_formula = simplified_standard_formula_with_opening_assets(
        opening_liabilities=opening_liabilities,
        nep_by_lob=nep_by_lob,
        net_claims_be_by_lob=net_claims_be_by_lob,
        net_catastrophe_losses=net_catastrophe_losses,
        reinsurance_recoverables=float(provisions.summary["reinsurance_recoverables"]),
        nep=nep,
        net_technical_provisions=float(provisions.summary["net_technical_provisions"]),
    )
    scr = float(standard_formula.summary["scr"])
    mcr = calculate_mcr(
        nwp=nep,
        net_claims_be=float(reserving_results["selected_reserve"].sum()),
        scr=scr,
    )
    balance_sheet = opening_balance_sheet(
        technical_provisions=float(provisions.summary["net_technical_provisions"]),
        other_liabilities=other_liabilities,
        scr=scr,
    )
    own_funds = own_funds_summary(
        assets=float(balance_sheet.summary["assets"]),
        liabilities=float(balance_sheet.summary["liabilities"]),
        scr=scr,
        mcr=mcr.mcr,
    )
    one_year = simulate_one_year_economic_capital(
        reality.policies,
        reserve_risk.simulations,
        opening_own_funds=float(balance_sheet.summary["own_funds"]),
        opening_net_best_estimate=float(provisions.summary["net_best_estimate"]),
        reinsurance_recoverables=float(provisions.summary["reinsurance_recoverables"]),
        n_simulations=capital_simulations,
        seed=seed,
        asset_portfolio=standard_formula.asset_portfolio,
    )
    stress_summaries = _stress_summary(one_year.simulations, standard_formula.market)
    return CapitalWorkflowResult(
        policies=reality.policies,
        reserving_results=reserving_results,
        technical_provisions=provisions,
        reserve_risk=reserve_risk,
        standard_formula=standard_formula,
        mcr=mcr,
        balance_sheet=balance_sheet,
        own_funds=own_funds,
        one_year_capital=one_year,
        stress_summaries=stress_summaries,
    )


def _stress_summary(one_year: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        [
            {
                "stress": "premium_risk_99_5",
                "loss": float(one_year["premium_risk_loss"].quantile(0.995)),
            },
            {
                "stress": "reserve_risk_99_5",
                "loss": float(one_year["reserve_loss"].quantile(0.995)),
            },
            {
                "stress": "market_risk_99_5",
                "loss": float(one_year["market_risk_loss"].quantile(0.995)),
            },
            {
                "stress": "operational_loss_proxy",
                "loss": float(one_year["operational_loss"].iloc[0]) if not one_year.empty else 0.0,
            },
        ]
    )
    if not market.empty:
        market_row = market.iloc[0].to_dict()
        market_rows = [
            {"stress": "sf_equity_shock", "loss": float(market_row["equity"])},
            {"stress": "sf_interest_rate_shock", "loss": float(market_row["interest_rate_scr"])},
            {"stress": "sf_spread_shock", "loss": float(market_row["spread"])},
        ]
        summary = pd.concat([summary, pd.DataFrame(market_rows)], ignore_index=True)
    return summary
