"""Named risk drivers for the Gaussian copula dependency model."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskDriver:
    """One dependency-model driver."""

    code: str
    name: str


RISK_DRIVERS: tuple[RiskDriver, ...] = (
    RiskDriver("PF", "premium frequency"),
    RiskDriver("PS", "premium severity"),
    RiskDriver("RD", "reserve deterioration"),
    RiskDriver("CI", "claims inflation"),
    RiskDriver("CAT", "catastrophe"),
    RiskDriver("EQ", "equity return"),
    RiskDriver("IR", "interest-rate change"),
    RiskDriver("SP", "credit spread"),
    RiskDriver("EX", "expense inflation"),
    RiskDriver("LV", "lapse/volume"),
    RiskDriver("RDf", "reinsurance default"),
)

DRIVER_CODES: tuple[str, ...] = tuple(driver.code for driver in RISK_DRIVERS)


def risk_driver_frame() -> pd.DataFrame:
    """Return risk-driver metadata as a table."""
    return pd.DataFrame([{"driver": driver.code, "name": driver.name} for driver in RISK_DRIVERS])
