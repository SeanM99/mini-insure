"""Deterministic catastrophe event and claim simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd

EVENT_LAMBDA_BY_YEAR = 0.45
EVENT_SEVERITY_MEAN = 3_000_000.0
EVENT_SEVERITY_SIGMA = 0.85

COUNTRY_AFFECTED_MULTIPLIER = {
    "Netherlands": 1.00,
    "Neighbouring EU": 0.65,
    "Nordics": 0.45,
    "Other EEA": 0.55,
}

URBANICITY_AFFECTED_MULTIPLIER = {
    "rural": 0.65,
    "suburban": 1.00,
    "urban": 1.35,
}

VEHICLE_AFFECTED_MULTIPLIER = {
    "small": 0.90,
    "medium": 1.00,
    "premium": 1.12,
    "electric": 1.20,
    "van": 1.08,
}


def simulate_catastrophe_events_and_claims(
    policies: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate catastrophe events and mapped HRG04 claims."""
    event_rows: list[dict[str, object]] = []
    claim_rows: list[pd.DataFrame] = []
    for year in sorted(policies["accident_year"].unique()):
        year_policies = policies.loc[policies["accident_year"] == year]
        event_count = int(rng.poisson(EVENT_LAMBDA_BY_YEAR))
        for event_number in range(1, event_count + 1):
            event_id = f"CAT{int(year)}{event_number:03d}"
            event_date = pd.Timestamp(year=int(year), month=1, day=1) + pd.to_timedelta(
                int(rng.integers(0, 365)),
                unit="D",
            )
            sigma = EVENT_SEVERITY_SIGMA
            mu = np.log(EVENT_SEVERITY_MEAN) - 0.5 * sigma**2
            gross_loss = float(rng.lognormal(mean=mu, sigma=sigma))
            affected_probability = _affected_probability(year_policies)
            affected_mask = rng.random(len(year_policies)) < affected_probability.to_numpy(dtype=float)
            affected = year_policies.loc[affected_mask].copy()
            if affected.empty:
                continue
            event_rows.append(
                {
                    "event_id": event_id,
                    "event_date": event_date,
                    "event_type": "convective_storm",
                    "gross_loss": gross_loss,
                    "insured_loss": gross_loss * 0.82,
                    "affected_policy_count": len(affected),
                }
            )
            shares = rng.dirichlet(np.repeat(1.8, len(affected)))
            affected["claim_id"] = [
                f"CATCLM{int(year)}{event_number:03d}{idx:06d}"
                for idx in range(1, len(affected) + 1)
            ]
            affected["accident_date"] = event_date
            affected["claim_type"] = "catastrophe_allocated"
            affected["homogeneous_risk_group"] = "HRG04"
            affected["catastrophe_event_id"] = event_id
            affected["preset_gross_ultimate"] = gross_loss * shares
            claim_rows.append(affected)

    events = pd.DataFrame(event_rows)
    if not claim_rows:
        return events, _empty_catastrophe_claims()
    claims = pd.concat(claim_rows, ignore_index=True)
    return events, claims[
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
            "preset_gross_ultimate",
        ]
    ]


def _affected_probability(policies: pd.DataFrame) -> pd.Series:
    probability = pd.Series(0.0018, index=policies.index)
    probability = probability * policies["country_group"].map(COUNTRY_AFFECTED_MULTIPLIER).fillna(1.0)
    probability = probability * policies["urbanicity"].map(URBANICITY_AFFECTED_MULTIPLIER).fillna(1.0)
    probability = probability * policies["vehicle_segment"].map(VEHICLE_AFFECTED_MULTIPLIER).fillna(1.0)
    return probability.clip(upper=0.02)


def _empty_catastrophe_claims() -> pd.DataFrame:
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
            "preset_gross_ultimate",
        ]
    )
