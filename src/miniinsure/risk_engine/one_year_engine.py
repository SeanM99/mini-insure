"""One-year economic capital engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from miniinsure.alm import calibrate_asset_portfolio
from miniinsure.own_funds import one_year_own_funds_movement
from miniinsure.risk_engine.dependency import gaussian_copula_drivers
from miniinsure.simulation.economic_scenarios import (
    bond_return,
    cash_return,
    deterministic_equity_return,
)
from miniinsure.utils import MASTER_SEED


@dataclass(frozen=True)
class OneYearCapitalResult:
    """One-year economic capital result."""

    simulations: pd.DataFrame
    summary: pd.DataFrame
    settings: dict[str, int]


def economic_capital_summary(losses: pd.Series | np.ndarray | list[float]) -> pd.DataFrame:
    """Economic capital = VaR 99.5% loss less expected loss, with TVaR."""
    values = np.asarray(losses, dtype=float)
    if len(values) == 0:
        return pd.DataFrame(
            [{"expected_loss": 0.0, "var_995": 0.0, "tvar_995": 0.0, "economic_capital": 0.0}]
        )
    expected = float(np.mean(values))
    var_995 = float(np.quantile(values, 0.995))
    tail = values[values >= var_995]
    tvar_995 = float(np.mean(tail)) if len(tail) else var_995
    return pd.DataFrame(
        [
            {
                "expected_loss": expected,
                "var_995": var_995,
                "tvar_995": tvar_995,
                "economic_capital": var_995 - expected,
            }
        ]
    )


def simulate_one_year_economic_capital(
    policies: pd.DataFrame,
    reserve_risk_simulations: pd.DataFrame,
    *,
    opening_own_funds: float,
    opening_net_best_estimate: float,
    reinsurance_recoverables: float,
    n_simulations: int = 1_000,
    seed: int = MASTER_SEED,
    asset_portfolio: pd.DataFrame | None = None,
) -> OneYearCapitalResult:
    """Simulate one-year own-funds movement and economic loss."""
    if n_simulations <= 0:
        raise ValueError("n_simulations must be positive")
    rng = np.random.default_rng(seed)
    drivers = gaussian_copula_drivers(n=n_simulations, seed=seed + 17)
    nep = float(policies["earned_premium"].sum()) if "earned_premium" in policies.columns else 0.0
    expected_loss = _expected_new_business_loss(policies)
    reserve_loss = _reserve_loss_vector(reserve_risk_simulations, n_simulations, rng)
    net_claims = _simulate_premium_risk_claims(policies, n_simulations=n_simulations, rng=rng)
    expense_ratio = np.maximum(rng.normal(0.22, 0.025, size=n_simulations), 0.0)
    expenses = nep * expense_ratio
    assets = asset_portfolio
    if assets is None:
        assets = calibrate_asset_portfolio(opening_liabilities=opening_net_best_estimate, scr=max(opening_own_funds / 1.40, 0.0))
    investment_result = _investment_results(assets, drivers)
    operational_loss = 0.03 * abs(nep) + 0.01 * max(float(opening_net_best_estimate), 0.0)
    credit_loss = _credit_losses(
        reinsurance_recoverables=float(reinsurance_recoverables),
        drivers=drivers,
        pd_=0.005,
        lgd=0.50,
    )

    of1 = np.array(
        [
            one_year_own_funds_movement(
                of0=opening_own_funds,
                nep=nep,
                net_claims=float(net_claims[index]),
                reserve_loss=float(reserve_loss[index]),
                expenses=float(expenses[index]),
                investment_result=float(investment_result[index]),
                operational_loss=float(operational_loss),
                credit_loss=float(credit_loss[index]),
            )
            for index in range(n_simulations)
        ],
        dtype=float,
    )
    losses = float(opening_own_funds) - of1
    simulations = pd.DataFrame(
        {
            "simulation": np.arange(1, n_simulations + 1),
            "of0": float(opening_own_funds),
            "of1": of1,
            "one_year_loss": losses,
            "nep": nep,
            "expected_new_business_loss": expected_loss,
            "net_claims": net_claims,
            "premium_risk_loss": net_claims - expected_loss,
            "reserve_loss": reserve_loss,
            "expenses": expenses,
            "investment_result": investment_result,
            "market_risk_loss": -investment_result,
            "operational_loss": operational_loss,
            "credit_loss": credit_loss,
        }
    )
    return OneYearCapitalResult(
        simulations=simulations,
        summary=economic_capital_summary(simulations["one_year_loss"]),
        settings={"simulation_count": int(n_simulations), "seed": int(seed)},
    )


def _expected_new_business_loss(policies: pd.DataFrame) -> float:
    if "loss_cost" in policies.columns:
        return float(policies["loss_cost"].sum())
    if "earned_premium" in policies.columns:
        return 0.62 * float(policies["earned_premium"].sum())
    return 0.0


def _expected_claim_count(policies: pd.DataFrame) -> float:
    frequency_columns = [column for column in policies.columns if column.startswith("expected_frequency_")]
    if frequency_columns:
        return float(policies[frequency_columns].sum().sum())
    return max(float(len(policies)) * 0.08, 1.0)


def _simulate_premium_risk_claims(
    policies: pd.DataFrame,
    *,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    expected_loss = _expected_new_business_loss(policies)
    expected_count = max(_expected_claim_count(policies), 1.0)
    mean_severity = max(expected_loss / expected_count, 1.0)
    dispersion = 2.0
    gamma_lambda = rng.gamma(shape=dispersion, scale=expected_count / dispersion, size=n_simulations)
    counts = rng.poisson(gamma_lambda)
    severity_cv = 0.70
    sigma = np.sqrt(np.log(1.0 + severity_cv**2))
    mu = np.log(mean_severity) - 0.5 * sigma**2
    sampled_mean_severity = rng.lognormal(mean=mu, sigma=sigma, size=n_simulations)
    return counts * sampled_mean_severity


def _reserve_loss_vector(
    reserve_risk_simulations: pd.DataFrame,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if reserve_risk_simulations.empty or "reserve_loss" not in reserve_risk_simulations.columns:
        return np.zeros(n_simulations, dtype=float)
    values = reserve_risk_simulations["reserve_loss"].to_numpy(dtype=float)
    if len(values) >= n_simulations:
        return values[:n_simulations]
    return rng.choice(values, size=n_simulations, replace=True)


def _investment_results(asset_portfolio: pd.DataFrame, drivers: pd.DataFrame) -> np.ndarray:
    total = np.zeros(len(drivers), dtype=float)
    ir_change = 0.01 * drivers["IR"].to_numpy(dtype=float)
    spread_change = 0.005 * drivers["SP"].to_numpy(dtype=float)
    equity_returns = np.array(
        [deterministic_equity_return(0.065 + 0.18 * value) for value in drivers["EQ"].to_numpy(dtype=float)],
        dtype=float,
    )
    for row in asset_portfolio.itertuples(index=False):
        market_value = float(row.market_value)
        if row.asset_class == "cash":
            total += market_value * cash_return()
        elif row.asset_class in {"short_bonds", "long_bonds"}:
            returns = np.array(
                [
                    bond_return(
                        yield_rate=float(row.expected_return),
                        duration=float(row.interest_duration),
                        interest_rate_change=float(ir_change[index]),
                        spread_change=float(spread_change[index]),
                    )
                    for index in range(len(drivers))
                ],
                dtype=float,
            )
            total += market_value * returns
        elif row.asset_class == "equities":
            total += market_value * equity_returns
    return total


def _credit_losses(
    *,
    reinsurance_recoverables: float,
    drivers: pd.DataFrame,
    pd_: float,
    lgd: float,
) -> np.ndarray:
    recoverables = max(float(reinsurance_recoverables), 0.0)
    if recoverables == 0.0:
        return np.zeros(len(drivers), dtype=float)
    threshold = norm.ppf(1.0 - pd_)
    defaults = drivers["RDf"].to_numpy(dtype=float) > threshold
    return defaults.astype(float) * recoverables * lgd
