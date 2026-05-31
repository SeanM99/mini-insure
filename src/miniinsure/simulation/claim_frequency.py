"""Deterministic claim frequency simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd

CLAIM_TYPES = (
    "liability_property_damage",
    "own_damage_attritional",
    "theft_fire",
    "attritional_bi",
    "large_bi",
)

COVERAGE_BASE_FREQUENCY = {
    "tpl": 0.048,
    "partial_casco": 0.082,
    "comprehensive": 0.118,
}

CLAIM_TYPE_ALLOCATION = {
    "tpl": {
        "liability_property_damage": 0.78,
        "own_damage_attritional": 0.00,
        "theft_fire": 0.00,
        "attritional_bi": 0.20,
        "large_bi": 0.02,
    },
    "partial_casco": {
        "liability_property_damage": 0.38,
        "own_damage_attritional": 0.37,
        "theft_fire": 0.14,
        "attritional_bi": 0.10,
        "large_bi": 0.01,
    },
    "comprehensive": {
        "liability_property_damage": 0.30,
        "own_damage_attritional": 0.47,
        "theft_fire": 0.12,
        "attritional_bi": 0.10,
        "large_bi": 0.01,
    },
}

DISPERSION = {
    "liability_property_damage": 1.8,
    "own_damage_attritional": 1.6,
    "theft_fire": 1.2,
    "attritional_bi": 1.4,
    "large_bi": 0.9,
}

FREQUENCY_RELATIVITIES = {
    "driver_age_band": {
        "18-24": 1.45,
        "25-34": 1.12,
        "35-49": 0.96,
        "50-64": 0.88,
        "65+": 1.08,
    },
    "vehicle_segment": {
        "small": 0.90,
        "medium": 1.00,
        "premium": 1.10,
        "electric": 1.06,
        "van": 1.18,
    },
    "urbanicity": {
        "rural": 0.86,
        "suburban": 1.00,
        "urban": 1.18,
    },
    "mileage_band": {
        "low": 0.84,
        "medium": 1.00,
        "high": 1.22,
    },
    "prior_claims_band": {
        "0": 0.82,
        "1": 1.24,
        "2+": 1.72,
    },
    "bonus_malus_class": {
        "low": 0.80,
        "medium": 1.00,
        "high": 1.32,
    },
}

ANNUAL_FREQUENCY_TREND = {
    2021: 0.96,
    2022: 0.98,
    2023: 1.00,
    2024: 1.02,
    2025: 1.04,
    2026: 1.06,
}


def expected_claim_frequency_by_type(policies: pd.DataFrame) -> pd.DataFrame:
    """Return expected annual frequency by policy and claim type."""
    relativity = _combined_relativity(policies)
    exposure = policies["earned_exposure"].astype(float)
    year_factor = policies["accident_year"].map(ANNUAL_FREQUENCY_TREND).fillna(1.0).astype(float)
    expected = pd.DataFrame(index=policies.index)
    for claim_type in CLAIM_TYPES:
        allocation = policies["coverage_type"].map(
            {
                coverage: values[claim_type]
                for coverage, values in CLAIM_TYPE_ALLOCATION.items()
            }
        ).fillna(0.0)
        base = policies["coverage_type"].map(COVERAGE_BASE_FREQUENCY).fillna(0.0)
        expected[claim_type] = exposure * base * allocation * relativity * year_factor
    return expected


def simulate_claim_frequency(
    policies: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Simulate claim counts using Gamma-Poisson negative binomial representation."""
    expected = expected_claim_frequency_by_type(policies)
    rows: list[pd.DataFrame] = []
    for claim_type in CLAIM_TYPES:
        mean = expected[claim_type].to_numpy(dtype=float)
        dispersion = DISPERSION[claim_type]
        gamma_lambda = rng.gamma(shape=dispersion, scale=np.divide(mean, dispersion))
        claim_counts = rng.poisson(gamma_lambda)
        repeated_index = np.repeat(policies.index.to_numpy(), claim_counts)
        if len(repeated_index) == 0:
            continue
        claim_rows = policies.loc[repeated_index].copy()
        claim_rows["claim_type"] = claim_type
        rows.append(claim_rows)

    if not rows:
        return _empty_claim_stubs()

    claims = pd.concat(rows, ignore_index=True)
    claims = claims.sample(frac=1.0, random_state=int(rng.integers(0, 2**32 - 1))).reset_index(drop=True)
    claims["claim_sequence"] = np.arange(1, len(claims) + 1)
    claims["claim_id"] = claims.apply(
        lambda row: f"CLM{int(row.accident_year)}{int(row.claim_sequence):07d}",
        axis=1,
    )
    if "earned_premium" not in claims.columns:
        claims["earned_premium"] = 0.0
    accident_offsets = rng.integers(0, 365, size=len(claims))
    claims["accident_date"] = pd.to_datetime(claims["accident_year"].astype(str) + "-01-01") + pd.to_timedelta(
        accident_offsets,
        unit="D",
    )
    claims["catastrophe_event_id"] = pd.NA
    return claims[
        [
            "claim_id",
            "policy_id",
            "underwriting_year",
            "accident_year",
            "accident_date",
            "claim_type",
            "coverage_type",
            "country_group",
            "solvency_ii_lob",
            "homogeneous_risk_group",
            "driver_age_band",
            "vehicle_segment",
            "mileage_band",
            "prior_claims_band",
            "bonus_malus_class",
            "deductible_band",
            "urbanicity",
            "sum_insured",
            "earned_premium",
            "catastrophe_event_id",
        ]
    ]


def _combined_relativity(policies: pd.DataFrame) -> pd.Series:
    relativity = pd.Series(1.0, index=policies.index)
    for column, mapping in FREQUENCY_RELATIVITIES.items():
        relativity = relativity * policies[column].map(mapping).fillna(1.0).astype(float)
    return relativity


def _empty_claim_stubs() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "claim_id",
            "policy_id",
            "underwriting_year",
            "accident_year",
            "accident_date",
            "claim_type",
            "coverage_type",
            "country_group",
            "solvency_ii_lob",
            "homogeneous_risk_group",
            "driver_age_band",
            "vehicle_segment",
            "mileage_band",
            "prior_claims_band",
            "bonus_malus_class",
            "deductible_band",
            "urbanicity",
            "sum_insured",
            "earned_premium",
            "catastrophe_event_id",
        ]
    )
