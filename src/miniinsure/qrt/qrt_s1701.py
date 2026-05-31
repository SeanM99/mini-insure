"""Mock S.17.01.02 non-life technical provisions template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate(capital: CapitalWorkflowResult) -> pd.DataFrame:
    """Generate gross and net technical provision rows."""
    tp = capital.technical_provisions.summary
    rows = [
        {
            "item": "gross_claims_provision",
            "amount": eur(tp["claims_provision"]),
            "source_field": "technical_provisions.claims_provision.summary.present_value",
        },
        {
            "item": "gross_premium_provision",
            "amount": eur(tp["premium_provision"]),
            "source_field": "technical_provisions.premium_provision.summary.present_value",
        },
        {
            "item": "gross_best_estimate",
            "amount": eur(tp["gross_best_estimate"]),
            "source_field": "technical_provisions.summary.gross_best_estimate",
        },
        {
            "item": "reinsurance_recoverables",
            "amount": eur(tp["reinsurance_recoverables"]),
            "source_field": "technical_provisions.reinsurance_recoverables.summary.present_value",
        },
        {
            "item": "net_best_estimate",
            "amount": eur(tp["net_best_estimate"]),
            "source_field": "technical_provisions.summary.net_best_estimate",
        },
        {
            "item": "risk_margin",
            "amount": eur(tp["risk_margin"]),
            "source_field": "technical_provisions.risk_margin.risk_margin",
        },
        {
            "item": "gross_technical_provisions",
            "amount": eur(tp["gross_technical_provisions"]),
            "source_field": "technical_provisions.summary.gross_technical_provisions",
        },
        {
            "item": "net_technical_provisions",
            "amount": eur(tp["net_technical_provisions"]),
            "source_field": "technical_provisions.summary.net_technical_provisions",
        },
    ]
    return add_currency(pd.DataFrame(rows))
