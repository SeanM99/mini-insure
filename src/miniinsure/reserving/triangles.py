"""Annual observed reserving triangles.

The functions in this module deliberately work from observed modelling inputs:
claim statuses, report dates, visible payments, and case estimates as of the
valuation date. Hidden synthetic ultimate fields are not required or accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from miniinsure.dnb_validation import ValidationMessage, error
from miniinsure.simulation.claim_settlement import VALUATION_DATE

DEFAULT_GROUP_COLUMNS = ("solvency_ii_lob", "homogeneous_risk_group")


@dataclass(frozen=True)
class TriangleSet:
    """Container for annual cumulative reserving triangles."""

    paid: pd.DataFrame
    incurred: pd.DataFrame
    counts: pd.DataFrame
    average_cost: pd.DataFrame


def calculate_development_year(
    calendar_year: int | pd.Series | np.ndarray,
    accident_year: int | pd.Series | np.ndarray,
) -> int | pd.Series:
    """Calculate annual development year as calendar year minus accident year plus one."""
    development = pd.Series(calendar_year, dtype="int64") - pd.Series(accident_year, dtype="int64") + 1
    if len(development) == 1:
        return int(development.iloc[0])
    return development.astype(int)


def development_year_from_date(
    dates: pd.Series | Iterable[object],
    accident_years: pd.Series | Iterable[object],
) -> pd.Series:
    """Calculate annual development year from event dates and accident years."""
    parsed_dates = pd.to_datetime(pd.Series(dates), errors="coerce")
    years = parsed_dates.dt.year
    accident = pd.Series(accident_years, dtype="int64")
    return (years - accident + 1).astype("Int64")


def build_annual_triangles(
    claims: pd.DataFrame,
    payments: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> TriangleSet:
    """Build paid, incurred, count, and average-cost triangles from observed data."""
    observed_claims = _prepare_claims(claims, valuation_date, group_columns)
    paid = build_paid_triangle(
        observed_claims,
        payments,
        valuation_date=valuation_date,
        group_columns=group_columns,
    )
    incurred = build_incurred_triangle(
        observed_claims,
        valuation_date=valuation_date,
        group_columns=group_columns,
    )
    counts = build_count_triangle(
        observed_claims,
        valuation_date=valuation_date,
        group_columns=group_columns,
    )
    average_cost = build_average_cost_triangle(incurred, counts, group_columns=group_columns)
    return TriangleSet(paid=paid, incurred=incurred, counts=counts, average_cost=average_cost)


def build_paid_triangle(
    claims: pd.DataFrame,
    payments: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> pd.DataFrame:
    """Build cumulative paid triangles, excluding zero insured amount claims."""
    prepared_claims = _prepare_claims(claims, valuation_date, group_columns)
    skeleton = _triangle_skeleton(prepared_claims, valuation_date, group_columns)
    value_columns = list(group_columns) + ["origin_year", "development_year"]
    if skeleton.empty:
        return _empty_paid_triangle(group_columns)
    if payments.empty:
        skeleton["incremental_paid"] = 0.0
        skeleton["cumulative_paid"] = 0.0
        return _with_development_aliases(skeleton, "cumulative_paid", group_columns)

    claim_lookup = prepared_claims.loc[
        ~prepared_claims["zero_insured_flag"].fillna(False),
        ["claim_id", "accident_year", *group_columns],
    ].copy()
    visible_payments = payments.copy()
    visible_payments["payment_date"] = pd.to_datetime(visible_payments["payment_date"], errors="coerce")
    visible_payments = visible_payments.loc[visible_payments["payment_date"] <= valuation_date]
    joined = visible_payments.merge(claim_lookup, on="claim_id", how="inner")
    if joined.empty:
        incremental = pd.DataFrame(columns=value_columns + ["incremental_paid"])
    else:
        joined["origin_year"] = joined["accident_year"].astype(int)
        joined["development_year"] = development_year_from_date(
            joined["payment_date"],
            joined["accident_year"],
        ).astype(int)
        joined = joined.loc[joined["development_year"] >= 1]
        incremental = (
            joined.groupby(value_columns, as_index=False)
            .agg(incremental_paid=("paid_amount", "sum"))
        )

    triangle = skeleton.merge(incremental, on=value_columns, how="left")
    triangle["incremental_paid"] = triangle["incremental_paid"].fillna(0.0).astype(float)
    triangle = triangle.sort_values([*group_columns, "origin_year", "development_year"]).reset_index(drop=True)
    triangle["cumulative_paid"] = triangle.groupby([*group_columns, "origin_year"])["incremental_paid"].cumsum()
    return _with_development_aliases(triangle, "cumulative_paid", group_columns)


def build_incurred_triangle(
    claims: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> pd.DataFrame:
    """Build cumulative incurred triangles from observed latest case estimates."""
    prepared_claims = _prepare_claims(claims, valuation_date, group_columns)
    skeleton = _triangle_skeleton(prepared_claims, valuation_date, group_columns)
    value_columns = list(group_columns) + ["origin_year", "development_year"]
    if skeleton.empty:
        return _empty_incurred_triangle(group_columns)

    reported = prepared_claims.copy()
    reported["development_year"] = development_year_from_date(
        reported["report_date"],
        reported["accident_year"],
    ).astype(int)
    reported["origin_year"] = reported["accident_year"].astype(int)
    reported["observed_incurred_estimate"] = pd.to_numeric(
        reported["latest_case_estimate"],
        errors="coerce",
    ).fillna(0.0)
    reported = reported.loc[reported["development_year"] >= 1]
    incremental = (
        reported.groupby(value_columns, as_index=False)
        .agg(incremental_incurred=("observed_incurred_estimate", "sum"))
    )
    triangle = skeleton.merge(incremental, on=value_columns, how="left")
    triangle["incremental_incurred"] = triangle["incremental_incurred"].fillna(0.0).astype(float)
    triangle = triangle.sort_values([*group_columns, "origin_year", "development_year"]).reset_index(drop=True)
    triangle["cumulative_incurred"] = triangle.groupby([*group_columns, "origin_year"])[
        "incremental_incurred"
    ].cumsum()
    return _with_development_aliases(triangle, "cumulative_incurred", group_columns)


def build_count_triangle(
    claims: pd.DataFrame,
    *,
    valuation_date: pd.Timestamp = VALUATION_DATE,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> pd.DataFrame:
    """Build cumulative reported claim count triangles, including zero insured claims."""
    prepared_claims = _prepare_claims(claims, valuation_date, group_columns)
    skeleton = _triangle_skeleton(prepared_claims, valuation_date, group_columns)
    value_columns = list(group_columns) + ["origin_year", "development_year"]
    if skeleton.empty:
        return _empty_count_triangle(group_columns)

    reported = prepared_claims.copy()
    reported["development_year"] = development_year_from_date(
        reported["report_date"],
        reported["accident_year"],
    ).astype(int)
    reported["origin_year"] = reported["accident_year"].astype(int)
    reported = reported.loc[reported["development_year"] >= 1]
    incremental = (
        reported.groupby(value_columns, as_index=False)
        .agg(incremental_count=("claim_id", "nunique"))
    )
    triangle = skeleton.merge(incremental, on=value_columns, how="left")
    triangle["incremental_count"] = triangle["incremental_count"].fillna(0).astype(int)
    triangle = triangle.sort_values([*group_columns, "origin_year", "development_year"]).reset_index(drop=True)
    triangle["cumulative_count"] = triangle.groupby([*group_columns, "origin_year"])[
        "incremental_count"
    ].cumsum()
    return _with_development_aliases(triangle, "cumulative_count", group_columns)


def build_average_cost_triangle(
    incurred_triangle: pd.DataFrame,
    count_triangle: pd.DataFrame,
    *,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> pd.DataFrame:
    """Build average-cost triangle as cumulative incurred divided by cumulative counts."""
    if incurred_triangle.empty or count_triangle.empty:
        return _empty_average_cost_triangle(group_columns)

    keys = list(group_columns) + ["origin_year", "development_year"]
    average = incurred_triangle[keys + ["cumulative_incurred"]].merge(
        count_triangle[keys + ["cumulative_count"]],
        on=keys,
        how="outer",
    )
    average["cumulative_incurred"] = average["cumulative_incurred"].fillna(0.0)
    average["cumulative_count"] = average["cumulative_count"].fillna(0).astype(int)
    average["average_cost"] = np.where(
        average["cumulative_count"] > 0,
        average["cumulative_incurred"] / average["cumulative_count"],
        0.0,
    )
    average = average.sort_values([*group_columns, "origin_year", "development_year"]).reset_index(drop=True)
    return _with_development_aliases(average, "average_cost", group_columns)


def triangle_to_matrix(
    triangle: pd.DataFrame,
    value_column: str,
    *,
    index_column: str = "origin_year",
    development_column: str = "development_year",
) -> pd.DataFrame:
    """Pivot a long annual triangle to accident-year by development-year form."""
    if triangle.empty:
        return pd.DataFrame()
    matrix = triangle.pivot_table(
        index=index_column,
        columns=development_column,
        values=value_column,
        aggfunc="sum",
    )
    matrix = matrix.sort_index().sort_index(axis=1)
    matrix.index.name = index_column
    matrix.columns.name = development_column
    return matrix


def validate_cumulative_paid_non_decreasing(
    paid_triangle: pd.DataFrame,
    *,
    group_columns: tuple[str, ...] = DEFAULT_GROUP_COLUMNS,
) -> list[ValidationMessage]:
    """DQ007: cumulative paid must be non-decreasing for each group and origin year."""
    if paid_triangle.empty:
        return []
    required = {*group_columns, "origin_year", "development_year", "cumulative_paid"}
    missing = required.difference(paid_triangle.columns)
    if missing:
        return [
            error(
                "DQ007",
                "paid_triangle",
                f"paid triangle is missing required columns: {sorted(missing)}",
            )
        ]

    ordered = paid_triangle.sort_values([*group_columns, "origin_year", "development_year"])
    movement = ordered.groupby([*group_columns, "origin_year"])["cumulative_paid"].diff()
    invalid = movement < -1e-9
    if not invalid.any():
        return []

    invalid_rows = ordered.loc[invalid, [*group_columns, "origin_year", "development_year"]]
    row_ids = [
        "|".join(str(value) for value in row)
        for row in invalid_rows.itertuples(index=False, name=None)
    ]
    return [
        error(
            "DQ007",
            "paid_triangle",
            "cumulative paid must be non-decreasing by LoB, HRG, and origin year",
            ", ".join(row_ids),
        )
    ]


def _prepare_claims(
    claims: pd.DataFrame,
    valuation_date: pd.Timestamp,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    required = {"claim_id", "accident_year", "report_date", "latest_case_estimate", *group_columns}
    missing = required.difference(claims.columns)
    if missing:
        return pd.DataFrame(columns=[*required, "zero_insured_flag"])

    prepared = claims.copy()
    prepared["report_date"] = pd.to_datetime(prepared["report_date"], errors="coerce")
    if "zero_insured_flag" not in prepared.columns:
        prepared["zero_insured_flag"] = False
    prepared = prepared.loc[prepared["report_date"].notna() & (prepared["report_date"] <= valuation_date)]
    prepared["accident_year"] = prepared["accident_year"].astype(int)
    for column in group_columns:
        prepared[column] = prepared[column].astype(str)
    return prepared.reset_index(drop=True)


def _triangle_skeleton(
    claims: pd.DataFrame,
    valuation_date: pd.Timestamp,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    if claims.empty:
        return pd.DataFrame(columns=[*group_columns, "origin_year", "development_year"])
    rows: list[dict[str, object]] = []
    valuation_year = pd.Timestamp(valuation_date).year
    origins = claims[[*group_columns, "accident_year"]].drop_duplicates()
    for row in origins.itertuples(index=False):
        group_values = dict(zip(group_columns, row[: len(group_columns)], strict=True))
        origin_year = int(row[-1])
        latest_development = max(valuation_year - origin_year + 1, 1)
        for development_year in range(1, latest_development + 1):
            rows.append(
                {
                    **group_values,
                    "origin_year": origin_year,
                    "development_year": development_year,
                }
            )
    return pd.DataFrame(rows)


def _with_development_aliases(
    triangle: pd.DataFrame,
    value_column: str,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    triangle = triangle.copy()
    triangle["accident_year"] = triangle["origin_year"]
    triangle["development_period"] = triangle["development_year"]
    ordered = [
        *group_columns,
        "origin_year",
        "accident_year",
        "development_year",
        "development_period",
    ]
    ordered = [column for column in ordered if column in triangle.columns]
    value_columns = [column for column in triangle.columns if column not in ordered]
    if value_column in value_columns:
        value_columns = [column for column in value_columns if column != value_column] + [value_column]
    return triangle[ordered + value_columns]


def _empty_paid_triangle(group_columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[*group_columns, "origin_year", "accident_year", "development_year", "development_period", "incremental_paid", "cumulative_paid"]
    )


def _empty_incurred_triangle(group_columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[*group_columns, "origin_year", "accident_year", "development_year", "development_period", "incremental_incurred", "cumulative_incurred"]
    )


def _empty_count_triangle(group_columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[*group_columns, "origin_year", "accident_year", "development_year", "development_period", "incremental_count", "cumulative_count"]
    )


def _empty_average_cost_triangle(group_columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[*group_columns, "origin_year", "accident_year", "development_year", "development_period", "cumulative_incurred", "cumulative_count", "average_cost"]
    )
