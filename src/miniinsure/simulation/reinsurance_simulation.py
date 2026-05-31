"""Fixed default reinsurance program for MiniInsure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReinsuranceProgram:
    """Default fixed reinsurance program."""

    quota_share_enabled: bool = False
    quota_share_ceded_pct: float = 0.0
    ceding_commission_rate: float = 0.20
    per_risk_xol_enabled: bool = True
    per_risk_retention: float = 250_000.0
    per_risk_limit: float = 1_000_000.0
    per_risk_rate_on_line: float = 0.18
    reinstatement_count: int = 1
    reinstatement_rate: float = 1.0
    aggregate_stop_loss_enabled: bool = True
    aggregate_attachment_loss_ratio: float = 0.90
    aggregate_stop_loss_limit: float = 10_000_000.0
    aggregate_premium_multiple: float = 1.25
    counterparty_default_pd: float = 0.005
    counterparty_lgd: float = 0.50
    recovery_delay_months: int = 3

    def __post_init__(self) -> None:
        if not 0.0 <= self.quota_share_ceded_pct <= 0.40:
            raise ValueError("quota_share_ceded_pct must be between 0% and 40%")
        if self.per_risk_retention < 0 or self.per_risk_limit < 0:
            raise ValueError("per-risk retention and limit must be non-negative")
        if self.aggregate_stop_loss_limit < 0:
            raise ValueError("aggregate stop loss limit must be non-negative")


@dataclass(frozen=True)
class ReinsuranceResult:
    """Auditable claim and annual reinsurance outputs."""

    claim_level: pd.DataFrame
    annual_level: pd.DataFrame
    summary: dict[str, float]


def per_risk_xol_recovery(
    loss: pd.Series | np.ndarray | float,
    *,
    retention: float = 250_000.0,
    limit: float = 1_000_000.0,
) -> pd.Series | float:
    """Per-risk recovery = min(max(loss - retention, 0), limit)."""
    values = np.minimum(np.maximum(np.asarray(loss, dtype=float) - retention, 0.0), limit)
    if np.isscalar(loss):
        return float(values)
    return pd.Series(values, index=getattr(loss, "index", None))


def aggregate_stop_loss_recovery(
    annual_loss: pd.Series | np.ndarray | float,
    earned_premium: pd.Series | np.ndarray | float,
    *,
    attachment_loss_ratio: float = 0.90,
    limit: float = 10_000_000.0,
) -> pd.Series | float:
    """Aggregate recovery = min(max(annual_loss - 0.90 * earned_premium, 0), limit)."""
    values = np.minimum(
        np.maximum(np.asarray(annual_loss, dtype=float) - attachment_loss_ratio * np.asarray(earned_premium, dtype=float), 0.0),
        limit,
    )
    if np.isscalar(annual_loss) and np.isscalar(earned_premium):
        return float(values)
    return pd.Series(values, index=getattr(annual_loss, "index", None))


def default_adjusted_recoverable(
    recovery: pd.Series | np.ndarray | float,
    *,
    pd_: float = 0.005,
    lgd: float = 0.50,
) -> pd.Series | float:
    """Default-adjusted recoverable = recovery * (1 - PD * LGD)."""
    values = np.asarray(recovery, dtype=float) * (1.0 - pd_ * lgd)
    if np.isscalar(recovery):
        return float(values)
    return pd.Series(values, index=getattr(recovery, "index", None))


def apply_default_reinsurance_program(
    claims: pd.DataFrame,
    policies: pd.DataFrame,
    *,
    program: ReinsuranceProgram | None = None,
    loss_column: str = "latest_case_estimate",
) -> ReinsuranceResult:
    """Apply the fixed treaty order to observed claim estimates."""
    program = program or ReinsuranceProgram()
    if claims.empty:
        return _empty_result(policies)
    if loss_column not in claims.columns:
        raise ValueError(f"claims must include loss column: {loss_column}")

    claim_level = claims.copy()
    claim_level["gross_loss"] = pd.to_numeric(claim_level[loss_column], errors="coerce").fillna(0.0).clip(lower=0.0)
    claim_level["quota_share_ceded_pct"] = program.quota_share_ceded_pct if program.quota_share_enabled else 0.0
    claim_level["quota_share_ceded_loss"] = claim_level["gross_loss"] * claim_level["quota_share_ceded_pct"]
    claim_level["loss_after_quota_share"] = claim_level["gross_loss"] - claim_level["quota_share_ceded_loss"]

    if program.per_risk_xol_enabled:
        claim_level["per_risk_xol_recovery"] = per_risk_xol_recovery(
            claim_level["loss_after_quota_share"],
            retention=program.per_risk_retention,
            limit=program.per_risk_limit,
        )
    else:
        claim_level["per_risk_xol_recovery"] = 0.0
    claim_level["per_risk_xol_recovery"] = np.minimum(
        claim_level["per_risk_xol_recovery"],
        claim_level["loss_after_quota_share"],
    )
    base_xol_premium = program.per_risk_limit * program.per_risk_rate_on_line
    claim_level["per_risk_reinstatement_premium"] = np.minimum(
        claim_level["per_risk_xol_recovery"] / max(program.per_risk_limit, 1.0),
        float(program.reinstatement_count),
    ) * base_xol_premium * program.reinstatement_rate
    claim_level["net_loss_before_aggregate"] = (
        claim_level["loss_after_quota_share"] - claim_level["per_risk_xol_recovery"]
    ).clip(lower=0.0)
    claim_level["per_risk_default_adjusted_recoverable"] = default_adjusted_recoverable(
        claim_level["per_risk_xol_recovery"],
        pd_=program.counterparty_default_pd,
        lgd=program.counterparty_lgd,
    )

    annual_level = _annual_reinsurance(claim_level, policies, program)
    summary = {
        "gross_loss": float(annual_level["gross_loss"].sum()),
        "quota_share_ceded_loss": float(annual_level["quota_share_ceded_loss"].sum()),
        "per_risk_xol_recovery": float(annual_level["per_risk_xol_recovery"].sum()),
        "aggregate_stop_loss_recovery": float(annual_level["aggregate_stop_loss_recovery"].sum()),
        "total_recovery": float(annual_level["total_recovery"].sum()),
        "default_adjusted_recoverable": float(annual_level["default_adjusted_recoverable"].sum()),
        "net_loss": float(annual_level["net_loss"].sum()),
    }
    return ReinsuranceResult(claim_level=claim_level, annual_level=annual_level, summary=summary)


def _annual_reinsurance(
    claim_level: pd.DataFrame,
    policies: pd.DataFrame,
    program: ReinsuranceProgram,
) -> pd.DataFrame:
    annual_claims = claim_level.groupby("accident_year", as_index=False).agg(
        gross_loss=("gross_loss", "sum"),
        quota_share_ceded_loss=("quota_share_ceded_loss", "sum"),
        loss_after_quota_share=("loss_after_quota_share", "sum"),
        per_risk_xol_recovery=("per_risk_xol_recovery", "sum"),
        net_loss_before_aggregate=("net_loss_before_aggregate", "sum"),
        per_risk_reinstatement_premium=("per_risk_reinstatement_premium", "sum"),
    )
    annual_premium = policies.groupby("accident_year", as_index=False).agg(
        earned_premium=("earned_premium", "sum"),
    )
    annual = annual_premium.merge(annual_claims, on="accident_year", how="left").fillna(0.0)
    annual["quota_share_ceded_premium"] = (
        annual["earned_premium"] * program.quota_share_ceded_pct
        if program.quota_share_enabled
        else 0.0
    )
    annual["quota_share_ceding_commission"] = annual["quota_share_ceded_premium"] * program.ceding_commission_rate
    annual["per_risk_xol_premium"] = (
        program.per_risk_limit * program.per_risk_rate_on_line
        if program.per_risk_xol_enabled
        else 0.0
    )
    if program.aggregate_stop_loss_enabled:
        annual["aggregate_stop_loss_recovery"] = aggregate_stop_loss_recovery(
            annual["net_loss_before_aggregate"],
            annual["earned_premium"],
            attachment_loss_ratio=program.aggregate_attachment_loss_ratio,
            limit=program.aggregate_stop_loss_limit,
        )
    else:
        annual["aggregate_stop_loss_recovery"] = 0.0
    annual["aggregate_stop_loss_recovery"] = np.minimum(
        annual["aggregate_stop_loss_recovery"],
        annual["net_loss_before_aggregate"],
    )
    annual["aggregate_stop_loss_premium"] = (
        annual["aggregate_stop_loss_recovery"] * program.aggregate_premium_multiple
    )
    annual["total_recovery"] = (
        annual["quota_share_ceded_loss"]
        + annual["per_risk_xol_recovery"]
        + annual["aggregate_stop_loss_recovery"]
    )
    annual["total_recovery"] = np.minimum(annual["total_recovery"], annual["gross_loss"])
    annual["default_adjusted_recoverable"] = default_adjusted_recoverable(
        annual["total_recovery"],
        pd_=program.counterparty_default_pd,
        lgd=program.counterparty_lgd,
    )
    annual["net_loss"] = (annual["gross_loss"] - annual["total_recovery"]).clip(lower=0.0)
    annual["gross_loss_ratio"] = np.divide(
        annual["gross_loss"],
        annual["earned_premium"],
        out=np.zeros(len(annual), dtype=float),
        where=annual["earned_premium"].to_numpy(dtype=float) != 0,
    )
    annual["net_loss_ratio"] = np.divide(
        annual["net_loss"],
        annual["earned_premium"],
        out=np.zeros(len(annual), dtype=float),
        where=annual["earned_premium"].to_numpy(dtype=float) != 0,
    )
    return annual.sort_values("accident_year").reset_index(drop=True)


def gross_to_net_reconciliation(result: ReinsuranceResult) -> pd.DataFrame:
    """Return a compact gross-to-net annual reconciliation."""
    return result.annual_level[
        [
            "accident_year",
            "earned_premium",
            "gross_loss",
            "quota_share_ceded_loss",
            "per_risk_xol_recovery",
            "aggregate_stop_loss_recovery",
            "total_recovery",
            "default_adjusted_recoverable",
            "net_loss",
            "gross_loss_ratio",
            "net_loss_ratio",
        ]
    ].copy()


def _empty_result(policies: pd.DataFrame) -> ReinsuranceResult:
    annual = policies.groupby("accident_year", as_index=False).agg(earned_premium=("earned_premium", "sum"))
    for column in [
        "gross_loss",
        "quota_share_ceded_loss",
        "loss_after_quota_share",
        "per_risk_xol_recovery",
        "net_loss_before_aggregate",
        "per_risk_reinstatement_premium",
        "quota_share_ceded_premium",
        "quota_share_ceding_commission",
        "per_risk_xol_premium",
        "aggregate_stop_loss_recovery",
        "aggregate_stop_loss_premium",
        "total_recovery",
        "default_adjusted_recoverable",
        "net_loss",
        "gross_loss_ratio",
        "net_loss_ratio",
    ]:
        annual[column] = 0.0
    return ReinsuranceResult(
        claim_level=pd.DataFrame(),
        annual_level=annual,
        summary={
            "gross_loss": 0.0,
            "quota_share_ceded_loss": 0.0,
            "per_risk_xol_recovery": 0.0,
            "aggregate_stop_loss_recovery": 0.0,
            "total_recovery": 0.0,
            "default_adjusted_recoverable": 0.0,
            "net_loss": 0.0,
        },
    )
