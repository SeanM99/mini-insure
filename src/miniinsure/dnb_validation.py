"""Strict table validation helpers for MiniInsure fixture data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

Severity = Literal["error", "warning"]
ColumnKind = Literal["string", "integer", "number", "date", "boolean"]

REPO_ROOT = Path(__file__).resolve().parents[2]
SMALL_PORTFOLIO_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "small_portfolio"

TABLE_FILE_NAMES = {
    "policies": "policies.csv",
    "claims": "claims.csv",
    "payments": "payments.csv",
    "case_reserves": "case_reserves.csv",
    "catastrophe_events": "catastrophe_events.csv",
    "reinsurance_recoveries": "reinsurance_recoveries.csv",
    "economic_scenarios": "economic_scenarios.csv",
    "asset_portfolio": "asset_portfolio.csv",
    "synthetic_truth": "synthetic_truth.csv",
    "observed_valuation_snapshot": "observed_valuation_snapshot.csv",
}


@dataclass(frozen=True)
class ValidationMessage:
    """One validation finding."""

    rule_id: str
    severity: Severity
    table: str
    message: str
    row_id: str | None = None

    @property
    def export_blocking(self) -> bool:
        return self.severity == "error"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["export_blocking"] = self.export_blocking
        return data


@dataclass(frozen=True)
class TableSchema:
    """Required columns and primary key for a table."""

    table_name: str
    primary_key: tuple[str, ...]
    columns: dict[str, ColumnKind]

    @property
    def required_columns(self) -> tuple[str, ...]:
        return tuple(self.columns)


@dataclass(frozen=True)
class ValidationSummary:
    """Validation result used by tests and Streamlit pages."""

    record_counts: dict[str, int]
    messages: tuple[ValidationMessage, ...] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        return sum(message.severity == "error" for message in self.messages)

    @property
    def warning_count(self) -> int:
        return sum(message.severity == "warning" for message in self.messages)

    @property
    def export_blocked(self) -> bool:
        return self.error_count > 0

    @property
    def status(self) -> str:
        return "pass" if self.error_count == 0 else "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "export_blocked": self.export_blocked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "record_counts": dict(sorted(self.record_counts.items())),
            "messages": [message.to_dict() for message in self.messages],
        }


def error(rule_id: str, table: str, message: str, row_id: str | None = None) -> ValidationMessage:
    """Create an export-blocking validation error."""
    return ValidationMessage(rule_id=rule_id, severity="error", table=table, message=message, row_id=row_id)


def warning(rule_id: str, table: str, message: str, row_id: str | None = None) -> ValidationMessage:
    """Create a non-blocking validation warning."""
    return ValidationMessage(rule_id=rule_id, severity="warning", table=table, message=message, row_id=row_id)


def validate_table_schema(
    df: pd.DataFrame | None,
    schema: TableSchema,
) -> tuple[pd.DataFrame | None, list[ValidationMessage]]:
    """Validate required columns, parseable types, dates, and primary keys."""
    if df is None:
        return None, [error("SCHEMA001", schema.table_name, "required table is missing")]

    messages: list[ValidationMessage] = []
    missing_columns = [column for column in schema.required_columns if column not in df.columns]
    for column in missing_columns:
        messages.append(error("SCHEMA001", schema.table_name, f"required column is missing: {column}"))

    if missing_columns:
        return df.copy(), messages

    typed = df.copy()
    for column, kind in schema.columns.items():
        if kind == "date":
            parsed = pd.to_datetime(typed[column], errors="coerce")
            invalid = typed[column].notna() & parsed.isna()
            if invalid.any():
                rows = _row_ids(typed.loc[invalid], schema.primary_key)
                messages.append(
                    error(
                        "SCHEMA_DATE",
                        schema.table_name,
                        f"date column could not be parsed: {column}",
                        ", ".join(rows),
                    )
                )
            typed[column] = parsed
        elif kind in {"integer", "number"}:
            parsed_number = pd.to_numeric(typed[column], errors="coerce")
            invalid = typed[column].notna() & parsed_number.isna()
            if invalid.any():
                rows = _row_ids(typed.loc[invalid], schema.primary_key)
                messages.append(
                    error(
                        "SCHEMA_TYPE",
                        schema.table_name,
                        f"numeric column could not be parsed: {column}",
                        ", ".join(rows),
                    )
                )
            if kind == "integer":
                non_integer = parsed_number.notna() & (parsed_number % 1 != 0)
                if non_integer.any():
                    rows = _row_ids(typed.loc[non_integer], schema.primary_key)
                    messages.append(
                        error(
                            "SCHEMA_TYPE",
                            schema.table_name,
                            f"integer column contains non-integer values: {column}",
                            ", ".join(rows),
                        )
                    )
            typed[column] = parsed_number
        elif kind == "boolean":
            if not typed[column].map(lambda value: isinstance(value, bool)).all():
                messages.append(error("SCHEMA_TYPE", schema.table_name, f"boolean column is invalid: {column}"))

    messages.extend(validate_primary_key(typed, schema))
    return typed, messages


def validate_primary_key(df: pd.DataFrame, schema: TableSchema) -> list[ValidationMessage]:
    """Validate primary key columns are present, non-null, and unique."""
    messages: list[ValidationMessage] = []
    missing_pk_columns = [column for column in schema.primary_key if column not in df.columns]
    if missing_pk_columns:
        return [
            error("PK001", schema.table_name, f"primary key column is missing: {column}")
            for column in missing_pk_columns
        ]

    null_key_rows = df[list(schema.primary_key)].isna().any(axis=1)
    if null_key_rows.any():
        messages.append(
            error(
                "PK001",
                schema.table_name,
                "primary key contains null values",
                ", ".join(_row_ids(df.loc[null_key_rows], schema.primary_key)),
            )
        )

    duplicate_rows = df.duplicated(list(schema.primary_key), keep=False)
    if duplicate_rows.any():
        messages.append(
            error(
                "PK001",
                schema.table_name,
                "primary key values must be unique",
                ", ".join(_row_ids(df.loc[duplicate_rows], schema.primary_key)),
            )
        )
    return messages


def validate_foreign_key(
    *,
    child_df: pd.DataFrame | None,
    child_table: str,
    child_column: str,
    parent_df: pd.DataFrame | None,
    parent_table: str,
    parent_column: str,
    child_key: tuple[str, ...],
) -> list[ValidationMessage]:
    """Validate that a child table references existing parent keys."""
    if child_df is None or parent_df is None:
        return []
    if child_column not in child_df.columns or parent_column not in parent_df.columns:
        return []

    parent_keys = set(parent_df[parent_column].dropna().astype(str))
    invalid = child_df[child_column].dropna().astype(str).map(lambda value: value not in parent_keys)
    invalid = invalid.reindex(child_df.index, fill_value=False)
    if not invalid.any():
        return []

    return [
        error(
            "FK001",
            child_table,
            f"{child_column} must reference {parent_table}.{parent_column}",
            ", ".join(_row_ids(child_df.loc[invalid], child_key)),
        )
    ]


def load_fixture_tables(
    fixture_dir: str | Path = SMALL_PORTFOLIO_FIXTURE_DIR,
) -> dict[str, pd.DataFrame]:
    """Load the deterministic small portfolio fixture tables."""
    root = Path(fixture_dir)
    return {
        table_name: read_table(root / file_name)
        for table_name, file_name in TABLE_FILE_NAMES.items()
    }


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a CSV or Parquet table."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, keep_default_na=True)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"unsupported table format: {path}")


def validate_fixture_tables(tables: dict[str, pd.DataFrame]) -> ValidationSummary:
    """Validate all fixture tables and cross-table relationships."""
    from miniinsure.reserving.validation import (
        CASE_RESERVES_SCHEMA,
        CLAIMS_SCHEMA,
        PAYMENTS_SCHEMA,
        validate_reserving_tables,
    )
    from miniinsure.simulation.validation import (
        POLICIES_SCHEMA,
        validate_simulation_tables,
    )

    record_counts = {
        table_name: len(df)
        for table_name, df in tables.items()
    }
    messages: list[ValidationMessage] = []
    messages.extend(validate_simulation_tables(tables))
    messages.extend(validate_reserving_tables(tables))

    messages.extend(
        validate_foreign_key(
            child_df=tables.get("claims"),
            child_table=CLAIMS_SCHEMA.table_name,
            child_column="policy_id",
            parent_df=tables.get("policies"),
            parent_table=POLICIES_SCHEMA.table_name,
            parent_column="policy_id",
            child_key=CLAIMS_SCHEMA.primary_key,
        )
    )
    messages.extend(
        validate_foreign_key(
            child_df=tables.get("payments"),
            child_table=PAYMENTS_SCHEMA.table_name,
            child_column="claim_id",
            parent_df=tables.get("claims"),
            parent_table=CLAIMS_SCHEMA.table_name,
            parent_column="claim_id",
            child_key=PAYMENTS_SCHEMA.primary_key,
        )
    )
    messages.extend(
        validate_foreign_key(
            child_df=tables.get("case_reserves"),
            child_table=CASE_RESERVES_SCHEMA.table_name,
            child_column="claim_id",
            parent_df=tables.get("claims"),
            parent_table=CLAIMS_SCHEMA.table_name,
            parent_column="claim_id",
            child_key=CASE_RESERVES_SCHEMA.primary_key,
        )
    )

    return ValidationSummary(record_counts=record_counts, messages=tuple(messages))


def validate_small_portfolio_fixture(
    fixture_dir: str | Path = SMALL_PORTFOLIO_FIXTURE_DIR,
) -> ValidationSummary:
    """Load and validate the deterministic small portfolio fixture."""
    return validate_fixture_tables(load_fixture_tables(fixture_dir))


def _row_ids(df: pd.DataFrame, key_columns: tuple[str, ...]) -> list[str]:
    if df.empty:
        return []
    if not key_columns or any(column not in df.columns for column in key_columns):
        return [str(index) for index in df.index.tolist()]
    return [
        "|".join(str(value) for value in row)
        for row in df[list(key_columns)].itertuples(index=False, name=None)
    ]
