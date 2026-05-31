"""Mock S.02.01.02 balance sheet template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.reporting import FinancialReportingResult
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate(capital: CapitalWorkflowResult, financial: FinancialReportingResult) -> pd.DataFrame:
    """Generate a Solvency II-style balance sheet table."""
    assets = capital.standard_formula.asset_portfolio
    if assets is None:
        assets = pd.DataFrame(columns=["asset_class", "market_value"])
    cash = float(assets.loc[assets["asset_class"] == "cash", "market_value"].sum()) if not assets.empty else 0.0
    investments = float(assets.loc[assets["asset_class"] != "cash", "market_value"].sum()) if not assets.empty else 0.0
    tp = capital.technical_provisions.summary
    balance = financial.balance_sheet.set_index("line_item")["amount"].to_dict()
    net_tp = float(tp["net_best_estimate"]) + float(tp["risk_margin"])
    rows = [
        {
            "section": "assets",
            "item": "investments_excluding_cash",
            "amount": eur(investments),
            "source_field": "standard_formula.asset_portfolio.market_value where asset_class != 'cash'",
        },
        {
            "section": "assets",
            "item": "cash_and_deposits",
            "amount": eur(cash),
            "source_field": "standard_formula.asset_portfolio.market_value where asset_class == 'cash'",
        },
        {
            "section": "assets",
            "item": "reinsurance_recoverables",
            "amount": eur(tp["reinsurance_recoverables"]),
            "source_field": "technical_provisions.summary.reinsurance_recoverables",
        },
        {
            "section": "assets",
            "item": "total_assets",
            "amount": eur(balance["total_assets"]),
            "source_field": "financial.balance_sheet.total_assets",
        },
        {
            "section": "liabilities",
            "item": "technical_provisions_non_life_net_best_estimate_plus_risk_margin",
            "amount": eur(net_tp),
            "source_field": "technical_provisions.summary.net_best_estimate + risk_margin",
        },
        {
            "section": "liabilities",
            "item": "reinsurance_recoverables_balance_sheet_gross_up",
            "amount": eur(tp["reinsurance_recoverables"]),
            "source_field": "technical_provisions.summary.reinsurance_recoverables",
        },
        {
            "section": "liabilities",
            "item": "technical_provisions_non_life_gross_balance_sheet",
            "amount": eur(tp["gross_technical_provisions"]),
            "source_field": "technical_provisions.summary.gross_technical_provisions",
        },
        {
            "section": "liabilities",
            "item": "other_liabilities",
            "amount": eur(capital.balance_sheet.summary["other_liabilities"]),
            "source_field": "balance_sheet.summary.other_liabilities",
        },
        {
            "section": "liabilities",
            "item": "total_liabilities",
            "amount": eur(balance["total_liabilities"]),
            "source_field": "financial.balance_sheet.total_liabilities",
        },
        {
            "section": "own_funds",
            "item": "excess_assets_over_liabilities",
            "amount": eur(balance["excess_assets_over_liabilities"]),
            "source_field": "financial.balance_sheet.excess_assets_over_liabilities",
        },
    ]
    return add_currency(pd.DataFrame(rows))
