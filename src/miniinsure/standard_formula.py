"""Simplified Solvency II Standard Formula SCR."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.alm import calibrate_asset_portfolio
from miniinsure.risk_engine.aggregation import aggregate_with_correlation, two_lob_correlation_matrix
from miniinsure.risk_engine.stress_tests import market_risk_stress_summary

LOB_SIGMAS = {
    "Motor vehicle liability": 0.10,
    "Other motor insurance": 0.08,
}


@dataclass(frozen=True)
class StandardFormulaResult:
    """Simplified Standard Formula result tables."""

    summary: dict[str, float]
    non_life_by_lob: pd.DataFrame
    market: pd.DataFrame
    module_charges: pd.DataFrame
    asset_portfolio: pd.DataFrame | None = None


def non_life_premium_reserve_scr(
    nep_by_lob: dict[str, float],
    net_claims_be_by_lob: dict[str, float],
) -> tuple[float, pd.DataFrame]:
    """SCR_PR_lob = 3 * sigma_lob * (NEP + net claims best estimate)."""
    rows: list[dict[str, float | str]] = []
    charges: dict[str, float] = {}
    for lob in sorted(set(nep_by_lob) | set(net_claims_be_by_lob)):
        volume = float(nep_by_lob.get(lob, 0.0)) + float(net_claims_be_by_lob.get(lob, 0.0))
        sigma = LOB_SIGMAS.get(lob, 0.09)
        scr = 3.0 * sigma * volume
        rows.append({"solvency_ii_lob": lob, "volume": volume, "sigma": sigma, "scr_pr_lob": scr})
        charges[lob] = scr
    correlation = two_lob_correlation_matrix(list(charges), off_diagonal=0.50)
    return aggregate_with_correlation(charges, correlation), pd.DataFrame(rows)


def catastrophe_scr(net_catastrophe_losses: pd.Series | np.ndarray | list[float]) -> float:
    """Cat SCR = VaR 99.5% net catastrophe loss less expected net catastrophe loss."""
    losses = np.asarray(net_catastrophe_losses, dtype=float)
    if len(losses) == 0:
        return 0.0
    return float(np.quantile(losses, 0.995) - np.mean(losses))


def counterparty_default_scr(
    reinsurance_recoverables: float,
    *,
    pd_: float = 0.005,
    lgd: float = 0.50,
) -> float:
    """SCR_CD = 3 * PD * LGD * recoverables, subject to expected default loss minimum."""
    recoverables = max(float(reinsurance_recoverables), 0.0)
    expected_default_loss = pd_ * lgd * recoverables
    return float(max(3.0 * expected_default_loss, expected_default_loss))


def operational_scr(nep: float, net_technical_provisions: float) -> float:
    """SCR_OP = 0.03 * NEP + 0.02 * net technical provisions."""
    return float(0.03 * max(float(nep), 0.0) + 0.02 * max(float(net_technical_provisions), 0.0))


def bscr_aggregation(
    *,
    market_scr: float,
    non_life_scr: float,
    counterparty_scr: float,
) -> float:
    """Aggregate market, non-life, and counterparty default modules."""
    charges = {
        "market": market_scr,
        "non_life": non_life_scr,
        "counterparty": counterparty_scr,
    }
    correlation = pd.DataFrame(
        [
            [1.00, 0.25, 0.25],
            [0.25, 1.00, 0.50],
            [0.25, 0.50, 1.00],
        ],
        index=["market", "non_life", "counterparty"],
        columns=["market", "non_life", "counterparty"],
    )
    return aggregate_with_correlation(charges, correlation)


def simplified_standard_formula_scr(
    *,
    nep_by_lob: dict[str, float],
    net_claims_be_by_lob: dict[str, float],
    net_catastrophe_losses: pd.Series | np.ndarray | list[float],
    asset_portfolio: pd.DataFrame,
    reinsurance_recoverables: float,
    nep: float,
    net_technical_provisions: float,
) -> StandardFormulaResult:
    """Calculate simplified Standard Formula SCR."""
    pr_scr, non_life_table = non_life_premium_reserve_scr(nep_by_lob, net_claims_be_by_lob)
    cat_scr = catastrophe_scr(net_catastrophe_losses)
    non_life_total = float(np.sqrt(pr_scr**2 + cat_scr**2))
    market = market_risk_stress_summary(asset_portfolio)
    market_scr = float(market.loc[0, "market_scr"])
    counterparty = counterparty_default_scr(reinsurance_recoverables)
    bscr = bscr_aggregation(
        market_scr=market_scr,
        non_life_scr=non_life_total,
        counterparty_scr=counterparty,
    )
    op = operational_scr(nep, net_technical_provisions)
    scr = bscr + op
    module_charges = pd.DataFrame(
        [
            {"module": "market", "scr": market_scr},
            {"module": "non_life_premium_reserve", "scr": pr_scr},
            {"module": "non_life_catastrophe", "scr": cat_scr},
            {"module": "non_life_total", "scr": non_life_total},
            {"module": "counterparty_default", "scr": counterparty},
            {"module": "operational", "scr": op},
            {"module": "bscr", "scr": bscr},
            {"module": "final_scr", "scr": scr},
        ]
    )
    return StandardFormulaResult(
        summary={
            "non_life_premium_reserve_scr": pr_scr,
            "catastrophe_scr": cat_scr,
            "non_life_scr": non_life_total,
            "market_scr": market_scr,
            "counterparty_default_scr": counterparty,
            "operational_scr": op,
            "bscr": bscr,
            "scr": scr,
        },
        non_life_by_lob=non_life_table,
        market=market,
        module_charges=module_charges,
        asset_portfolio=None,
    )


def simplified_standard_formula_with_opening_assets(
    *,
    opening_liabilities: float,
    nep_by_lob: dict[str, float],
    net_claims_be_by_lob: dict[str, float],
    net_catastrophe_losses: pd.Series | np.ndarray | list[float],
    reinsurance_recoverables: float,
    nep: float,
    net_technical_provisions: float,
    iterations: int = 8,
) -> StandardFormulaResult:
    """Solve the opening asset/SCR dependency with a simple fixed-point iteration."""
    scr_guess = max(0.25 * float(opening_liabilities), 1.0)
    result: StandardFormulaResult | None = None
    asset_portfolio: pd.DataFrame | None = None
    for _ in range(max(iterations, 1)):
        asset_portfolio = calibrate_asset_portfolio(
            opening_liabilities=opening_liabilities,
            scr=scr_guess,
        )
        result = simplified_standard_formula_scr(
            nep_by_lob=nep_by_lob,
            net_claims_be_by_lob=net_claims_be_by_lob,
            net_catastrophe_losses=net_catastrophe_losses,
            asset_portfolio=asset_portfolio,
            reinsurance_recoverables=reinsurance_recoverables,
            nep=nep,
            net_technical_provisions=net_technical_provisions,
        )
        scr_guess = result.summary["scr"]
    if result is None or asset_portfolio is None:
        raise RuntimeError("standard formula fixed-point iteration failed")
    return StandardFormulaResult(
        summary=result.summary,
        non_life_by_lob=result.non_life_by_lob,
        market=result.market,
        module_charges=result.module_charges,
        asset_portfolio=asset_portfolio,
    )
