"""Quick-mode one-year reserve risk simulation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.reserving.deterministic_methods import TAIL_FACTORS, method_weights
from miniinsure.reserving.stochastic_methods import (
    bootstrap_chain_ladder_one_year,
    lognormal_amounts_from_mean_cv,
    negative_binomial_counts,
)
from miniinsure.reserving.triangles import DEFAULT_GROUP_COLUMNS, triangle_to_matrix
from miniinsure.utils import MASTER_SEED

QUICK_MODE_SIMULATIONS = 1_000
DEFAULT_RESERVE_RISK_SEED = MASTER_SEED

ATTRITIONAL_CLAIM_TYPES = {
    "liability_property_damage",
    "own_damage_attritional",
    "theft_fire",
    "attritional",
}
BODILY_INJURY_CLAIM_TYPES = {"attritional_bi"}
LARGE_BI_CLAIM_TYPES = {"large_bi"}
CATASTROPHE_CLAIM_TYPES = {"catastrophe_allocated"}


@dataclass(frozen=True)
class ReserveRiskResult:
    """One-year reserve risk simulation output."""

    simulations: pd.DataFrame
    summary: pd.DataFrame
    component_summary: pd.DataFrame
    settings: dict[str, int | str | bool]


def simulate_reserve_risk_quick(
    paid_triangle: pd.DataFrame,
    incurred_triangle: pd.DataFrame,
    policies: pd.DataFrame,
    claims: pd.DataFrame,
    opening_reserving_results: pd.DataFrame,
    *,
    n_simulations: int = QUICK_MODE_SIMULATIONS,
    seed: int = DEFAULT_RESERVE_RISK_SEED,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> ReserveRiskResult:
    """Simulate quick-mode one-year reserve risk with deterministic seed control."""
    if n_simulations <= 0:
        raise ValueError("n_simulations must be positive")

    rng = np.random.default_rng(seed)
    opening = opening_reserving_results.copy()
    if opening.empty:
        simulations = _empty_simulations()
        summary = reserve_risk_summary(simulations)
        return ReserveRiskResult(
            simulations=simulations,
            summary=summary,
            component_summary=pd.DataFrame(),
            settings=_settings(n_simulations, seed),
        )

    opening_best_estimate = float(opening["selected_reserve"].clip(lower=0.0).sum())
    totals = _zero_component_arrays(n_simulations)
    component_frames: list[pd.DataFrame] = []

    attritional = _simulate_attritional_component(
        paid_triangle,
        opening,
        n_simulations=n_simulations,
        rng=rng,
        group_columns=group_columns,
    )
    _add_component(totals, attritional)
    component_frames.append(_summarise_component("attritional_claims", attritional))

    bodily_injury = _simulate_bodily_injury_component(opening, n_simulations=n_simulations, rng=rng)
    _add_component(totals, bodily_injury)
    component_frames.append(_summarise_component("bodily_injury", bodily_injury))

    large_bi = _simulate_lognormal_development_component(
        opening,
        claim_types=LARGE_BI_CLAIM_TYPES,
        component_name="large_bi",
        n_simulations=n_simulations,
        rng=rng,
        ultimate_cv=0.30,
        payment_share=0.18,
        reestimate_cv=0.12,
    )
    _add_component(totals, large_bi)
    component_frames.append(_summarise_component("large_bi", large_bi))

    catastrophe = _simulate_lognormal_development_component(
        opening,
        claim_types=CATASTROPHE_CLAIM_TYPES,
        component_name="catastrophe",
        n_simulations=n_simulations,
        rng=rng,
        ultimate_cv=0.40,
        payment_share=0.35,
        reestimate_cv=0.18,
    )
    _add_component(totals, catastrophe)
    component_frames.append(_summarise_component("catastrophe", catastrophe))

    simulations = pd.DataFrame(
        {
            "simulation": np.arange(1, n_simulations + 1),
            "opening_best_estimate": opening_best_estimate,
            "next_12_month_payments": totals["next_12_month_payments"],
            "closing_best_estimate": totals["closing_best_estimate"],
            "reserve_loss": (
                totals["next_12_month_payments"]
                + totals["closing_best_estimate"]
                - opening_best_estimate
            ),
            "simulated_direct_remaining_unpaid_diagnostic": totals[
                "simulated_direct_remaining_unpaid_diagnostic"
            ],
            "closing_best_estimate_basis": "re-estimated_from_simulated_one_year_observed_triangle",
            "closing_reestimated_from_observed_triangle": True,
        }
    )
    summary = reserve_risk_summary(simulations)
    component_summary = pd.concat(component_frames, ignore_index=True)
    return ReserveRiskResult(
        simulations=simulations,
        summary=summary,
        component_summary=component_summary,
        settings=_settings(n_simulations, seed),
    )


def reserve_risk_summary(simulations: pd.DataFrame) -> pd.DataFrame:
    """Return reserve risk output statistics."""
    if simulations.empty:
        return pd.DataFrame(
            [
                {
                    "mean": 0.0,
                    "standard_deviation": 0.0,
                    "var_95": 0.0,
                    "var_99": 0.0,
                    "var_995": 0.0,
                    "tvar_995": 0.0,
                    "probability_of_adverse_development": 0.0,
                    "expected_reserve_loss": 0.0,
                    "reserve_capital": 0.0,
                }
            ]
        )

    losses = simulations["reserve_loss"].to_numpy(dtype=float)
    var_95 = float(np.quantile(losses, 0.95))
    var_99 = float(np.quantile(losses, 0.99))
    var_995 = float(np.quantile(losses, 0.995))
    tail = losses[losses >= var_995]
    mean = float(np.mean(losses))
    return pd.DataFrame(
        [
            {
                "mean": mean,
                "standard_deviation": float(np.std(losses, ddof=1)) if len(losses) > 1 else 0.0,
                "var_95": var_95,
                "var_99": var_99,
                "var_995": var_995,
                "tvar_995": float(np.mean(tail)) if len(tail) else var_995,
                "probability_of_adverse_development": float(np.mean(losses > 0.0)),
                "expected_reserve_loss": mean,
                "reserve_capital": float(var_995 - mean),
            }
        ]
    )


def _simulate_attritional_component(
    paid_triangle: pd.DataFrame,
    opening: pd.DataFrame,
    *,
    n_simulations: int,
    rng: np.random.Generator,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    attritional_rows = opening.loc[opening["claim_type_basis"].isin(ATTRITIONAL_CLAIM_TYPES)]
    if attritional_rows.empty:
        return _component_frame(n_simulations)

    component = _component_frame(n_simulations)
    for lob, lob_rows in attritional_rows.groupby("solvency_ii_lob"):
        lob_triangle = _triangle_for_opening_rows(
            paid_triangle,
            lob_rows,
            group_columns=group_columns,
        )
        matrix = triangle_to_matrix(lob_triangle, "cumulative_paid")
        tail_factor = TAIL_FACTORS.get(str(lob), 1.01)
        tail_sigma = 0.03 if str(lob) == "Motor vehicle liability" else 0.01
        bootstrap = bootstrap_chain_ladder_one_year(
            matrix,
            n_simulations=n_simulations,
            rng=rng,
            tail_factor=tail_factor,
            tail_sigma=tail_sigma,
        )
        if bootstrap.empty:
            continue
        opening_attritional_reserve = float(lob_rows["selected_reserve"].clip(lower=0.0).sum())
        bootstrap_opening = float(bootstrap["opening_chain_ladder_reserve"].mean())
        scale = opening_attritional_reserve / bootstrap_opening if bootstrap_opening > 0 else 1.0
        component["next_12_month_payments"] += bootstrap["next_12_month_payments"].to_numpy(dtype=float) * scale
        component["closing_best_estimate"] += bootstrap["closing_reestimated_reserve"].to_numpy(dtype=float) * scale
        component["simulated_direct_remaining_unpaid_diagnostic"] += (
            bootstrap["simulated_direct_remaining_unpaid_diagnostic"].to_numpy(dtype=float) * scale
        )
    return component


def _simulate_bodily_injury_component(
    opening: pd.DataFrame,
    *,
    n_simulations: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = opening.loc[opening["claim_type_basis"].isin(BODILY_INJURY_CLAIM_TYPES)]
    component = _component_frame(n_simulations)
    if rows.empty:
        return component

    reserve = float(rows["selected_reserve"].clip(lower=0.0).sum())
    current_count = max(float(rows["claim_count"].sum()), 1.0)
    mean_ibnr_count = max(current_count * 0.12, 0.25)
    severity_mean = max(reserve / current_count, 1_000.0)
    counts = negative_binomial_counts(mean_ibnr_count, dispersion=1.4, size=n_simulations, rng=rng)
    severities = lognormal_amounts_from_mean_cv(severity_mean, 0.65, size=n_simulations, rng=rng)
    severity_emergence = counts * severities
    reserve_emergence = lognormal_amounts_from_mean_cv(reserve, 0.22, size=n_simulations, rng=rng)
    total_emergence = severity_emergence + reserve_emergence
    payment_share = rng.beta(2.0, 7.0, size=n_simulations)
    next_payments = total_emergence * payment_share
    direct_remaining = np.maximum(total_emergence - next_payments, 0.0)
    reestimate_factor = rng.lognormal(mean=-0.5 * 0.16**2, sigma=0.16, size=n_simulations)
    method_multiplier = _method_selection_reestimate_multiplier(rows)
    component["next_12_month_payments"] = next_payments
    component["closing_best_estimate"] = direct_remaining * reestimate_factor * method_multiplier
    component["simulated_direct_remaining_unpaid_diagnostic"] = direct_remaining
    return component


def _simulate_lognormal_development_component(
    opening: pd.DataFrame,
    *,
    claim_types: set[str],
    component_name: str,
    n_simulations: int,
    rng: np.random.Generator,
    ultimate_cv: float,
    payment_share: float,
    reestimate_cv: float,
) -> pd.DataFrame:
    rows = opening.loc[opening["claim_type_basis"].isin(claim_types)]
    component = _component_frame(n_simulations)
    if rows.empty:
        return component

    current_case_estimate = float(rows["latest_incurred"].clip(lower=0.0).sum())
    if current_case_estimate == 0.0:
        current_case_estimate = float(rows["selected_ultimate"].clip(lower=0.0).sum())
    latest_paid = float(rows["latest_paid"].clip(lower=0.0).sum())
    simulated_ultimate = lognormal_amounts_from_mean_cv(
        max(current_case_estimate, 1.0),
        ultimate_cv,
        size=n_simulations,
        rng=rng,
    )
    unpaid_before_year = np.maximum(simulated_ultimate - latest_paid, 0.0)
    next_payments = unpaid_before_year * rng.beta(payment_share * 12.0, (1.0 - payment_share) * 12.0, size=n_simulations)
    direct_remaining = np.maximum(unpaid_before_year - next_payments, 0.0)
    reestimate_factor = lognormal_amounts_from_mean_cv(1.0, reestimate_cv, size=n_simulations, rng=rng)
    method_multiplier = _method_selection_reestimate_multiplier(rows)
    component["next_12_month_payments"] = next_payments
    component["closing_best_estimate"] = direct_remaining * reestimate_factor * method_multiplier
    component["simulated_direct_remaining_unpaid_diagnostic"] = direct_remaining
    component["component_name"] = component_name
    return component


def _triangle_for_opening_rows(
    triangle: pd.DataFrame,
    rows: pd.DataFrame,
    *,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    if triangle.empty or rows.empty:
        return triangle.iloc[0:0].copy()
    keys = rows[[*group_columns, "origin_year"]].drop_duplicates()
    filtered = triangle.merge(keys, on=[*group_columns, "origin_year"], how="inner")
    if filtered.empty:
        return filtered
    value_columns = [*group_columns, "origin_year", "development_year"]
    numeric_columns = [column for column in ["incremental_paid", "cumulative_paid"] if column in filtered.columns]
    return (
        filtered.groupby(value_columns, as_index=False)[numeric_columns]
        .sum()
        .sort_values(value_columns)
        .reset_index(drop=True)
    )


def _method_selection_reestimate_multiplier(rows: pd.DataFrame) -> float:
    """Use the deterministic method-selection framework to scale closing re-estimates."""
    if rows.empty:
        return 1.0
    method_multipliers = {
        "paid_chain_ladder": 0.98,
        "incurred_chain_ladder": 1.04,
        "bornhuetter_ferguson": 1.00,
        "frequency_severity": 1.08,
        "case_adequacy_review": 1.02,
        "event_based_estimate": 1.00,
        "segment_estimate": 1.00,
        "all_portfolio_selected_factors": 1.00,
    }
    weighted_total = 0.0
    weight_base = 0.0
    for row in rows.itertuples(index=False):
        row_weight = max(float(row.selected_reserve), 0.0)
        if row_weight == 0.0:
            continue
        weights = method_weights(
            solvency_ii_lob=str(row.solvency_ii_lob),
            claim_type=str(row.claim_type_basis),
            latest_development_year=int(row.latest_development_year) + 1,
            sparse=bool(row.sparse_hrg_fallback),
        )
        multiplier = sum(
            method_multipliers.get(method, 1.0) * weight
            for method, weight in weights.items()
        )
        weighted_total += multiplier * row_weight
        weight_base += row_weight
    if weight_base == 0.0:
        return 1.0
    return float(weighted_total / weight_base)


def _add_component(totals: dict[str, np.ndarray], component: pd.DataFrame) -> None:
    for column in totals:
        totals[column] += component[column].to_numpy(dtype=float)


def _zero_component_arrays(n_simulations: int) -> dict[str, np.ndarray]:
    return {
        "next_12_month_payments": np.zeros(n_simulations, dtype=float),
        "closing_best_estimate": np.zeros(n_simulations, dtype=float),
        "simulated_direct_remaining_unpaid_diagnostic": np.zeros(n_simulations, dtype=float),
    }


def _component_frame(n_simulations: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "simulation": np.arange(1, n_simulations + 1),
            "next_12_month_payments": np.zeros(n_simulations, dtype=float),
            "closing_best_estimate": np.zeros(n_simulations, dtype=float),
            "simulated_direct_remaining_unpaid_diagnostic": np.zeros(n_simulations, dtype=float),
        }
    )


def _summarise_component(component_name: str, component: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "component": component_name,
                "mean_next_12_month_payments": float(component["next_12_month_payments"].mean()),
                "mean_closing_best_estimate": float(component["closing_best_estimate"].mean()),
                "mean_direct_remaining_unpaid_diagnostic": float(
                    component["simulated_direct_remaining_unpaid_diagnostic"].mean()
                ),
            }
        ]
    )


def _settings(n_simulations: int, seed: int) -> dict[str, int | str | bool]:
    return {
        "mode": "quick",
        "simulation_count": int(n_simulations),
        "seed": int(seed),
        "full_mode_default": False,
        "closing_best_estimate_basis": "re-estimated_from_simulated_one_year_observed_triangle",
    }


def _empty_simulations() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "simulation",
            "opening_best_estimate",
            "next_12_month_payments",
            "closing_best_estimate",
            "reserve_loss",
            "simulated_direct_remaining_unpaid_diagnostic",
            "closing_best_estimate_basis",
            "closing_reestimated_from_observed_triangle",
        ]
    )
