"""Financial reporting and board report helpers for MiniInsure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from miniinsure.assumptions import (
    Assumptions,
    ScenarioState,
    load_effective_assumptions,
    scenario_metadata,
)
from miniinsure.pricing import COMMISSION_RATIO, EXPENSE_RATIO
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult, calculate_capital_workflow
from miniinsure.utils import APP_VERSION, MASTER_SEED, PROJECT_NAME, REPORTING_QUARTER, VALUATION_DATE


@dataclass(frozen=True)
class FinancialReportingResult:
    """Auditable financial reporting tables."""

    income_statement: pd.DataFrame
    kpis: pd.DataFrame
    balance_sheet: pd.DataFrame
    reconciliations: pd.DataFrame
    lob_income_statement: pd.DataFrame
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ReportingWorkflowResult:
    """Shared workflow object for Streamlit reporting pages."""

    capital: CapitalWorkflowResult
    financial: FinancialReportingResult
    assumptions: Assumptions
    scenario_state: ScenarioState


def calculate_reporting_workflow(
    *,
    scenario_name: str = "Base",
    portfolio_mode: str = "small",
    policies_per_year: int | None = None,
    reserve_risk_simulations: int = 250,
    capital_simulations: int = 500,
    seed: int = MASTER_SEED,
) -> ReportingWorkflowResult:
    """Run the shared capital workflow and derive reporting outputs."""
    scenario_state = ScenarioState(
        scenario_name=scenario_name,
        portfolio_mode=portfolio_mode,
        seed=seed,
    )
    assumptions = load_effective_assumptions(
        ui_overrides=scenario_state.ui_assumption_overrides(),
    )
    capital = calculate_capital_workflow(
        portfolio_mode=portfolio_mode,
        policies_per_year=policies_per_year,
        reserve_risk_simulations=reserve_risk_simulations,
        capital_simulations=capital_simulations,
        seed=seed,
    )
    financial = calculate_financial_reporting(
        capital,
        scenario_name=scenario_state.scenario_name,
        assumptions=assumptions,
        seed=seed,
    )
    return ReportingWorkflowResult(
        capital=capital,
        financial=financial,
        assumptions=assumptions,
        scenario_state=scenario_state,
    )


def calculate_financial_reporting(
    capital: CapitalWorkflowResult,
    *,
    scenario_name: str = "Base",
    assumptions: Assumptions | None = None,
    seed: int = MASTER_SEED,
    generated_at: datetime | None = None,
) -> FinancialReportingResult:
    """Create the management income statement, KPIs, and balance sheet."""
    assumptions = assumptions or load_effective_assumptions()
    metadata = scenario_metadata(
        scenario_name=scenario_name,
        assumptions=assumptions,
        seed=seed,
        generated_at=generated_at,
    )

    components = _financial_components(capital)
    income_statement = _income_statement_table(components)
    kpis = _kpi_table(capital, components)
    balance_sheet = solvency_ii_balance_sheet_table(capital)
    reconciliations = _reconciliation_table(capital, components, balance_sheet)
    lob_income_statement = _lob_income_statement(capital, components)
    return FinancialReportingResult(
        income_statement=income_statement,
        kpis=kpis,
        balance_sheet=balance_sheet,
        reconciliations=reconciliations,
        lob_income_statement=lob_income_statement,
        metadata=metadata,
    )


def generate_board_risk_report_markdown(
    *,
    capital: CapitalWorkflowResult,
    financial: FinancialReportingResult,
    validation_status: str = "not run",
    validation_errors: int = 0,
    validation_warnings: int = 0,
    generated_at: datetime | None = None,
) -> str:
    """Generate a board-style Markdown risk report."""
    timestamp = (generated_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    kpis = financial.kpis.set_index("metric")["value"].to_dict()
    tp = capital.technical_provisions.summary
    reserve_summary = capital.reserve_risk.summary.iloc[0].to_dict()
    sf = capital.standard_formula.summary
    own_funds = capital.own_funds
    mcr = capital.mcr

    solvency_ratio = float(own_funds["solvency_ratio"])
    combined_ratio = float(kpis.get("combined_ratio", 0.0))
    reserve_capital = float(reserve_summary.get("reserve_capital", 0.0))
    adverse_probability = float(reserve_summary.get("probability_of_adverse_development", 0.0))
    operational_scr = float(sf.get("operational_scr", 0.0))
    traffic_lights = [
        _traffic_light("Solvency ratio", solvency_ratio, green=1.40, amber=1.10, higher_is_better=True),
        _traffic_light("Combined ratio", combined_ratio, green=0.95, amber=1.05, higher_is_better=False),
        _traffic_light("Reserve capital / SCR", reserve_capital / max(float(sf["scr"]), 1.0), green=0.35, amber=0.60, higher_is_better=False),
        _traffic_light("Operational SCR / SCR", operational_scr / max(float(sf["scr"]), 1.0), green=0.10, amber=0.20, higher_is_better=False),
    ]
    kri_table = _markdown_table(
        traffic_lights,
        ["metric", "value", "status", "green_threshold", "amber_threshold"],
    )

    return f"""# MiniInsure Europe NL Board Risk Report

## Executive Summary

{PROJECT_NAME} remains an educational synthetic motor insurer model. The scenario shows a solvency ratio of {solvency_ratio:.1%}, eligible own funds of EUR {own_funds["eligible_own_funds"]:,.0f}, SCR of EUR {sf["scr"]:,.0f}, and MCR of EUR {mcr.mcr:,.0f}. The combined ratio is {combined_ratio:.1%}.

## Valuation Date And Scenario

- Valuation date: {VALUATION_DATE}
- Reporting quarter: {REPORTING_QUARTER}
- Scenario: {financial.metadata["scenario_name"]}
- Assumption hash: `{financial.metadata["assumption_hash"]}`
- Generated timestamp: {timestamp}
- App version: {APP_VERSION}

## Own Funds And Capital Requirements

- Eligible own funds: EUR {own_funds["eligible_own_funds"]:,.0f}
- Tier 1 unrestricted own funds: EUR {own_funds["tier_1_unrestricted"]:,.0f}
- SCR: EUR {sf["scr"]:,.0f}
- MCR: EUR {mcr.mcr:,.0f}
- MCR ratio: {own_funds["mcr_ratio"]:.1%}

## Technical Provisions

- Gross technical provisions: EUR {tp["gross_technical_provisions"]:,.0f}
- Reinsurance recoverables: EUR {tp["reinsurance_recoverables"]:,.0f}
- Net technical provisions: EUR {tp["net_technical_provisions"]:,.0f}
- Risk margin: EUR {tp["risk_margin"]:,.0f}
- Reconciliation status: {tp["reconciliation_status"].upper()}

## Reserve Risk Summary

- Mean reserve loss: EUR {reserve_summary["mean"]:,.0f}
- VaR 99.5% reserve loss: EUR {reserve_summary["var_995"]:,.0f}
- TVaR 99.5% reserve loss: EUR {reserve_summary["tvar_995"]:,.0f}
- Reserve capital: EUR {reserve_summary["reserve_capital"]:,.0f}
- Probability of adverse development: {adverse_probability:.1%}

## Risk Commentary

Premium risk is represented through aggregate frequency and severity variation using the deterministic policy portfolio as exposure. Reinsurance risk reflects the default fixed treaty program and counterparty default adjustment. Market risk reflects the educational asset allocation, interest-rate, spread, and equity shocks. Operational risk uses the simplified proxy already visible in the capital model.

## Traffic-Light KRIs

{kri_table}

## Validation Status

- QRT validation status: {validation_status.upper()}
- Blocking errors: {validation_errors}
- Warnings: {validation_warnings}

## Limitations

This report is educational only. It does not represent a real insurer, does not produce real Solvency II filings, and does not create real XBRL. Synthetic truth outputs are isolated for diagnostics and are not used in reserving, reporting, QRT-shaped templates, or board reporting.
"""


def _financial_components(capital: CapitalWorkflowResult) -> dict[str, float]:
    policies = capital.policies
    provisions = capital.technical_provisions
    claims_summary = provisions.claims_provision.summary
    reinsurance_annual = provisions.reinsurance_recoverables.reinsurance_result.annual_level

    gross_written_premium = float(policies["written_premium"].sum())
    gross_earned_premium = float(policies["earned_premium"].sum())
    paid_claims = float(capital.reserving_results["latest_paid"].sum()) if not capital.reserving_results.empty else 0.0
    change_in_gross_claims_provision = float(claims_summary["present_value"])
    gross_claims_incurred = paid_claims + change_in_gross_claims_provision
    ceded_recoveries = float(provisions.summary["reinsurance_recoverables"])
    reinsurance_premium_cost = _reinsurance_premium_cost(reinsurance_annual)
    net_claims_incurred = gross_claims_incurred - ceded_recoveries + reinsurance_premium_cost
    acquisition_expenses = gross_earned_premium * COMMISSION_RATIO
    administration_expenses = gross_earned_premium * EXPENSE_RATIO
    claims_handling_expenses = float(claims_summary["allocated_loss_adjustment_expense"]) + float(
        claims_summary["unallocated_loss_adjustment_expense"]
    )
    expenses = acquisition_expenses + administration_expenses + claims_handling_expenses
    net_earned_premium = gross_earned_premium - _quota_share_ceded_premium(reinsurance_annual)
    underwriting_result = net_earned_premium - net_claims_incurred - expenses
    investment_result = float(capital.one_year_capital.simulations["investment_result"].mean())
    profit_before_tax = underwriting_result + investment_result
    scr = float(capital.standard_formula.summary["scr"])

    return {
        "gross_written_premium": gross_written_premium,
        "gross_earned_premium": gross_earned_premium,
        "net_earned_premium": net_earned_premium,
        "paid_claims": paid_claims,
        "change_in_gross_claims_provision": change_in_gross_claims_provision,
        "gross_claims_incurred": gross_claims_incurred,
        "ceded_recoveries": ceded_recoveries,
        "reinsurance_premium_cost": reinsurance_premium_cost,
        "net_claims_incurred": net_claims_incurred,
        "acquisition_expenses": acquisition_expenses,
        "administration_expenses": administration_expenses,
        "claims_handling_expenses": claims_handling_expenses,
        "expenses": expenses,
        "underwriting_result": underwriting_result,
        "investment_result": investment_result,
        "profit_before_tax": profit_before_tax,
        "tax": 0.0,
        "profit_after_tax": profit_before_tax,
        "combined_ratio": (net_claims_incurred + expenses) / net_earned_premium if net_earned_premium else np.nan,
        "return_on_capital": profit_before_tax / scr if scr else np.nan,
    }


def _income_statement_table(components: dict[str, float]) -> pd.DataFrame:
    rows = [
        ("gross_written_premium", "Gross written premium", components["gross_written_premium"]),
        ("gross_earned_premium", "Gross earned premium", components["gross_earned_premium"]),
        ("net_earned_premium", "Net earned premium", components["net_earned_premium"]),
        ("paid_claims", "Paid claims", components["paid_claims"]),
        (
            "change_in_gross_claims_provision",
            "Change in gross claims provision",
            components["change_in_gross_claims_provision"],
        ),
        ("gross_claims_incurred", "Gross claims incurred", components["gross_claims_incurred"]),
        ("ceded_recoveries", "Ceded recoveries", components["ceded_recoveries"]),
        ("reinsurance_premium_cost", "Reinsurance premium cost", components["reinsurance_premium_cost"]),
        ("net_claims_incurred", "Net claims incurred", components["net_claims_incurred"]),
        ("acquisition_expenses", "Acquisition expenses", components["acquisition_expenses"]),
        ("administration_expenses", "Administration expenses", components["administration_expenses"]),
        ("claims_handling_expenses", "Claims handling expenses", components["claims_handling_expenses"]),
        ("expenses", "Total expenses", components["expenses"]),
        ("underwriting_result", "Underwriting result", components["underwriting_result"]),
        ("investment_result", "Investment result", components["investment_result"]),
        ("profit_before_tax", "Profit before tax", components["profit_before_tax"]),
        ("tax", "Tax disabled", components["tax"]),
        ("profit_after_tax", "Profit after tax", components["profit_after_tax"]),
    ]
    return pd.DataFrame(rows, columns=["line_item", "description", "amount"])


def _kpi_table(capital: CapitalWorkflowResult, components: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "combined_ratio", "description": "Combined ratio", "value": components["combined_ratio"]},
            {"metric": "return_on_capital", "description": "Return on capital", "value": components["return_on_capital"]},
            {"metric": "solvency_ratio", "description": "Solvency ratio", "value": capital.own_funds["solvency_ratio"]},
            {"metric": "mcr_ratio", "description": "MCR ratio", "value": capital.own_funds["mcr_ratio"]},
        ]
    )


def solvency_ii_balance_sheet_table(capital: CapitalWorkflowResult) -> pd.DataFrame:
    """Return a gross-up balance sheet with recoverables shown as assets."""
    assets_without_recoverables = float(capital.balance_sheet.summary["assets"])
    reinsurance_recoverables = float(capital.technical_provisions.summary["reinsurance_recoverables"])
    gross_technical_provisions = float(capital.technical_provisions.summary["gross_technical_provisions"])
    other_liabilities = float(capital.balance_sheet.summary["other_liabilities"])
    total_assets = assets_without_recoverables + reinsurance_recoverables
    total_liabilities = gross_technical_provisions + other_liabilities
    excess = total_assets - total_liabilities
    rows = [
        ("assets", "asset_portfolio_market_value", assets_without_recoverables),
        ("assets", "reinsurance_recoverables", reinsurance_recoverables),
        ("assets", "total_assets", total_assets),
        ("liabilities", "gross_technical_provisions", gross_technical_provisions),
        ("liabilities", "other_liabilities", other_liabilities),
        ("liabilities", "total_liabilities", total_liabilities),
        ("own_funds", "excess_assets_over_liabilities", excess),
        ("own_funds", "tier_1_unrestricted", excess),
        ("capital_requirement", "scr", float(capital.standard_formula.summary["scr"])),
        ("capital_requirement", "mcr", float(capital.mcr.mcr)),
    ]
    return pd.DataFrame(rows, columns=["section", "line_item", "amount"])


def _reconciliation_table(
    capital: CapitalWorkflowResult,
    components: dict[str, float],
    balance_sheet: pd.DataFrame,
) -> pd.DataFrame:
    def amount(line_item: str) -> float:
        return float(balance_sheet.loc[balance_sheet["line_item"] == line_item, "amount"].iloc[0])

    rows = [
        {
            "check": "gross_claims_incurred_formula",
            "actual": components["gross_claims_incurred"],
            "expected": components["paid_claims"] + components["change_in_gross_claims_provision"],
        },
        {
            "check": "net_claims_incurred_formula",
            "actual": components["net_claims_incurred"],
            "expected": components["gross_claims_incurred"] - components["ceded_recoveries"] + components["reinsurance_premium_cost"],
        },
        {
            "check": "balance_sheet_excess",
            "actual": amount("excess_assets_over_liabilities"),
            "expected": amount("total_assets") - amount("total_liabilities"),
        },
        {
            "check": "tier_1_unrestricted",
            "actual": amount("tier_1_unrestricted"),
            "expected": amount("excess_assets_over_liabilities"),
        },
        {
            "check": "technical_provisions_reconciliation",
            "actual": float(capital.technical_provisions.summary["gross_technical_provisions"])
            - float(capital.technical_provisions.summary["reinsurance_recoverables"]),
            "expected": float(capital.technical_provisions.summary["net_technical_provisions"]),
        },
    ]
    result = pd.DataFrame(rows)
    result["difference"] = result["actual"] - result["expected"]
    result["status"] = np.where(result["difference"].abs() <= 0.01, "pass", "fail")
    return result


def _lob_income_statement(
    capital: CapitalWorkflowResult,
    components: dict[str, float],
) -> pd.DataFrame:
    policies = capital.policies
    reserving = capital.reserving_results
    if policies.empty:
        return pd.DataFrame()
    lob = (
        policies.groupby("solvency_ii_lob", as_index=False)
        .agg(
            gross_written_premium=("written_premium", "sum"),
            gross_earned_premium=("earned_premium", "sum"),
        )
    )
    if reserving.empty:
        paid = pd.DataFrame(columns=["solvency_ii_lob", "paid_claims"])
    else:
        paid = (
            reserving.groupby("solvency_ii_lob", as_index=False)
            .agg(paid_claims=("latest_paid", "sum"))
        )
    lob = lob.merge(paid, on="solvency_ii_lob", how="left").fillna({"paid_claims": 0.0})
    provision_by_lob = _claims_provision_by_lob(capital)
    lob = lob.merge(provision_by_lob, on="solvency_ii_lob", how="left").fillna(
        {"change_in_gross_claims_provision": 0.0}
    )
    lob["gross_claims_incurred"] = lob["paid_claims"] + lob["change_in_gross_claims_provision"]
    shares = _lob_shares(lob, "gross_earned_premium")
    lob["ceded_recoveries"] = shares * components["ceded_recoveries"]
    lob["reinsurance_premium_cost"] = shares * components["reinsurance_premium_cost"]
    lob["net_claims_incurred"] = (
        lob["gross_claims_incurred"] - lob["ceded_recoveries"] + lob["reinsurance_premium_cost"]
    )
    lob["acquisition_expenses"] = lob["gross_earned_premium"] * COMMISSION_RATIO
    lob["administration_expenses"] = lob["gross_earned_premium"] * EXPENSE_RATIO
    lob["claims_handling_expenses"] = shares * components["claims_handling_expenses"]
    lob["expenses"] = lob["acquisition_expenses"] + lob["administration_expenses"] + lob["claims_handling_expenses"]
    return lob


def _claims_provision_by_lob(capital: CapitalWorkflowResult) -> pd.DataFrame:
    cashflows = capital.technical_provisions.claims_provision.cashflows
    if not cashflows.empty and {"solvency_ii_lob", "present_value"}.issubset(cashflows.columns):
        grouped = (
            cashflows.groupby("solvency_ii_lob", as_index=False)
            .agg(change_in_gross_claims_provision=("present_value", "sum"))
        )
        return grouped
    reserving = capital.reserving_results
    if reserving.empty:
        return pd.DataFrame(columns=["solvency_ii_lob", "change_in_gross_claims_provision"])
    return (
        reserving.groupby("solvency_ii_lob", as_index=False)
        .agg(change_in_gross_claims_provision=("selected_reserve", "sum"))
    )


def _reinsurance_premium_cost(annual: pd.DataFrame) -> float:
    if annual.empty:
        return 0.0
    cost_columns = [
        "quota_share_ceded_premium",
        "per_risk_xol_premium",
        "per_risk_reinstatement_premium",
        "aggregate_stop_loss_premium",
    ]
    cost = sum(float(annual[column].sum()) for column in cost_columns if column in annual.columns)
    commission = float(annual["quota_share_ceding_commission"].sum()) if "quota_share_ceding_commission" in annual.columns else 0.0
    return cost - commission


def _quota_share_ceded_premium(annual: pd.DataFrame) -> float:
    if annual.empty or "quota_share_ceded_premium" not in annual.columns:
        return 0.0
    return float(annual["quota_share_ceded_premium"].sum())


def _lob_shares(lob: pd.DataFrame, amount_column: str) -> pd.Series:
    total = float(lob[amount_column].sum())
    if total == 0.0:
        return pd.Series(np.repeat(1.0 / max(len(lob), 1), len(lob)), index=lob.index)
    return lob[amount_column].astype(float) / total


def _traffic_light(
    metric: str,
    value: float,
    *,
    green: float,
    amber: float,
    higher_is_better: bool,
) -> dict[str, object]:
    if higher_is_better:
        status = "green" if value >= green else "amber" if value >= amber else "red"
    else:
        status = "green" if value <= green else "amber" if value <= amber else "red"
    return {
        "metric": metric,
        "value": f"{value:.1%}",
        "status": status,
        "green_threshold": f"{green:.1%}",
        "amber_threshold": f"{amber:.1%}",
    }


def _markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])
