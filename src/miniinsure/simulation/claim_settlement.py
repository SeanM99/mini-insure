"""Claim settlement, payment, and case reserve simulation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VALUATION_DATE = pd.Timestamp("2026-12-31")

SETTLEMENT_DELAY_MEAN_DAYS = {
    "liability_property_damage": 120,
    "own_damage_attritional": 90,
    "theft_fire": 75,
    "attritional_bi": 420,
    "large_bi": 900,
    "catastrophe_allocated": 180,
}

PAYMENT_PATTERN = np.array([0.45, 0.35, 0.20])


@dataclass(frozen=True)
class LifecycleTables:
    """Observed claim lifecycle tables."""

    observed_claims: pd.DataFrame
    payments: pd.DataFrame
    case_reserves: pd.DataFrame


def apply_settlement_and_payments(
    claims: pd.DataFrame,
    truth: pd.DataFrame,
    *,
    rng: np.random.Generator,
    valuation_date: pd.Timestamp = VALUATION_DATE,
) -> LifecycleTables:
    """Simulate settlements, payments, and case reserves visible at valuation."""
    if claims.empty:
        return LifecycleTables(
            observed_claims=_empty_observed_claims(),
            payments=_empty_payments(),
            case_reserves=_empty_case_reserves(),
        )

    claims = claims.merge(
        truth[["claim_id", "insured_ultimate_amount"]],
        on="claim_id",
        how="left",
    ).copy()
    means = claims["claim_type"].map(SETTLEMENT_DELAY_MEAN_DAYS).fillna(150).astype(float)
    settlement_delay = rng.gamma(shape=2.0, scale=means / 2.0).round().astype(int)
    settlement_delay = np.maximum(settlement_delay, 0)
    true_settlement_date = pd.to_datetime(claims["report_date"]) + pd.to_timedelta(settlement_delay, unit="D")
    claims["true_settlement_date"] = true_settlement_date
    claims["claim_status"] = np.where(true_settlement_date <= valuation_date, "settled", "open")
    claims["settlement_date"] = true_settlement_date.where(true_settlement_date <= valuation_date, pd.NaT)
    claims["overpayment_flag"] = False

    payment_rows: list[dict[str, object]] = []
    reserve_rows: list[dict[str, object]] = []
    observed_rows: list[dict[str, object]] = []

    for row in claims.itertuples(index=False):
        ultimate = float(row.insured_ultimate_amount)
        paid_to_date = 0.0
        if ultimate > 0:
            rows, paid_to_date = _generate_claim_payments(row, ultimate, rng, valuation_date)
            payment_rows.extend(rows)
        case_estimate = _case_estimate(row, ultimate, paid_to_date, rng)
        case_reserve = 0.0 if row.claim_status == "settled" else max(case_estimate - paid_to_date, 0.0)
        reserve_rows.append(
            {
                "case_reserve_id": f"CR{row.claim_id}",
                "claim_id": row.claim_id,
                "valuation_date": valuation_date,
                "case_reserve": case_reserve,
            }
        )
        observed_rows.append(
            {
                "claim_id": row.claim_id,
                "policy_id": row.policy_id,
                "accident_year": row.accident_year,
                "accident_date": row.accident_date,
                "report_date": row.report_date,
                "settlement_date": row.settlement_date,
                "claim_status": row.claim_status,
                "claim_type": row.claim_type,
                "coverage_type": row.coverage_type,
                "solvency_ii_lob": row.solvency_ii_lob,
                "homogeneous_risk_group": row.homogeneous_risk_group,
                "country_group": row.country_group,
                "paid_to_date": paid_to_date,
                "latest_case_estimate": case_estimate,
                "case_reserve": case_reserve,
                "zero_insured_flag": bool(row.zero_insured_flag),
                "large_loss_flag": bool(row.large_loss_flag),
                "catastrophe_event_id": row.catastrophe_event_id,
                "reopened_flag": False,
                "overpayment_flag": False,
            }
        )

    payments = pd.DataFrame(payment_rows) if payment_rows else _empty_payments()
    if not payments.empty:
        payments = payments.sort_values(["claim_id", "payment_date", "payment_id"]).reset_index(drop=True)
    return LifecycleTables(
        observed_claims=pd.DataFrame(observed_rows),
        payments=payments,
        case_reserves=pd.DataFrame(reserve_rows),
    )


def _generate_claim_payments(
    row: object,
    ultimate: float,
    rng: np.random.Generator,
    valuation_date: pd.Timestamp,
) -> tuple[list[dict[str, object]], float]:
    report_date = pd.Timestamp(row.report_date)
    accident_date = pd.Timestamp(row.accident_date)
    true_settlement_date = pd.Timestamp(row.true_settlement_date)
    if row.claim_status == "settled":
        shares = rng.dirichlet(PAYMENT_PATTERN * 35.0)
        payment_dates = _payment_dates_between(report_date, true_settlement_date, len(shares))
        amounts = shares * ultimate
        amounts[-1] = ultimate - amounts[:-1].sum()
    else:
        age_days = max((valuation_date - report_date).days, 0)
        if age_days == 0:
            return [], 0.0
        cumulative_share = min(0.75, 0.18 + 0.0015 * age_days)
        payment_count = int(np.clip(np.ceil(age_days / 180), 1, 3))
        shares = rng.dirichlet(PAYMENT_PATTERN[:payment_count] * 30.0)
        amounts = shares * ultimate * cumulative_share
        payment_dates = _payment_dates_between(report_date, valuation_date, payment_count)

    rows: list[dict[str, object]] = []
    for idx, (payment_date, amount) in enumerate(zip(payment_dates, amounts, strict=True), start=1):
        visible_date = max(pd.Timestamp(payment_date), report_date, accident_date)
        if visible_date > valuation_date:
            continue
        rows.append(
            {
                "payment_id": f"PAY{row.claim_id}{idx:02d}",
                "claim_id": row.claim_id,
                "payment_date": visible_date,
                "paid_amount": float(amount),
                "overpayment_flag": False,
            }
        )
    return rows, float(sum(item["paid_amount"] for item in rows))


def _payment_dates_between(start: pd.Timestamp, end: pd.Timestamp, count: int) -> list[pd.Timestamp]:
    if count <= 0:
        return []
    if end < start:
        end = start
    offsets = np.linspace(0, max((end - start).days, 0), count + 2)[1:-1]
    return [start + pd.to_timedelta(int(round(offset)), unit="D") for offset in offsets]


def _case_estimate(row: object, ultimate: float, paid_to_date: float, rng: np.random.Generator) -> float:
    if row.claim_status == "settled":
        return paid_to_date
    if ultimate <= 0:
        return 0.0
    noise = rng.lognormal(mean=-0.5 * 0.22**2, sigma=0.22)
    return max(paid_to_date, ultimate * noise)


def _empty_observed_claims() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "claim_id",
            "policy_id",
            "accident_year",
            "accident_date",
            "report_date",
            "settlement_date",
            "claim_status",
            "claim_type",
            "coverage_type",
            "solvency_ii_lob",
            "homogeneous_risk_group",
            "country_group",
            "paid_to_date",
            "latest_case_estimate",
            "case_reserve",
            "zero_insured_flag",
            "large_loss_flag",
            "catastrophe_event_id",
            "reopened_flag",
            "overpayment_flag",
        ]
    )


def _empty_payments() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "payment_id",
            "claim_id",
            "payment_date",
            "paid_amount",
            "overpayment_flag",
        ]
    )


def _empty_case_reserves() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "case_reserve_id",
            "claim_id",
            "valuation_date",
            "case_reserve",
        ]
    )
