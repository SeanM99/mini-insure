"""Auditable mappings for mock QRT-shaped templates."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

REPORTING_CURRENCY = "EUR"
MONETARY_DECIMALS = 0

TEMPLATE_STATUS = {
    "S.01.01.02": "generated",
    "S.01.02.01": "generated",
    "S.02.01.02": "generated",
    "S.05.01.02": "generated",
    "S.06.02.01": "generated",
    "S.06.03.01": "conditional",
    "S.08.01.01": "empty generated",
    "S.12.01.02": "not applicable",
    "S.17.01.02": "generated",
    "S.23.01.01": "generated",
    "S.28.01.01": "generated",
    "S.28.02.01": "not applicable",
}

TEMPLATE_NOTES = {
    "S.01.01.02": "Content-of-submission index for mock QRT pack.",
    "S.01.02.01": "Basic synthetic undertaking and reporting information.",
    "S.02.01.02": "Solvency II-style balance sheet projection; mock only.",
    "S.05.01.02": "Premiums, claims, and expenses by Solvency II line of business.",
    "S.06.02.01": "Asset holding table from the educational ALM asset portfolio.",
    "S.06.03.01": "Conditional derivatives template; generated only as no-derivative marker.",
    "S.08.01.01": "Open derivatives template; empty because derivatives are out of scope.",
    "S.12.01.02": "Life technical provisions template; not applicable to synthetic motor insurer.",
    "S.17.01.02": "Non-life technical provisions projection.",
    "S.23.01.01": "Own funds and capital requirement projection.",
    "S.28.01.01": "Minimum Capital Requirement projection.",
    "S.28.02.01": "Composite/life MCR template; not applicable.",
}

QRT_MAPPINGS = {
    "S.02.01.02": {
        "investments_excluding_cash": "standard_formula.asset_portfolio.market_value where asset_class != 'cash'",
        "cash_and_deposits": "standard_formula.asset_portfolio.market_value where asset_class == 'cash'",
        "reinsurance_recoverables": "technical_provisions.summary.reinsurance_recoverables",
        "technical_provisions_non_life_net_best_estimate_plus_risk_margin": "technical_provisions.summary.net_best_estimate + risk_margin",
    },
    "S.05.01.02": {
        "gross_written_premium": "policies.written_premium grouped by solvency_ii_lob",
        "gross_earned_premium": "policies.earned_premium grouped by solvency_ii_lob",
        "gross_claims_incurred": "financial.lob_income_statement paid_claims + change_in_gross_claims_provision",
        "expenses": "financial.lob_income_statement acquisition + administration + claims handling expenses",
    },
    "S.06.02.01": {
        "market_value": "standard_formula.asset_portfolio.market_value by asset_class",
    },
    "S.17.01.02": {
        "gross_claims_provision": "technical_provisions.claims_provision.summary.present_value",
        "gross_premium_provision": "technical_provisions.premium_provision.summary.present_value",
        "reinsurance_recoverables": "technical_provisions.reinsurance_recoverables.summary.present_value",
        "risk_margin": "technical_provisions.risk_margin.risk_margin",
    },
    "S.23.01.01": {
        "tier_1_unrestricted": "financial balance sheet excess assets over liabilities",
        "scr": "standard_formula.summary.scr",
        "mcr": "mcr.mcr",
    },
    "S.28.01.01": {
        "final_mcr": "mcr.mcr",
    },
}

MONETARY_COLUMN_NAMES = {
    "amount",
    "market_value",
    "gross_written_premium",
    "gross_earned_premium",
    "paid_claims",
    "change_in_gross_claims_provision",
    "gross_claims_incurred",
    "ceded_recoveries",
    "reinsurance_premium_cost",
    "net_claims_incurred",
    "expenses",
    "scr",
    "mcr",
    "mcr_linear",
    "mcr_combined",
    "lower_corridor",
    "upper_corridor",
}


@dataclass(frozen=True)
class ExportNames:
    """Stable mock export file names."""

    scenario_slug: str
    qrt_xlsx: str
    qrt_zip: str
    board_report_md: str
    metadata_json: str = "scenario_metadata.json"


def applicability_matrix() -> pd.DataFrame:
    """Return the explicit QRT applicability matrix."""
    return pd.DataFrame(
        [
            {
                "template": template,
                "status": status,
                "generated": status in {"generated", "conditional", "empty generated"},
                "note": TEMPLATE_NOTES[template],
            }
            for template, status in TEMPLATE_STATUS.items()
        ]
    )


def mapping_table() -> pd.DataFrame:
    """Return traceable source-field mappings."""
    rows: list[dict[str, str]] = []
    for template, mappings in QRT_MAPPINGS.items():
        for qrt_field, source_field in mappings.items():
            rows.append(
                {
                    "template": template,
                    "qrt_field": qrt_field,
                    "source_field": source_field,
                }
            )
    return pd.DataFrame(rows)


def eur(value: float) -> float:
    """Round a monetary value according to the mock export convention."""
    return float(np.round(float(value), MONETARY_DECIMALS))


def add_currency(frame: pd.DataFrame, currency: str = REPORTING_CURRENCY) -> pd.DataFrame:
    """Attach the reporting currency to rows with monetary values."""
    result = frame.copy()
    result["currency"] = currency
    return result


def monetary_columns(frame: pd.DataFrame) -> list[str]:
    """Detect columns subject to the EUR rounding convention."""
    return [
        column
        for column in frame.columns
        if column in MONETARY_COLUMN_NAMES or column.endswith("_amount") or column.endswith("_value")
    ]


def export_names(scenario_name: str) -> ExportNames:
    """Return stable mock export file names for a scenario."""
    slug = scenario_slug(scenario_name)
    prefix = f"miniinsure_europe_nl"
    return ExportNames(
        scenario_slug=slug,
        qrt_xlsx=f"{prefix}_qrt_mock_2026Q4_{slug}.xlsx",
        qrt_zip=f"{prefix}_qrt_mock_2026Q4_{slug}.zip",
        board_report_md=f"{prefix}_board_risk_report_{slug}.md",
    )


def scenario_slug(scenario_name: str) -> str:
    """Normalize scenario names for deterministic file names."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(scenario_name).strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "base"
