"""Typed assumption loading and scenario metadata utilities."""

from miniinsure.assumptions.loader import (
    BASE_ASSUMPTIONS_PATH,
    REGULATORY_ASSUMPTIONS_PATH,
    build_effective_assumptions,
    load_effective_assumptions,
    load_yaml_file,
    scenario_metadata,
    scenario_metadata_json,
    stable_assumption_hash,
)
from miniinsure.assumptions.scenario_state import ScenarioState
from miniinsure.assumptions.schema import (
    PORTFOLIO_MODES,
    Assumptions,
    DisplayConventions,
    ExportConventions,
    LegalEntity,
    PortfolioMode,
    ProjectionPeriod,
    ValidationTolerances,
)

__all__ = [
    "BASE_ASSUMPTIONS_PATH",
    "REGULATORY_ASSUMPTIONS_PATH",
    "PORTFOLIO_MODES",
    "Assumptions",
    "DisplayConventions",
    "ExportConventions",
    "LegalEntity",
    "PortfolioMode",
    "ProjectionPeriod",
    "ScenarioState",
    "ValidationTolerances",
    "build_effective_assumptions",
    "load_effective_assumptions",
    "load_yaml_file",
    "scenario_metadata",
    "scenario_metadata_json",
    "stable_assumption_hash",
]
