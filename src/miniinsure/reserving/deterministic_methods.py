"""Readable deterministic reserving methods for observed annual triangles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from miniinsure.reserving.triangles import DEFAULT_GROUP_COLUMNS, triangle_to_matrix

TAIL_FACTORS = {
    "Motor vehicle liability": 1.05,
    "Other motor insurance": 1.01,
}

EXPECTED_LOSS_RATIOS = {
    "Motor vehicle liability": 0.68,
    "Other motor insurance": 0.62,
}

METHOD_LABELS = {
    "paid_chain_ladder": "Paid chain ladder",
    "incurred_chain_ladder": "Incurred chain ladder",
    "bornhuetter_ferguson": "Bornhuetter-Ferguson",
    "frequency_severity": "Frequency-severity",
    "case_adequacy_review": "Case adequacy review",
    "event_based_estimate": "Event-based estimate",
    "segment_estimate": "Segment estimate",
    "all_portfolio_selected_factors": "All-portfolio selected factors",
}


@dataclass(frozen=True)
class ChainLadderResult:
    """Development factors and origin-year reserve estimates."""

    factors: pd.DataFrame
    origin_estimates: pd.DataFrame


def development_factors(
    cumulative_triangle: pd.DataFrame,
    *,
    value_column: str | None = None,
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """Calculate volume-weighted age-to-age factors and append the tail factor."""
    matrix = _as_matrix(cumulative_triangle, value_column)
    if matrix.empty:
        return pd.DataFrame(columns=["from_development_year", "to_development_year", "factor", "is_tail"])

    columns = [int(column) for column in matrix.columns]
    factor_rows: list[dict[str, object]] = []
    for from_dev, to_dev in zip(columns[:-1], columns[1:], strict=False):
        current = matrix[from_dev]
        next_value = matrix[to_dev]
        valid = current.notna() & next_value.notna() & (current > 0)
        factor = float(next_value.loc[valid].sum() / current.loc[valid].sum()) if valid.any() else 1.0
        factor_rows.append(
            {
                "from_development_year": from_dev,
                "to_development_year": to_dev,
                "factor": max(factor, 1.0),
                "is_tail": False,
            }
        )
    factor_rows.append(
        {
            "from_development_year": columns[-1],
            "to_development_year": "ultimate",
            "factor": float(tail_factor),
            "is_tail": True,
        }
    )
    return pd.DataFrame(factor_rows)


def cumulative_development_factors(
    cumulative_triangle: pd.DataFrame,
    *,
    value_column: str | None = None,
    tail_factor: float = 1.0,
) -> dict[int, float]:
    """Return cumulative development factors from each observed age to ultimate."""
    factors = development_factors(
        cumulative_triangle,
        value_column=value_column,
        tail_factor=tail_factor,
    )
    if factors.empty:
        return {}

    age_factors = {
        int(row.from_development_year): float(row.factor)
        for row in factors.itertuples(index=False)
        if not bool(row.is_tail)
    }
    tail_row = factors.loc[factors["is_tail"]].iloc[0]
    tail = float(tail_row["factor"])
    observed_development_years = sorted(age_factors)
    if not observed_development_years:
        return {int(tail_row["from_development_year"]): tail}
    max_dev = max(max(observed_development_years), int(tail_row["from_development_year"]))
    cdfs: dict[int, float] = {}
    for development_year in range(1, max_dev + 1):
        factor = tail
        for age in range(development_year, max_dev):
            factor *= age_factors.get(age, 1.0)
        cdfs[development_year] = max(float(factor), 1.0)
    return cdfs


def paid_chain_ladder(
    paid_triangle: pd.DataFrame,
    *,
    tail_factor: float = 1.0,
) -> ChainLadderResult:
    """Apply paid chain ladder with non-negative reserve floor."""
    return chain_ladder(
        paid_triangle,
        value_column="cumulative_paid",
        method_name="paid_chain_ladder",
        tail_factor=tail_factor,
    )


def incurred_chain_ladder(
    incurred_triangle: pd.DataFrame,
    *,
    tail_factor: float = 1.0,
) -> ChainLadderResult:
    """Apply incurred chain ladder with non-negative IBNR floor."""
    return chain_ladder(
        incurred_triangle,
        value_column="cumulative_incurred",
        method_name="incurred_chain_ladder",
        tail_factor=tail_factor,
    )


def chain_ladder(
    cumulative_triangle: pd.DataFrame,
    *,
    value_column: str,
    method_name: str,
    tail_factor: float = 1.0,
) -> ChainLadderResult:
    """Generic chain ladder over a cumulative annual triangle."""
    matrix = _as_matrix(cumulative_triangle, value_column)
    factors = development_factors(matrix, tail_factor=tail_factor)
    cdfs = cumulative_development_factors(matrix, tail_factor=tail_factor)
    rows: list[dict[str, object]] = []
    for origin_year, row in matrix.iterrows():
        latest_development_year = _latest_observed_development_year(row)
        latest_value = float(row.loc[latest_development_year]) if latest_development_year is not None else 0.0
        cdf = cdfs.get(int(latest_development_year), tail_factor) if latest_development_year is not None else tail_factor
        ultimate = max(latest_value * cdf, latest_value)
        rows.append(
            {
                "origin_year": int(origin_year),
                "method": method_name,
                "latest_development_year": int(latest_development_year or 1),
                "latest_value": latest_value,
                "cdf_to_ultimate": float(cdf),
                "ultimate": float(ultimate),
                "ibnr": float(max(ultimate - latest_value, 0.0)),
            }
        )
    return ChainLadderResult(factors=factors, origin_estimates=pd.DataFrame(rows))


def bornhuetter_ferguson(
    cumulative_triangle: pd.DataFrame,
    earned_premium_by_origin: Mapping[int, float] | pd.Series | pd.DataFrame,
    *,
    expected_loss_ratio: float,
    value_column: str = "cumulative_paid",
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """Apply Bornhuetter-Ferguson using expected loss ratio and CDF emergence."""
    matrix = _as_matrix(cumulative_triangle, value_column)
    cdfs = cumulative_development_factors(matrix, tail_factor=tail_factor)
    premium = _premium_series(earned_premium_by_origin)
    rows: list[dict[str, object]] = []
    for origin_year, row in matrix.iterrows():
        latest_development_year = _latest_observed_development_year(row)
        latest_value = float(row.loc[latest_development_year]) if latest_development_year is not None else 0.0
        cdf = cdfs.get(int(latest_development_year), tail_factor) if latest_development_year is not None else tail_factor
        expected_ultimate = float(premium.get(int(origin_year), 0.0)) * float(expected_loss_ratio)
        unreported_percentage = max(1.0 - min(1.0 / max(cdf, 1.0), 1.0), 0.0)
        ibnr = max(expected_ultimate * unreported_percentage, 0.0)
        rows.append(
            {
                "origin_year": int(origin_year),
                "method": "bornhuetter_ferguson",
                "latest_development_year": int(latest_development_year or 1),
                "latest_value": latest_value,
                "expected_ultimate": expected_ultimate,
                "cdf_to_ultimate": float(cdf),
                "unreported_percentage": float(unreported_percentage),
                "ultimate": float(latest_value + ibnr),
                "ibnr": float(ibnr),
            }
        )
    return pd.DataFrame(rows)


def cape_cod(
    cumulative_triangle: pd.DataFrame,
    earned_premium_by_origin: Mapping[int, float] | pd.Series | pd.DataFrame,
    *,
    value_column: str = "cumulative_paid",
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """Apply Cape Cod with exposure-weighted selected loss ratio."""
    matrix = _as_matrix(cumulative_triangle, value_column)
    cdfs = cumulative_development_factors(matrix, tail_factor=tail_factor)
    premium = _premium_series(earned_premium_by_origin)
    latest_values: dict[int, float] = {}
    used_up_premium: dict[int, float] = {}
    latest_development: dict[int, int] = {}
    for origin_year, row in matrix.iterrows():
        latest_dev = _latest_observed_development_year(row)
        latest_development[int(origin_year)] = int(latest_dev or 1)
        latest = float(row.loc[latest_dev]) if latest_dev is not None else 0.0
        cdf = cdfs.get(int(latest_dev), tail_factor) if latest_dev is not None else tail_factor
        percent_reported = min(1.0 / max(cdf, 1.0), 1.0)
        latest_values[int(origin_year)] = latest
        used_up_premium[int(origin_year)] = float(premium.get(int(origin_year), 0.0)) * percent_reported

    denominator = sum(used_up_premium.values())
    selected_loss_ratio = sum(latest_values.values()) / denominator if denominator > 0 else 0.0
    rows: list[dict[str, object]] = []
    for origin_year, latest in latest_values.items():
        raw_ultimate = float(premium.get(origin_year, 0.0)) * selected_loss_ratio
        ultimate = max(raw_ultimate, latest)
        rows.append(
            {
                "origin_year": int(origin_year),
                "method": "cape_cod",
                "latest_development_year": latest_development[origin_year],
                "latest_value": float(latest),
                "used_up_premium": float(used_up_premium[origin_year]),
                "selected_loss_ratio": float(selected_loss_ratio),
                "ultimate": float(ultimate),
                "ibnr": float(max(ultimate - latest, 0.0)),
            }
        )
    return pd.DataFrame(rows)


def method_weights(
    *,
    solvency_ii_lob: str,
    claim_type: str,
    latest_development_year: int,
    sparse: bool = False,
) -> dict[str, float]:
    """Return deterministic method weights for a segment and origin year."""
    if sparse:
        return {"segment_estimate": 0.50, "all_portfolio_selected_factors": 0.50}
    if claim_type == "large_bi":
        return {"incurred_chain_ladder": 0.20, "frequency_severity": 0.60, "case_adequacy_review": 0.20}
    if claim_type == "catastrophe_allocated":
        return {"event_based_estimate": 0.70, "bornhuetter_ferguson": 0.30}
    if solvency_ii_lob == "Motor vehicle liability" and claim_type == "attritional_bi":
        if latest_development_year >= 4:
            return {"paid_chain_ladder": 0.20, "incurred_chain_ladder": 0.40, "bornhuetter_ferguson": 0.40}
        return {"incurred_chain_ladder": 0.20, "bornhuetter_ferguson": 0.80}
    if solvency_ii_lob == "Motor vehicle liability":
        if latest_development_year >= 4:
            return {"paid_chain_ladder": 0.30, "incurred_chain_ladder": 0.30, "bornhuetter_ferguson": 0.40}
        return {"incurred_chain_ladder": 0.30, "bornhuetter_ferguson": 0.70}
    if latest_development_year >= 3:
        return {"paid_chain_ladder": 0.80, "bornhuetter_ferguson": 0.20}
    return {"paid_chain_ladder": 0.40, "bornhuetter_ferguson": 0.60}


def apply_sparse_hrg_fallback(segment_estimate: float, all_portfolio_estimate: float) -> float:
    """Apply the required sparse HRG 50/50 fallback."""
    return 0.50 * float(segment_estimate) + 0.50 * float(all_portfolio_estimate)


def blend_method_estimates(
    estimates: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """Blend method estimates using explicit weights."""
    return float(sum(float(estimates.get(method, 0.0)) * weight for method, weight in weights.items()))


def deterministic_reserving_results(
    paid_triangle: pd.DataFrame,
    incurred_triangle: pd.DataFrame,
    policies: pd.DataFrame,
    claims: pd.DataFrame,
    *,
    sparse_claim_threshold: int = 30,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> pd.DataFrame:
    """Return selected deterministic reserve estimates by LoB, HRG, and origin year."""
    if paid_triangle.empty or incurred_triangle.empty:
        return _empty_results(group_columns)

    all_paid = _drop_group_columns(paid_triangle, group_columns)
    all_incurred = _drop_group_columns(incurred_triangle, group_columns)
    all_tail = float(np.mean(list(TAIL_FACTORS.values())))
    all_paid_result = paid_chain_ladder(all_paid, tail_factor=all_tail).origin_estimates
    all_factor_by_origin = all_paid_result.set_index("origin_year")["cdf_to_ultimate"].to_dict()

    rows: list[dict[str, object]] = []
    segment_keys = paid_triangle[list(group_columns)].drop_duplicates()
    for segment in segment_keys.itertuples(index=False, name=None):
        segment_filter = _segment_filter(paid_triangle, group_columns, segment)
        segment_paid = paid_triangle.loc[segment_filter]
        segment_incurred = incurred_triangle.loc[_segment_filter(incurred_triangle, group_columns, segment)]
        if segment_paid.empty or segment_incurred.empty:
            continue

        lob = str(segment[group_columns.index("solvency_ii_lob")]) if "solvency_ii_lob" in group_columns else ""
        hrg = str(segment[group_columns.index("homogeneous_risk_group")]) if "homogeneous_risk_group" in group_columns else ""
        tail = TAIL_FACTORS.get(lob, 1.0)
        expected_loss_ratio = EXPECTED_LOSS_RATIOS.get(lob, 0.65)
        premium = _earned_premium_for_segment(policies, segment, group_columns)
        paid_result = paid_chain_ladder(segment_paid, tail_factor=tail).origin_estimates.set_index("origin_year")
        incurred_result = incurred_chain_ladder(segment_incurred, tail_factor=tail).origin_estimates.set_index("origin_year")
        bf_result = bornhuetter_ferguson(
            segment_paid,
            premium,
            expected_loss_ratio=expected_loss_ratio,
            tail_factor=tail,
        ).set_index("origin_year")

        origins = sorted(set(paid_result.index).union(incurred_result.index).union(bf_result.index))
        claim_profile = _claim_profile_for_segment(claims, segment, group_columns)
        for origin_year in origins:
            claim_type = _dominant_claim_type(claim_profile, int(origin_year))
            claim_count = _claim_count(claim_profile, int(origin_year))
            paid_latest = float(paid_result.loc[origin_year, "latest_value"]) if origin_year in paid_result.index else 0.0
            incurred_latest = (
                float(incurred_result.loc[origin_year, "latest_value"]) if origin_year in incurred_result.index else paid_latest
            )
            latest_development_year = int(
                max(
                    paid_result.loc[origin_year, "latest_development_year"] if origin_year in paid_result.index else 1,
                    incurred_result.loc[origin_year, "latest_development_year"] if origin_year in incurred_result.index else 1,
                )
            )
            method_estimates = {
                "paid_chain_ladder": float(paid_result.loc[origin_year, "ultimate"]) if origin_year in paid_result.index else paid_latest,
                "incurred_chain_ladder": (
                    float(incurred_result.loc[origin_year, "ultimate"]) if origin_year in incurred_result.index else incurred_latest
                ),
                "bornhuetter_ferguson": float(bf_result.loc[origin_year, "ultimate"]) if origin_year in bf_result.index else paid_latest,
                "frequency_severity": max(incurred_latest * tail, incurred_latest),
                "case_adequacy_review": max(incurred_latest * 1.05, incurred_latest),
                "event_based_estimate": incurred_latest,
            }
            base_weights = method_weights(
                solvency_ii_lob=lob,
                claim_type=claim_type,
                latest_development_year=latest_development_year,
                sparse=False,
            )
            segment_estimate = blend_method_estimates(method_estimates, base_weights)
            all_portfolio_estimate = paid_latest * all_factor_by_origin.get(int(origin_year), tail)
            sparse = claim_count < sparse_claim_threshold
            if sparse:
                weights = method_weights(
                    solvency_ii_lob=lob,
                    claim_type=claim_type,
                    latest_development_year=latest_development_year,
                    sparse=True,
                )
                selected_ultimate = apply_sparse_hrg_fallback(segment_estimate, all_portfolio_estimate)
            else:
                weights = base_weights
                selected_ultimate = segment_estimate
            selected_ultimate = max(float(selected_ultimate), incurred_latest, paid_latest)
            rows.append(
                {
                    **dict(zip(group_columns, segment, strict=True)),
                    "origin_year": int(origin_year),
                    "claim_type_basis": claim_type,
                    "claim_count": int(claim_count),
                    "latest_development_year": latest_development_year,
                    "sparse_hrg_fallback": bool(sparse),
                    "method_weights": _format_weights(weights),
                    "selected_method": _format_weights(weights),
                    "latest_paid": paid_latest,
                    "latest_incurred": incurred_latest,
                    "paid_chain_ladder_ultimate": method_estimates["paid_chain_ladder"],
                    "incurred_chain_ladder_ultimate": method_estimates["incurred_chain_ladder"],
                    "bornhuetter_ferguson_ultimate": method_estimates["bornhuetter_ferguson"],
                    "selected_ultimate": selected_ultimate,
                    "ibnr": max(selected_ultimate - incurred_latest, 0.0),
                    "selected_reserve": max(selected_ultimate - paid_latest, 0.0),
                }
            )
    return pd.DataFrame(rows).sort_values([*group_columns, "origin_year"]).reset_index(drop=True)


def _as_matrix(triangle: pd.DataFrame, value_column: str | None = None) -> pd.DataFrame:
    if triangle.empty:
        return pd.DataFrame()
    if value_column and {"origin_year", "development_year", value_column}.issubset(triangle.columns):
        return triangle_to_matrix(triangle, value_column)
    matrix = triangle.copy()
    matrix.columns = [int(column) for column in matrix.columns]
    return matrix.sort_index().sort_index(axis=1)


def _latest_observed_development_year(row: pd.Series) -> int | None:
    observed = row.dropna()
    if observed.empty:
        return None
    return int(observed.index[-1])


def _premium_series(earned_premium_by_origin: Mapping[int, float] | pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(earned_premium_by_origin, pd.DataFrame):
        if {"origin_year", "earned_premium"}.issubset(earned_premium_by_origin.columns):
            return earned_premium_by_origin.set_index("origin_year")["earned_premium"].astype(float)
        if {"accident_year", "earned_premium"}.issubset(earned_premium_by_origin.columns):
            return earned_premium_by_origin.set_index("accident_year")["earned_premium"].astype(float)
        raise ValueError("premium dataframe must contain origin_year or accident_year and earned_premium")
    if isinstance(earned_premium_by_origin, pd.Series):
        return earned_premium_by_origin.astype(float)
    return pd.Series(dict(earned_premium_by_origin), dtype=float)


def _drop_group_columns(triangle: pd.DataFrame, group_columns: tuple[str, ...]) -> pd.DataFrame:
    columns = [column for column in triangle.columns if column not in group_columns]
    grouped = triangle[columns].groupby(["origin_year", "development_year"], as_index=False).sum(numeric_only=True)
    return grouped


def _segment_filter(frame: pd.DataFrame, group_columns: tuple[str, ...], segment: tuple[object, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column, value in zip(group_columns, segment, strict=True):
        mask = mask & (frame[column] == value)
    return mask


def _earned_premium_for_segment(
    policies: pd.DataFrame,
    segment: tuple[object, ...],
    group_columns: tuple[str, ...],
) -> pd.Series:
    if policies.empty or "earned_premium" not in policies.columns:
        return pd.Series(dtype=float)
    filtered = policies.copy()
    for column, value in zip(group_columns, segment, strict=True):
        if column in filtered.columns:
            filtered = filtered.loc[filtered[column] == value]
    year_column = "accident_year" if "accident_year" in filtered.columns else "underwriting_year"
    return filtered.groupby(year_column)["earned_premium"].sum().astype(float)


def _claim_profile_for_segment(
    claims: pd.DataFrame,
    segment: tuple[object, ...],
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    if claims.empty:
        return claims.copy()
    filtered = claims.copy()
    for column, value in zip(group_columns, segment, strict=True):
        if column in filtered.columns:
            filtered = filtered.loc[filtered[column] == value]
    return filtered


def _dominant_claim_type(claims: pd.DataFrame, origin_year: int) -> str:
    if claims.empty or "claim_type" not in claims.columns:
        return "attritional"
    filtered = claims.loc[claims["accident_year"].astype(int) == origin_year]
    if filtered.empty:
        return "attritional"
    return str(filtered["claim_type"].mode().iloc[0])


def _claim_count(claims: pd.DataFrame, origin_year: int) -> int:
    if claims.empty or "claim_id" not in claims.columns:
        return 0
    return int(claims.loc[claims["accident_year"].astype(int) == origin_year, "claim_id"].nunique())


def _format_weights(weights: Mapping[str, float]) -> str:
    return ", ".join(f"{METHOD_LABELS.get(method, method)} {weight:.0%}" for method, weight in weights.items())


def _empty_results(group_columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            *group_columns,
            "origin_year",
            "claim_type_basis",
            "claim_count",
            "latest_development_year",
            "sparse_hrg_fallback",
            "selected_method",
            "latest_paid",
            "latest_incurred",
            "selected_ultimate",
            "ibnr",
            "selected_reserve",
        ]
    )
