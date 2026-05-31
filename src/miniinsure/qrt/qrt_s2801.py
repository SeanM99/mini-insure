"""Mock S.28.01.01 MCR template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import add_currency, eur
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate(capital: CapitalWorkflowResult) -> pd.DataFrame:
    """Generate the final MCR rows."""
    mcr = capital.mcr
    rows = [
        {"item": "mcr_linear", "amount": eur(mcr.mcr_linear), "source_field": "mcr.mcr_linear"},
        {"item": "lower_corridor", "amount": eur(mcr.lower_corridor), "source_field": "mcr.lower_corridor"},
        {"item": "upper_corridor", "amount": eur(mcr.upper_corridor), "source_field": "mcr.upper_corridor"},
        {"item": "mcr_combined", "amount": eur(mcr.mcr_combined), "source_field": "mcr.mcr_combined"},
        {"item": "final_mcr", "amount": eur(mcr.mcr), "source_field": "mcr.mcr"},
    ]
    return add_currency(pd.DataFrame(rows))
