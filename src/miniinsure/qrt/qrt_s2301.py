"""Mock S.23.01.01 own funds template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.reporting import FinancialReportingResult
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate(capital: CapitalWorkflowResult, financial: FinancialReportingResult) -> pd.DataFrame:
    """Generate own funds and capital requirement rows."""
    balance = financial.balance_sheet.set_index("line_item")["amount"].to_dict()
    excess = float(balance["excess_assets_over_liabilities"])
    rows = [
        {
            "item": "tier_1_unrestricted_own_funds",
            "amount": eur(excess),
            "source_field": "financial.balance_sheet.excess_assets_over_liabilities",
        },
        {
            "item": "eligible_own_funds_to_meet_scr",
            "amount": eur(excess),
            "source_field": "financial.balance_sheet.excess_assets_over_liabilities",
        },
        {
            "item": "eligible_own_funds_to_meet_mcr",
            "amount": eur(excess),
            "source_field": "financial.balance_sheet.excess_assets_over_liabilities",
        },
        {
            "item": "scr",
            "amount": eur(capital.standard_formula.summary["scr"]),
            "source_field": "standard_formula.summary.scr",
        },
        {
            "item": "mcr",
            "amount": eur(capital.mcr.mcr),
            "source_field": "mcr.mcr",
        },
    ]
    return add_currency(pd.DataFrame(rows))
