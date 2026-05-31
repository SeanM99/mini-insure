"""Transparent deterministic pricing for synthetic motor policies."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from miniinsure.utils import MASTER_SEED

CLAIM_TYPES = ("attritional_damage", "bodily_injury", "theft_fire")

BASE_FREQUENCY = {
    "attritional_damage": 0.055,
    "bodily_injury": 0.0045,
    "theft_fire": 0.011,
}

BASE_SEVERITY = {
    "attritional_damage": 1800.0,
    "bodily_injury": 22000.0,
    "theft_fire": 5200.0,
}

FREQUENCY_TREND = {
    "attritional_damage": 1.010,
    "bodily_injury": 1.006,
    "theft_fire": 1.012,
}

SEVERITY_TREND = {
    "attritional_damage": 1.035,
    "bodily_injury": 1.030,
    "theft_fire": 1.040,
}

MARKET_CYCLE_FACTORS = {
    2021: 0.98,
    2022: 1.00,
    2023: 1.03,
    2024: 0.97,
    2025: 0.95,
    2026: 1.02,
}

RISK_LOAD = 0.04
EXPENSE_RATIO = 0.22
COMMISSION_RATIO = 0.08
TARGET_PROFIT_MARGIN = 0.06
COMPETITIVE_SIGMA = 0.08
MINIMUM_CHARGED_PREMIUM = 150.0

FREQUENCY_RELATIVITIES = {
    "driver_age_band": {
        "18-24": 1.55,
        "25-34": 1.18,
        "35-49": 0.95,
        "50-64": 0.88,
        "65+": 1.08,
    },
    "vehicle_segment": {
        "small": 0.88,
        "medium": 1.00,
        "premium": 1.18,
        "electric": 1.08,
        "van": 1.22,
    },
    "urbanicity": {
        "rural": 0.86,
        "suburban": 1.00,
        "urban": 1.18,
    },
    "mileage_band": {
        "low": 0.82,
        "medium": 1.00,
        "high": 1.24,
    },
    "prior_claims_band": {
        "0": 0.82,
        "1": 1.20,
        "2+": 1.70,
    },
    "bonus_malus_class": {
        "low": 0.80,
        "medium": 1.00,
        "high": 1.34,
    },
    "coverage_type": {
        "tpl": 0.82,
        "partial_casco": 1.00,
        "comprehensive": 1.16,
    },
    "customer_type": {
        "retail": 1.00,
        "small_commercial": 1.16,
    },
    "country_group": {
        "Netherlands": 1.00,
        "Neighbouring EU": 1.04,
        "Nordics": 0.92,
        "Other EEA": 1.08,
    },
}

SEVERITY_RELATIVITIES = {
    "driver_age_band": {
        "18-24": 1.10,
        "25-34": 1.04,
        "35-49": 1.00,
        "50-64": 0.98,
        "65+": 1.05,
    },
    "vehicle_segment": {
        "small": 0.82,
        "medium": 1.00,
        "premium": 1.45,
        "electric": 1.32,
        "van": 1.14,
    },
    "coverage_type": {
        "tpl": 0.90,
        "partial_casco": 1.00,
        "comprehensive": 1.22,
    },
    "deductible_band": {
        "none": 1.08,
        "eur250": 1.00,
        "eur500": 0.94,
        "eur1000": 0.88,
    },
    "country_group": {
        "Netherlands": 1.00,
        "Neighbouring EU": 1.03,
        "Nordics": 1.10,
        "Other EEA": 1.06,
    },
}


def price_policies(
    policies: pd.DataFrame,
    *,
    seed: int = MASTER_SEED,
    competitive_factors: Iterable[float] | float | None = None,
) -> pd.DataFrame:
    """Return policies with transparent technical and charged premium columns."""
    priced = policies.copy()
    if priced.empty:
        return priced

    exposure = _series_or_default(priced, "earned_exposure", 1.0).astype(float)
    underwriting_year = priced["underwriting_year"].astype(int)
    year_offset = underwriting_year - 2021

    frequency_rel = _combined_relativity(priced, FREQUENCY_RELATIVITIES)
    severity_rel = _combined_relativity(priced, SEVERITY_RELATIVITIES)

    loss_cost = pd.Series(0.0, index=priced.index)
    for claim_type in CLAIM_TYPES:
        expected_frequency = (
            exposure
            * BASE_FREQUENCY[claim_type]
            * frequency_rel
            * np.power(FREQUENCY_TREND[claim_type], year_offset)
        )
        expected_severity = (
            BASE_SEVERITY[claim_type]
            * severity_rel
            * np.power(SEVERITY_TREND[claim_type], year_offset)
        )
        priced[f"expected_frequency_{claim_type}"] = expected_frequency
        priced[f"expected_severity_{claim_type}"] = expected_severity
        priced[f"loss_cost_{claim_type}"] = expected_frequency * expected_severity
        loss_cost = loss_cost + priced[f"loss_cost_{claim_type}"]

    priced["loss_cost"] = loss_cost
    pricing_denominator = 1.0 - EXPENSE_RATIO - COMMISSION_RATIO - TARGET_PROFIT_MARGIN
    priced["technical_premium"] = priced["loss_cost"] * (1.0 + RISK_LOAD) / pricing_denominator

    if "market_cycle_factor" in priced.columns:
        market_factor = priced["market_cycle_factor"].astype(float)
    else:
        market_factor = underwriting_year.map(MARKET_CYCLE_FACTORS).astype(float)

    competitive_factor = _competitive_factors(len(priced), seed, competitive_factors)
    priced["competitive_factor"] = competitive_factor
    raw_charged = priced["technical_premium"] * market_factor * priced["competitive_factor"]
    priced["charged_premium"] = round_to_nearest_eur_5(
        np.maximum(raw_charged, MINIMUM_CHARGED_PREMIUM)
    )
    written_exposure = _series_or_default(priced, "written_exposure", 1.0).astype(float)
    earned_exposure = _series_or_default(priced, "earned_exposure", 1.0).astype(float)
    priced["written_premium"] = priced["charged_premium"] * written_exposure
    priced["earned_premium"] = priced["charged_premium"] * earned_exposure
    return priced


def round_to_nearest_eur_5(values: pd.Series | np.ndarray | float) -> pd.Series | float:
    """Round premiums to the nearest EUR 5 using half-up behavior."""
    rounded = np.floor(np.asarray(values, dtype=float) / 5.0 + 0.5) * 5.0
    if np.isscalar(values):
        return float(rounded)
    return pd.Series(rounded, index=getattr(values, "index", None))


def segment_profitability(
    policies: pd.DataFrame,
    *,
    segment_column: str = "homogeneous_risk_group",
) -> pd.DataFrame:
    """Summarize premium adequacy by segment."""
    grouped = policies.groupby(segment_column, dropna=False).agg(
        policy_count=("policy_id", "count"),
        earned_exposure=("earned_exposure", "sum"),
        loss_cost=("loss_cost", "sum"),
        technical_premium=("technical_premium", "sum"),
        charged_premium=("charged_premium", "sum"),
        earned_premium=("earned_premium", "sum"),
    )
    grouped["rate_adequacy"] = grouped["charged_premium"] / grouped["technical_premium"]
    grouped["expected_loss_ratio"] = grouped["loss_cost"] / grouped["charged_premium"]
    return grouped.reset_index().sort_values("earned_premium", ascending=False)


def _competitive_factors(
    size: int,
    seed: int,
    competitive_factors: Iterable[float] | float | None,
) -> np.ndarray:
    if competitive_factors is not None:
        if np.isscalar(competitive_factors):
            return np.repeat(float(competitive_factors), size)
        factors = np.asarray(list(competitive_factors), dtype=float)
        if len(factors) != size:
            raise ValueError("competitive_factors must match the number of policies")
        return np.clip(factors, 0.75, 1.30)

    rng = np.random.default_rng(seed)
    mean = -0.5 * COMPETITIVE_SIGMA**2
    return np.clip(
        rng.lognormal(mean=mean, sigma=COMPETITIVE_SIGMA, size=size),
        0.75,
        1.30,
    )


def _combined_relativity(
    policies: pd.DataFrame,
    relativity_maps: dict[str, dict[str, float]],
) -> pd.Series:
    relativity = pd.Series(1.0, index=policies.index)
    for column, values in relativity_maps.items():
        if column not in policies.columns:
            continue
        relativity = relativity * policies[column].map(values).fillna(1.0).astype(float)
    return relativity


def _series_or_default(df: pd.DataFrame, column: str, value: float) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(value, index=df.index)
