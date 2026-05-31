"""Claim severity simulation and deductible/limit application."""

from __future__ import annotations

import numpy as np
import pandas as pd

from miniinsure.simulation.large_losses import expected_large_bi_gross_mean, simulate_large_bi_gross

GAMMA_SEVERITY = {
    "liability_property_damage": {"mean": 2_600.0, "shape": 2.2},
    "own_damage_attritional": {"mean": 1_900.0, "shape": 2.6},
}

LOGNORMAL_SEVERITY = {
    "theft_fire": {"mean": 5_800.0, "sigma": 0.72},
    "attritional_bi": {"mean": 18_500.0, "sigma": 0.82},
    "catastrophe_allocated": {"mean": 9_000.0, "sigma": 0.95},
}

SEVERITY_RELATIVITIES = {
    "vehicle_segment": {
        "small": 0.82,
        "medium": 1.00,
        "premium": 1.45,
        "electric": 1.30,
        "van": 1.16,
    },
    "coverage_type": {
        "tpl": 0.92,
        "partial_casco": 1.00,
        "comprehensive": 1.20,
    },
    "country_group": {
        "Netherlands": 1.00,
        "Neighbouring EU": 1.03,
        "Nordics": 1.08,
        "Other EEA": 1.06,
    },
}

DEDUCTIBLE_AMOUNTS = {
    "none": 0.0,
    "eur250": 250.0,
    "eur500": 500.0,
    "eur1000": 1_000.0,
}


def simulate_claim_severity(
    claim_stubs: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate gross and insured severities, returning observed-safe claims and truth."""
    if claim_stubs.empty:
        return claim_stubs.copy(), _empty_truth()

    claims = claim_stubs.copy().reset_index(drop=True)
    gross = np.zeros(len(claims), dtype=float)
    for claim_type in claims["claim_type"].unique():
        mask = claims["claim_type"] == claim_type
        gross[mask.to_numpy()] = _simulate_gross_by_type(claim_type, int(mask.sum()), rng)

    if "preset_gross_ultimate" in claims.columns:
        preset = pd.to_numeric(claims["preset_gross_ultimate"], errors="coerce")
        preset_mask = preset.notna()
        gross[preset_mask.to_numpy()] = preset[preset_mask].to_numpy(dtype=float)

    relativities = _severity_relativity(claims)
    gross = gross * relativities.to_numpy(dtype=float)
    deductible = claims["deductible_band"].map(DEDUCTIBLE_AMOUNTS).fillna(0.0).astype(float)
    policy_limit = _policy_limit(claims)
    insured = apply_deductible_and_limit(gross, deductible.to_numpy(), policy_limit.to_numpy())

    claims["zero_insured_flag"] = insured <= 0
    claims["large_loss_flag"] = claims["claim_type"] == "large_bi"
    claims["reopened_flag"] = False

    truth = pd.DataFrame(
        {
            "truth_record_id": [f"TRUTH{i:09d}" for i in range(1, len(claims) + 1)],
            "claim_id": claims["claim_id"],
            "policy_id": claims["policy_id"],
            "claim_type": claims["claim_type"],
            "gross_ultimate_amount": gross,
            "deductible_amount": deductible,
            "policy_limit_amount": policy_limit,
            "insured_ultimate_amount": insured,
            "large_loss_flag": claims["large_loss_flag"],
            "catastrophe_event_id": claims["catastrophe_event_id"],
        }
    )
    return claims.drop(columns=["preset_gross_ultimate"], errors="ignore"), truth


def apply_deductible_and_limit(
    gross_amount: np.ndarray | pd.Series | float,
    deductible_amount: np.ndarray | pd.Series | float,
    policy_limit_amount: np.ndarray | pd.Series | float,
) -> np.ndarray:
    """Apply deductible first, then cap at policy limit."""
    net_of_deductible = np.maximum(np.asarray(gross_amount, dtype=float) - np.asarray(deductible_amount, dtype=float), 0.0)
    return np.minimum(net_of_deductible, np.asarray(policy_limit_amount, dtype=float))


def expected_gross_severity_mean(claim_type: str) -> float:
    """Return theoretical gross severity mean before relativities and coverage terms."""
    if claim_type in GAMMA_SEVERITY:
        return GAMMA_SEVERITY[claim_type]["mean"]
    if claim_type in LOGNORMAL_SEVERITY:
        return LOGNORMAL_SEVERITY[claim_type]["mean"]
    if claim_type == "large_bi":
        return expected_large_bi_gross_mean()
    raise ValueError(f"unknown claim_type: {claim_type}")


def _simulate_gross_by_type(
    claim_type: str,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if claim_type in GAMMA_SEVERITY:
        params = GAMMA_SEVERITY[claim_type]
        return rng.gamma(shape=params["shape"], scale=params["mean"] / params["shape"], size=size)
    if claim_type in LOGNORMAL_SEVERITY:
        params = LOGNORMAL_SEVERITY[claim_type]
        sigma = params["sigma"]
        mu = np.log(params["mean"]) - 0.5 * sigma**2
        return rng.lognormal(mean=mu, sigma=sigma, size=size)
    if claim_type == "large_bi":
        return simulate_large_bi_gross(rng, size)
    raise ValueError(f"unknown claim_type: {claim_type}")


def _severity_relativity(claims: pd.DataFrame) -> pd.Series:
    relativity = pd.Series(1.0, index=claims.index)
    for column, mapping in SEVERITY_RELATIVITIES.items():
        relativity = relativity * claims[column].map(mapping).fillna(1.0).astype(float)
    return relativity


def _policy_limit(claims: pd.DataFrame) -> pd.Series:
    base_limit = claims["sum_insured"].astype(float)
    bi_multiplier = np.where(claims["claim_type"].isin(["attritional_bi", "large_bi"]), 8.0, 1.0)
    catastrophe_multiplier = np.where(claims["claim_type"] == "catastrophe_allocated", 1.5, 1.0)
    return pd.Series(base_limit * bi_multiplier * catastrophe_multiplier, index=claims.index)


def _empty_truth() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "truth_record_id",
            "claim_id",
            "policy_id",
            "claim_type",
            "gross_ultimate_amount",
            "deductible_amount",
            "policy_limit_amount",
            "insured_ultimate_amount",
            "large_loss_flag",
            "catastrophe_event_id",
        ]
    )
