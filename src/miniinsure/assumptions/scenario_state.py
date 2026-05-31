"""Scenario state shared by Streamlit pages."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from miniinsure.assumptions.loader import scenario_metadata_json
from miniinsure.assumptions.schema import Assumptions, PortfolioMode
from miniinsure.utils import MASTER_SEED


class ScenarioState(BaseModel):
    """UI-facing scenario selections with reproducible metadata helpers."""

    model_config = ConfigDict(frozen=True)

    scenario_name: str = Field(default="Base", max_length=120)
    portfolio_mode: PortfolioMode = "medium"
    seed: int = MASTER_SEED

    @field_validator("scenario_name", mode="before")
    @classmethod
    def normalize_scenario_name(cls, value: object) -> str:
        text = str(value or "").strip()
        return text or "Base"

    def ui_assumption_overrides(self) -> dict[str, str]:
        """Return UI-controlled assumption overrides."""
        return {"portfolio_mode": self.portfolio_mode}

    def metadata_json(self, assumptions: Assumptions) -> str:
        """Return scenario metadata JSON for the current state."""
        return scenario_metadata_json(
            scenario_name=self.scenario_name,
            assumptions=assumptions,
            seed=self.seed,
        )
