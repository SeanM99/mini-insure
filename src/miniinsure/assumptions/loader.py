"""Deterministic assumption loading, merging, hashing, and metadata."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from numbers import Real
from pathlib import Path
from typing import Any

import yaml

from miniinsure.assumptions.schema import Assumptions
from miniinsure.utils import APP_VERSION

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_ASSUMPTIONS_PATH = REPO_ROOT / "data" / "assumptions" / "base.yaml"
REGULATORY_ASSUMPTIONS_PATH = REPO_ROOT / "data" / "assumptions" / "regulatory.yaml"

TRANSFORMATION_MODES = {
    "replace",
    "multiply",
    "additive_percentage_point",
    "additive_amount",
}


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    with Path(path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return loaded


def load_effective_assumptions(
    *,
    scenario_overrides: Mapping[str, Any] | None = None,
    stress_overrides: Mapping[str, Any] | None = None,
    ui_overrides: Mapping[str, Any] | None = None,
    base_path: str | Path = BASE_ASSUMPTIONS_PATH,
    regulatory_path: str | Path = REGULATORY_ASSUMPTIONS_PATH,
) -> Assumptions:
    """Load base and regulatory assumptions, then apply optional override layers."""
    base = load_yaml_file(base_path)
    regulatory = load_yaml_file(regulatory_path)
    return build_effective_assumptions(
        base=base,
        regulatory=regulatory,
        scenario=scenario_overrides,
        stress=stress_overrides,
        ui=ui_overrides,
    )


def build_effective_assumptions(
    *,
    base: Mapping[str, Any],
    regulatory: Mapping[str, Any] | None = None,
    scenario: Mapping[str, Any] | None = None,
    stress: Mapping[str, Any] | None = None,
    ui: Mapping[str, Any] | None = None,
) -> Assumptions:
    """Merge assumptions in the required base/regulatory/scenario/stress/ui order."""
    merged: dict[str, Any] = deepcopy(dict(base))
    merged = merge_assumption_layer(merged, regulatory or {})
    merged = merge_assumption_layer(merged, scenario or {}, allow_transformations=True)
    merged = merge_assumption_layer(merged, stress or {}, allow_transformations=True)
    merged = merge_assumption_layer(merged, ui or {})
    return Assumptions.model_validate(merged)


def merge_assumption_layer(
    current: Mapping[str, Any],
    override: Mapping[str, Any],
    *,
    allow_transformations: bool = False,
) -> dict[str, Any]:
    """Return a new mapping with one assumption layer applied."""
    result: dict[str, Any] = deepcopy(dict(current))
    _merge_into(result, override, allow_transformations=allow_transformations, path=())
    return result


def stable_assumption_hash(assumptions: Assumptions | Mapping[str, Any]) -> str:
    """Hash assumptions using canonical JSON so identical assumptions hash the same."""
    validated = (
        assumptions
        if isinstance(assumptions, Assumptions)
        else Assumptions.model_validate(assumptions)
    )
    canonical = json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def scenario_metadata(
    *,
    scenario_name: str,
    assumptions: Assumptions,
    seed: int | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Create scenario metadata for reproducible downloads and later exports."""
    timestamp = generated_at or datetime.now(UTC)
    return {
        "scenario_name": scenario_name,
        "seed": assumptions.master_seed if seed is None else seed,
        "valuation_date": assumptions.valuation_date.isoformat(),
        "reporting_quarter": assumptions.primary_reporting_quarter,
        "portfolio_mode": assumptions.portfolio_mode,
        "assumption_hash": stable_assumption_hash(assumptions),
        "app_version": APP_VERSION,
        "generation_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
    }


def scenario_metadata_json(
    *,
    scenario_name: str,
    assumptions: Assumptions,
    seed: int | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Create stable, readable scenario metadata JSON."""
    return json.dumps(
        scenario_metadata(
            scenario_name=scenario_name,
            assumptions=assumptions,
            seed=seed,
            generated_at=generated_at,
        ),
        indent=2,
        sort_keys=True,
    )


def _merge_into(
    current: dict[str, Any],
    override: Mapping[str, Any],
    *,
    allow_transformations: bool,
    path: tuple[str, ...],
) -> None:
    for key, override_value in override.items():
        string_key = str(key)
        target_key = _resolve_existing_key(current, key)
        current_value = current.get(target_key)

        if allow_transformations and _is_transformation(override_value):
            current[target_key] = _apply_transformation(
                current_value,
                override_value,
                path=path + (string_key,),
            )
            continue

        if isinstance(current_value, dict) and isinstance(override_value, Mapping):
            _merge_into(
                current_value,
                override_value,
                allow_transformations=allow_transformations,
                path=path + (string_key,),
            )
            current[target_key] = current_value
            continue

        current[target_key] = deepcopy(override_value)


def _resolve_existing_key(current: Mapping[str, Any], key: Any) -> Any:
    if key in current:
        return key
    key_text = str(key)
    for existing_key in current:
        if str(existing_key) == key_text:
            return existing_key
    return key


def _is_transformation(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and "mode" in value
        and value.get("mode") in TRANSFORMATION_MODES
        and "value" in value
    )


def _apply_transformation(
    current_value: Any,
    instruction: Mapping[str, Any],
    *,
    path: tuple[str, ...],
) -> Any:
    mode = instruction["mode"]
    value = instruction["value"]

    if mode == "replace":
        return deepcopy(value)
    if current_value is None:
        dotted_path = ".".join(path)
        raise ValueError(f"cannot transform missing assumption leaf: {dotted_path}")
    if mode == "multiply":
        return _transform_numeric_tree(current_value, value, lambda left, right: left * right)
    if mode in {"additive_percentage_point", "additive_amount"}:
        return _transform_numeric_tree(current_value, value, lambda left, right: left + right)

    raise ValueError(f"unsupported assumption transformation mode: {mode}")


def _transform_numeric_tree(current_value: Any, operand: Any, operation: Any) -> Any:
    if isinstance(current_value, bool) or isinstance(operand, bool):
        raise ValueError("numeric transformations cannot be applied to booleans")

    if isinstance(current_value, Real) and isinstance(operand, Real):
        result = operation(current_value, operand)
        if isinstance(current_value, int) and float(result).is_integer():
            return int(result)
        return result

    if isinstance(current_value, list):
        return [_transform_numeric_tree(item, operand, operation) for item in current_value]

    if isinstance(current_value, dict):
        return {
            key: _transform_numeric_tree(item, operand, operation)
            for key, item in current_value.items()
        }

    raise ValueError("numeric transformations require numeric leaves")
