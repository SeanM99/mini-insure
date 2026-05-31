"""Deterministic synthetic policy generation for MiniInsure."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from miniinsure.pricing import MARKET_CYCLE_FACTORS, price_policies
from miniinsure.utils import MASTER_SEED

HISTORICAL_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025, 2026)

FULL_ANNUAL_POLICY_COUNTS = {
    2021: 100_000,
    2022: 102_000,
    2023: 105_000,
    2024: 108_000,
    2025: 110_000,
    2026: 112_000,
}

INTERACTIVE_POLICY_COUNTS = {
    "small": 10_000,
    "medium": 50_000,
    "full": 100_000,
}

REQUIRED_POLICY_COLUMNS = (
    "policy_id",
    "underwriting_year",
    "accident_year",
    "inception_date",
    "expiry_date",
    "written_exposure",
    "earned_exposure",
    "country_group",
    "solvency_ii_lob",
    "homogeneous_risk_group",
    "coverage_type",
    "distribution_channel",
    "customer_type",
    "driver_age_band",
    "vehicle_segment",
    "mileage_band",
    "prior_claims_band",
    "bonus_malus_class",
    "deductible_band",
    "urbanicity",
    "technical_premium",
    "charged_premium",
    "written_premium",
    "earned_premium",
    "lapse_probability",
    "renewal_probability",
)

BASE_DISTRIBUTIONS: dict[str, dict[str, float]] = {
    "country_group": {
        "Netherlands": 0.82,
        "Neighbouring EU": 0.08,
        "Nordics": 0.04,
        "Other EEA": 0.06,
    },
    "driver_age_band": {
        "18-24": 0.09,
        "25-34": 0.22,
        "35-49": 0.31,
        "50-64": 0.25,
        "65+": 0.13,
    },
    "vehicle_segment": {
        "small": 0.30,
        "medium": 0.36,
        "premium": 0.12,
        "electric": 0.10,
        "van": 0.12,
    },
    "urbanicity": {
        "rural": 0.24,
        "suburban": 0.46,
        "urban": 0.30,
    },
    "customer_type": {
        "retail": 0.86,
        "small_commercial": 0.14,
    },
    "coverage_type": {
        "tpl": 0.30,
        "partial_casco": 0.35,
        "comprehensive": 0.35,
    },
    "distribution_channel": {
        "broker": 0.34,
        "direct": 0.32,
        "aggregator": 0.22,
        "affinity": 0.12,
    },
    "mileage_band": {
        "low": 0.27,
        "medium": 0.53,
        "high": 0.20,
    },
    "prior_claims_band": {
        "0": 0.70,
        "1": 0.22,
        "2+": 0.08,
    },
    "bonus_malus_class": {
        "low": 0.20,
        "medium": 0.60,
        "high": 0.20,
    },
    "deductible_band": {
        "none": 0.20,
        "eur250": 0.50,
        "eur500": 0.25,
        "eur1000": 0.05,
    },
}


def generate_policy_data(
    *,
    portfolio_mode: str = "small",
    seed: int = MASTER_SEED,
    years: Iterable[int] = HISTORICAL_YEARS,
    policies_per_year: int | None = None,
    include_pricing: bool = True,
) -> pd.DataFrame:
    """Generate deterministic synthetic policies for the requested years."""
    if portfolio_mode not in INTERACTIVE_POLICY_COUNTS:
        raise ValueError("portfolio_mode must be one of small, medium, full")

    rng = np.random.default_rng(seed)
    frames = [
        _generate_year_policies(
            rng=rng,
            year=int(year),
            count=policies_per_year or INTERACTIVE_POLICY_COUNTS[portfolio_mode],
            portfolio_mode=portfolio_mode,
        )
        for year in years
    ]
    policies = pd.concat(frames, ignore_index=True)
    if include_pricing:
        policies = price_policies(policies, seed=seed)
    return _ordered_policy_columns(policies)


def conditional_distribution(field: str, context: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Return the distribution for one field after applying conditional rules."""
    context = context or {}
    if field not in BASE_DISTRIBUTIONS:
        raise ValueError(f"unknown distribution field: {field}")

    distribution = dict(BASE_DISTRIBUTIONS[field])
    if field == "distribution_channel" and context.get("driver_age_band") == "18-24":
        distribution["aggregator"] = 0.45
        distribution["affinity"] = 0.05
        return _normalize(distribution)

    if field == "coverage_type" and context.get("vehicle_segment") in {"premium", "electric"}:
        return _set_probability(distribution, "comprehensive", 0.85)

    if field == "customer_type" and context.get("vehicle_segment") == "van":
        return _set_probability(distribution, "small_commercial", 0.45)

    if field == "bonus_malus_class" and context.get("prior_claims_band") == "2+":
        return _set_probability(distribution, "high", 0.65)

    if field == "mileage_band" and context.get("urbanicity") == "urban":
        return _set_probability(distribution, "high", 0.28)

    if field == "vehicle_segment" and context.get("country_group") == "Nordics":
        return _set_probability(distribution, "electric", 0.15)

    return _normalize(distribution)


def _generate_year_policies(
    *,
    rng: np.random.Generator,
    year: int,
    count: int,
    portfolio_mode: str,
) -> pd.DataFrame:
    country_group = _sample_categories(rng, count, conditional_distribution("country_group"))
    driver_age = _sample_categories(rng, count, conditional_distribution("driver_age_band"))
    vehicle_segment = _sample_conditional(
        rng,
        "vehicle_segment",
        [{"country_group": value} for value in country_group],
    )
    urbanicity = _sample_categories(rng, count, conditional_distribution("urbanicity"))
    customer_type = _sample_conditional(
        rng,
        "customer_type",
        [{"vehicle_segment": value} for value in vehicle_segment],
    )
    coverage_type = _sample_conditional(
        rng,
        "coverage_type",
        [{"vehicle_segment": value} for value in vehicle_segment],
    )
    channel = _sample_conditional(
        rng,
        "distribution_channel",
        [{"driver_age_band": value} for value in driver_age],
    )
    mileage = _sample_conditional(
        rng,
        "mileage_band",
        [{"urbanicity": value} for value in urbanicity],
    )
    prior_claims = _sample_categories(rng, count, conditional_distribution("prior_claims_band"))
    bonus_malus = _sample_conditional(
        rng,
        "bonus_malus_class",
        [{"prior_claims_band": value} for value in prior_claims],
    )
    deductible = _sample_categories(rng, count, conditional_distribution("deductible_band"))

    sequence = np.arange(1, count + 1)
    inception = pd.Timestamp(year=year, month=1, day=1)
    expiry = pd.Timestamp(year=year, month=12, day=31)
    policies = pd.DataFrame(
        {
            "policy_id": [f"POL{year}{number:06d}" for number in sequence],
            "underwriting_year": year,
            "accident_year": year,
            "inception_date": inception,
            "expiry_date": expiry,
            "written_exposure": 1.0,
            "earned_exposure": 1.0,
            "country_group": country_group,
            "coverage_type": coverage_type,
            "distribution_channel": channel,
            "customer_type": customer_type,
            "driver_age_band": driver_age,
            "vehicle_segment": vehicle_segment,
            "mileage_band": mileage,
            "prior_claims_band": prior_claims,
            "bonus_malus_class": bonus_malus,
            "deductible_band": deductible,
            "urbanicity": urbanicity,
            "portfolio_mode": portfolio_mode,
            "product": "Motor insurance",
            "exposure": 1.0,
            "sum_insured": _sum_insured(vehicle_segment),
            "market_cycle_factor": MARKET_CYCLE_FACTORS[year],
        }
    )
    policies["solvency_ii_lob"] = np.where(
        policies["coverage_type"] == "tpl",
        "Motor vehicle liability",
        "Other motor insurance",
    )
    policies["homogeneous_risk_group"] = (
        policies["coverage_type"]
        + "|"
        + policies["customer_type"]
        + "|"
        + policies["vehicle_segment"]
    )
    policies["lapse_probability"] = _lapse_probability(policies)
    policies["renewal_probability"] = 1.0 - policies["lapse_probability"]
    return policies


def _ordered_policy_columns(policies: pd.DataFrame) -> pd.DataFrame:
    ordered = [column for column in REQUIRED_POLICY_COLUMNS if column in policies.columns]
    remainder = [column for column in policies.columns if column not in ordered]
    return policies[ordered + remainder]


def _sample_conditional(
    rng: np.random.Generator,
    field: str,
    contexts: Iterable[Mapping[str, Any]],
) -> np.ndarray:
    return np.array(
        [
            _sample_one(rng, conditional_distribution(field, context))
            for context in contexts
        ],
        dtype=object,
    )


def _sample_categories(
    rng: np.random.Generator,
    count: int,
    distribution: Mapping[str, float],
) -> np.ndarray:
    categories = list(distribution)
    probabilities = np.array(list(distribution.values()), dtype=float)
    return rng.choice(categories, size=count, p=probabilities)


def _sample_one(rng: np.random.Generator, distribution: Mapping[str, float]) -> str:
    return str(_sample_categories(rng, 1, distribution)[0])


def _normalize(distribution: Mapping[str, float]) -> dict[str, float]:
    total = float(sum(distribution.values()))
    if total <= 0:
        raise ValueError("distribution probabilities must have positive total")
    return {key: value / total for key, value in distribution.items()}


def _set_probability(
    distribution: Mapping[str, float],
    target: str,
    target_probability: float,
) -> dict[str, float]:
    if target not in distribution:
        raise ValueError(f"target is not in distribution: {target}")
    other_total = float(sum(value for key, value in distribution.items() if key != target))
    remaining = 1.0 - target_probability
    adjusted = {
        key: (target_probability if key == target else value / other_total * remaining)
        for key, value in distribution.items()
    }
    return _normalize(adjusted)


def _sum_insured(vehicle_segment: pd.Series | np.ndarray) -> np.ndarray:
    values = pd.Series(vehicle_segment).map(
        {
            "small": 18_000,
            "medium": 28_000,
            "premium": 55_000,
            "electric": 48_000,
            "van": 35_000,
        }
    )
    return values.to_numpy(dtype=float)


def _lapse_probability(policies: pd.DataFrame) -> pd.Series:
    base = pd.Series(0.09, index=policies.index)
    base = base + np.where(policies["distribution_channel"] == "aggregator", 0.045, 0.0)
    base = base + np.where(policies["prior_claims_band"] == "2+", 0.020, 0.0)
    base = base - np.where(policies["bonus_malus_class"] == "low", 0.020, 0.0)
    return pd.Series(np.clip(base, 0.02, 0.30), index=policies.index)
