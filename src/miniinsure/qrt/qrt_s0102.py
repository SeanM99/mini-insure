"""Mock S.01.02.01 basic information template."""

from __future__ import annotations

import pandas as pd

from miniinsure.assumptions import Assumptions
from miniinsure.utils import APP_VERSION


def generate(assumptions: Assumptions, *, scenario_name: str, assumption_hash: str) -> pd.DataFrame:
    """Generate synthetic undertaking and reporting information."""
    return pd.DataFrame(
        [
            {"field": "undertaking_name", "value": assumptions.legal_entity.name, "source_field": "assumptions.legal_entity.name"},
            {"field": "lei", "value": assumptions.legal_entity.lei, "source_field": "assumptions.legal_entity.lei"},
            {"field": "supervisor", "value": assumptions.supervisor, "source_field": "assumptions.supervisor"},
            {"field": "jurisdiction", "value": assumptions.jurisdiction, "source_field": "assumptions.jurisdiction"},
            {"field": "reporting_framework", "value": assumptions.reporting_framework, "source_field": "assumptions.reporting_framework"},
            {"field": "business_type", "value": assumptions.business_type, "source_field": "assumptions.business_type"},
            {"field": "product", "value": assumptions.product, "source_field": "assumptions.product"},
            {"field": "valuation_date", "value": assumptions.valuation_date.isoformat(), "source_field": "assumptions.valuation_date"},
            {"field": "reporting_quarter", "value": assumptions.primary_reporting_quarter, "source_field": "assumptions.primary_reporting_quarter"},
            {"field": "reporting_currency", "value": assumptions.reporting_currency, "source_field": "assumptions.reporting_currency"},
            {"field": "scenario_name", "value": scenario_name, "source_field": "ScenarioState.scenario_name"},
            {"field": "assumption_hash", "value": assumption_hash, "source_field": "stable_assumption_hash(assumptions)"},
            {"field": "app_version", "value": APP_VERSION, "source_field": "miniinsure.utils.APP_VERSION"},
            {"field": "real_xbrl_disabled", "value": str(assumptions.real_xbrl_disabled), "source_field": "assumptions.real_xbrl_disabled"},
            {"field": "mock_reporting_only", "value": str(assumptions.export_conventions.qrt_outputs_are_mock_only), "source_field": "assumptions.export_conventions.qrt_outputs_are_mock_only"},
        ]
    )
