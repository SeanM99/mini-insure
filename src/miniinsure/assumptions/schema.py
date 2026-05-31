"""Pydantic schema for MiniInsure assumption sets."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from miniinsure.utils import MASTER_SEED

PortfolioMode = Literal["small", "medium", "full"]
PORTFOLIO_MODES: tuple[PortfolioMode, ...] = ("small", "medium", "full")


class LegalEntity(BaseModel):
    """Synthetic legal entity profile."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    registration_id: str = Field(min_length=1)
    lei: str = Field(min_length=1)
    country: str = Field(min_length=1)


class ProjectionPeriod(BaseModel):
    """Projection year window."""

    model_config = ConfigDict(frozen=True)

    start_year: int
    end_year: int

    @model_validator(mode="after")
    def validate_year_order(self) -> "ProjectionPeriod":
        if self.end_year < self.start_year:
            raise ValueError("projection_period.end_year must be after start_year")
        return self


class DisplayConventions(BaseModel):
    """UI and report display conventions."""

    model_config = ConfigDict(frozen=True)

    date_format: str = Field(min_length=1)
    decimal_places: int = Field(ge=0, le=8)
    percent_decimal_places: int = Field(ge=0, le=8)
    currency_symbol: str = Field(min_length=1)


class ExportConventions(BaseModel):
    """Export naming and limitation conventions."""

    model_config = ConfigDict(frozen=True)

    file_prefix: str = Field(min_length=1)
    include_scenario_metadata: bool = True
    qrt_outputs_are_mock_only: bool = True

    @field_validator("qrt_outputs_are_mock_only")
    @classmethod
    def validate_mock_reporting_only(cls, value: bool) -> bool:
        if not value:
            raise ValueError("QRT outputs must remain mock-only")
        return value


class ValidationTolerances(BaseModel):
    """Numeric validation tolerances."""

    model_config = ConfigDict(frozen=True)

    monetary_abs: float = Field(ge=0)
    ratio_abs: float = Field(ge=0)


class Assumptions(BaseModel):
    """Effective assumptions after deterministic layer merging."""

    model_config = ConfigDict(frozen=True)

    legal_entity: LegalEntity
    supervisor: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    reporting_framework: str = Field(min_length=1)
    business_type: str = Field(min_length=1)
    product: str = Field(min_length=1)
    reporting_currency: str = Field(min_length=3, max_length=3)
    valuation_date: date
    projection_period: ProjectionPeriod
    historical_accident_years: list[int] = Field(min_length=1)
    primary_reporting_quarter: str = Field(min_length=1)
    master_seed: int
    selectable_portfolio_modes: tuple[PortfolioMode, ...]
    portfolio_mode: PortfolioMode
    policy_counts_by_year: dict[int, int] = Field(min_length=1)
    market_cycle_factors: dict[str, float] = Field(min_length=1)
    display_conventions: DisplayConventions
    export_conventions: ExportConventions
    validation_tolerances: ValidationTolerances
    real_xbrl_disabled: bool

    @field_validator("master_seed")
    @classmethod
    def validate_master_seed(cls, value: int) -> int:
        if value != MASTER_SEED:
            raise ValueError(f"master_seed must equal {MASTER_SEED}")
        return value

    @field_validator("real_xbrl_disabled")
    @classmethod
    def validate_xbrl_disabled(cls, value: bool) -> bool:
        if not value:
            raise ValueError("real XBRL must remain disabled")
        return value

    @field_validator("historical_accident_years")
    @classmethod
    def validate_accident_years(cls, value: list[int]) -> list[int]:
        if value != sorted(value):
            raise ValueError("historical_accident_years must be sorted")
        if len(value) != len(set(value)):
            raise ValueError("historical_accident_years must be unique")
        return value

    @field_validator("policy_counts_by_year")
    @classmethod
    def validate_policy_counts(cls, value: dict[int, int]) -> dict[int, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("policy_counts_by_year cannot contain negative counts")
        return value

    @field_validator("market_cycle_factors")
    @classmethod
    def validate_market_cycle_factors(cls, value: dict[str, float]) -> dict[str, float]:
        if any(factor <= 0 for factor in value.values()):
            raise ValueError("market_cycle_factors must be positive")
        return value

    @model_validator(mode="after")
    def validate_portfolio_mode_is_selectable(self) -> "Assumptions":
        if self.portfolio_mode not in self.selectable_portfolio_modes:
            raise ValueError("portfolio_mode must be one of selectable_portfolio_modes")
        if self.selectable_portfolio_modes != PORTFOLIO_MODES:
            raise ValueError("selectable_portfolio_modes must be small, medium, full")
        return self
