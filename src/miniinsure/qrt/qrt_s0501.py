"""Mock S.05.01.02 premiums, claims, and expenses template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.reporting import FinancialReportingResult


def generate(financial: FinancialReportingResult) -> pd.DataFrame:
    """Generate premium, claim, and expense rows by Solvency II LoB."""
    if financial.lob_income_statement.empty:
        return add_currency(pd.DataFrame())
    qrt = financial.lob_income_statement.copy()
    qrt = qrt[
        [
            "solvency_ii_lob",
            "gross_written_premium",
            "gross_earned_premium",
            "paid_claims",
            "change_in_gross_claims_provision",
            "gross_claims_incurred",
            "ceded_recoveries",
            "reinsurance_premium_cost",
            "net_claims_incurred",
            "expenses",
        ]
    ].copy()
    for column in qrt.columns:
        if column != "solvency_ii_lob":
            qrt[column] = qrt[column].apply(eur)
    qrt["source_field"] = "financial.lob_income_statement"
    return add_currency(qrt)
