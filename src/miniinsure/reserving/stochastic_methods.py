"""Stochastic reserving methods used by quick-mode reserve risk."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.reserving.deterministic_methods import cumulative_development_factors


@dataclass(frozen=True)
class ChainLadderFit:
    """Compact chain-ladder fit for bootstrap simulation."""

    factors: pd.DataFrame
    cdfs: dict[int, float]
    fitted_cumulative: pd.DataFrame
    fitted_incremental: pd.DataFrame
    latest_development_year: dict[int, int]
    latest_cumulative: dict[int, float]
    ultimate: dict[int, float]


def cumulative_to_incremental(cumulative: pd.DataFrame) -> pd.DataFrame:
    """Convert cumulative triangle matrix to incremental triangle matrix."""
    if cumulative.empty:
        return cumulative.copy()
    ordered = cumulative.sort_index().sort_index(axis=1).astype(float)
    incremental = ordered.copy()
    columns = list(ordered.columns)
    for index, column in enumerate(columns):
        if index == 0:
            incremental[column] = ordered[column]
        else:
            previous = ordered[columns[index - 1]]
            incremental[column] = ordered[column] - previous.fillna(0.0)
            incremental.loc[ordered[column].isna(), column] = np.nan
    return incremental


def incremental_to_cumulative(incremental: pd.DataFrame) -> pd.DataFrame:
    """Convert incremental triangle matrix to cumulative triangle matrix."""
    if incremental.empty:
        return incremental.copy()
    ordered = incremental.sort_index().sort_index(axis=1).astype(float)
    cumulative = ordered.cumsum(axis=1, skipna=True)
    cumulative = cumulative.where(ordered.notna())
    return cumulative


def fit_paid_chain_ladder_for_bootstrap(
    cumulative: pd.DataFrame,
    *,
    tail_factor: float = 1.0,
) -> ChainLadderFit:
    """Fit paid chain ladder and derive fitted cumulative and incremental values."""
    matrix = cumulative.sort_index().sort_index(axis=1).astype(float)
    cdfs = cumulative_development_factors(matrix, tail_factor=tail_factor)
    fitted_cumulative = matrix.copy()
    latest_development: dict[int, int] = {}
    latest_cumulative: dict[int, float] = {}
    ultimate: dict[int, float] = {}

    for origin_year, row in matrix.iterrows():
        observed = row.dropna()
        if observed.empty:
            latest_dev = int(matrix.columns[0])
            latest_value = 0.0
        else:
            latest_dev = int(observed.index[-1])
            latest_value = float(observed.iloc[-1])
        latest_development[int(origin_year)] = latest_dev
        latest_cumulative[int(origin_year)] = latest_value
        ultimate_estimate = latest_value * cdfs.get(latest_dev, tail_factor)
        ultimate[int(origin_year)] = float(max(ultimate_estimate, latest_value))

        for development_year in matrix.columns:
            if pd.isna(row[development_year]):
                fitted_cumulative.loc[origin_year, development_year] = np.nan
                continue
            cdf = max(cdfs.get(int(development_year), 1.0), 1.0)
            fitted_cumulative.loc[origin_year, development_year] = ultimate[int(origin_year)] / cdf

    fitted_incremental = cumulative_to_incremental(fitted_cumulative).clip(lower=0.0)
    factors = _factor_frame(matrix, tail_factor=tail_factor)
    return ChainLadderFit(
        factors=factors,
        cdfs=cdfs,
        fitted_cumulative=fitted_cumulative,
        fitted_incremental=fitted_incremental,
        latest_development_year=latest_development,
        latest_cumulative=latest_cumulative,
        ultimate=ultimate,
    )


def pearson_residuals(
    observed_incremental: pd.DataFrame,
    fitted_incremental: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate centered Pearson residuals by development period."""
    residuals = (observed_incremental - fitted_incremental) / np.sqrt(fitted_incremental.clip(lower=1.0))
    residuals = residuals.where(observed_incremental.notna() & fitted_incremental.notna())
    for development_year in residuals.columns:
        valid = residuals[development_year].dropna()
        if valid.empty:
            continue
        residuals[development_year] = residuals[development_year] - float(valid.mean())
    return residuals


def bootstrap_chain_ladder_one_year(
    cumulative: pd.DataFrame,
    *,
    n_simulations: int,
    rng: np.random.Generator,
    tail_factor: float = 1.0,
    tail_sigma: float = 0.01,
) -> pd.DataFrame:
    """Run the required bootstrap chain-ladder one-year simulation."""
    matrix = cumulative.sort_index().sort_index(axis=1).astype(float)
    if matrix.empty or n_simulations <= 0:
        return _empty_bootstrap_result()

    observed_incremental = cumulative_to_incremental(matrix)
    opening_fit = fit_paid_chain_ladder_for_bootstrap(matrix, tail_factor=tail_factor)
    residuals = pearson_residuals(observed_incremental, opening_fit.fitted_incremental)
    process_phi = _process_phi(residuals)

    rows: list[dict[str, float | int]] = []
    for simulation in range(1, n_simulations + 1):
        simulated_tail = float(tail_factor * rng.lognormal(mean=-0.5 * tail_sigma**2, sigma=tail_sigma))
        pseudo_incremental = _pseudo_incremental_triangle(
            opening_fit.fitted_incremental,
            observed_incremental,
            residuals,
            rng,
        )
        pseudo_cumulative = incremental_to_cumulative(pseudo_incremental)
        refit = fit_paid_chain_ladder_for_bootstrap(pseudo_cumulative, tail_factor=simulated_tail)

        next_payments = 0.0
        closing_reserve = 0.0
        direct_remaining = 0.0
        opening_chain_ladder_reserve = 0.0
        for origin_year, latest_development_year in refit.latest_development_year.items():
            latest_cumulative = refit.latest_cumulative[origin_year]
            ultimate = refit.ultimate[origin_year]
            opening_chain_ladder_reserve += max(ultimate - latest_cumulative, 0.0)
            next_development_year = latest_development_year + 1
            expected_next_cumulative = _expected_cumulative_at_development(
                ultimate,
                next_development_year,
                refit.cdfs,
            )
            expected_next_increment = max(expected_next_cumulative - latest_cumulative, 0.0)
            next_payment = overdispersed_poisson_process_amount(expected_next_increment, process_phi, rng)
            next_payments += next_payment

            closing_cumulative = latest_cumulative + next_payment
            closing_cdf = max(refit.cdfs.get(next_development_year, 1.0), 1.0)
            closing_reserve += max(closing_cumulative * closing_cdf - closing_cumulative, 0.0)
            direct_remaining += max(ultimate - closing_cumulative, 0.0)

        rows.append(
            {
                "simulation": simulation,
                "next_12_month_payments": float(next_payments),
                "closing_reestimated_reserve": float(closing_reserve),
                "opening_chain_ladder_reserve": float(opening_chain_ladder_reserve),
                "simulated_direct_remaining_unpaid_diagnostic": float(direct_remaining),
                "tail_factor": simulated_tail,
                "process_phi": process_phi,
            }
        )
    return pd.DataFrame(rows)


def negative_binomial_counts(
    mean: float,
    dispersion: float,
    *,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate counts using the Gamma-Poisson negative binomial representation."""
    mean = max(float(mean), 0.0)
    dispersion = max(float(dispersion), 1e-6)
    if mean == 0.0:
        return np.zeros(size, dtype=int)
    gamma_lambda = rng.gamma(shape=dispersion, scale=mean / dispersion, size=size)
    return rng.poisson(gamma_lambda)


def lognormal_amounts_from_mean_cv(
    mean: float,
    coefficient_of_variation: float,
    *,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate lognormal amounts from a target mean and coefficient of variation."""
    mean = max(float(mean), 0.0)
    if mean == 0.0:
        return np.zeros(size, dtype=float)
    cv = max(float(coefficient_of_variation), 1e-6)
    sigma = np.sqrt(np.log(1.0 + cv**2))
    mu = np.log(mean) - 0.5 * sigma**2
    return rng.lognormal(mean=mu, sigma=sigma, size=size)


def overdispersed_poisson_process_amount(
    mean_amount: float,
    dispersion: float,
    rng: np.random.Generator,
) -> float:
    """Add overdispersed Poisson process variation to a future incremental payment."""
    mean_amount = max(float(mean_amount), 0.0)
    if mean_amount == 0.0:
        return 0.0
    unit = max(mean_amount / 1_000.0, 1.0)
    lambda_mean = mean_amount / unit
    phi = max(float(dispersion), 1.0)
    gamma_lambda = rng.gamma(shape=lambda_mean / phi, scale=phi)
    return float(rng.poisson(gamma_lambda) * unit)


def _pseudo_incremental_triangle(
    fitted_incremental: pd.DataFrame,
    observed_incremental: pd.DataFrame,
    residuals: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    pseudo = fitted_incremental.copy()
    for development_year in fitted_incremental.columns:
        residual_pool = residuals[development_year].dropna().to_numpy(dtype=float)
        observed_mask = observed_incremental[development_year].notna()
        if len(residual_pool) == 0:
            sampled = np.zeros(int(observed_mask.sum()), dtype=float)
        else:
            sampled = rng.choice(residual_pool, size=int(observed_mask.sum()), replace=True)
        fitted_values = fitted_incremental.loc[observed_mask, development_year].to_numpy(dtype=float)
        pseudo.loc[observed_mask, development_year] = np.maximum(
            fitted_values + sampled * np.sqrt(np.maximum(fitted_values, 1.0)),
            0.0,
        )
        pseudo.loc[~observed_mask, development_year] = np.nan
    return pseudo


def _expected_cumulative_at_development(
    ultimate: float,
    development_year: int,
    cdfs: dict[int, float],
) -> float:
    cdf = max(cdfs.get(int(development_year), 1.0), 1.0)
    return float(max(ultimate / cdf, 0.0))


def _process_phi(residuals: pd.DataFrame) -> float:
    values = residuals.to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if len(values) <= 1:
        return 1.0
    return float(max(np.var(values, ddof=1), 1.0))


def _factor_frame(matrix: pd.DataFrame, *, tail_factor: float) -> pd.DataFrame:
    columns = [int(column) for column in matrix.columns]
    rows: list[dict[str, object]] = []
    for from_dev, to_dev in zip(columns[:-1], columns[1:], strict=False):
        current = matrix[from_dev]
        next_value = matrix[to_dev]
        valid = current.notna() & next_value.notna() & (current > 0)
        factor = float(next_value.loc[valid].sum() / current.loc[valid].sum()) if valid.any() else 1.0
        rows.append(
            {
                "from_development_year": from_dev,
                "to_development_year": to_dev,
                "factor": max(factor, 1.0),
                "is_tail": False,
            }
        )
    if columns:
        rows.append(
            {
                "from_development_year": columns[-1],
                "to_development_year": "ultimate",
                "factor": float(tail_factor),
                "is_tail": True,
            }
        )
    return pd.DataFrame(rows)


def _empty_bootstrap_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "simulation",
            "next_12_month_payments",
            "closing_reestimated_reserve",
            "opening_chain_ladder_reserve",
            "simulated_direct_remaining_unpaid_diagnostic",
            "tail_factor",
            "process_phi",
        ]
    )
