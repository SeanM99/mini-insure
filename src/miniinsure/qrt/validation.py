"""Mock DNB-style validation for QRT-shaped outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from miniinsure.qrt.mappings import REPORTING_CURRENCY, TEMPLATE_STATUS, monetary_columns
from miniinsure.reporting import FinancialReportingResult
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult

ValidationSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class QRTValidationMessage:
    """One mock QRT validation message."""

    rule_id: str
    severity: ValidationSeverity
    template: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "template": self.template,
            "message": self.message,
        }


def validate_qrt_pack(
    pack: dict[str, pd.DataFrame],
    *,
    capital: CapitalWorkflowResult,
    financial: FinancialReportingResult,
    tolerance: float = 1.0,
) -> pd.DataFrame:
    """Validate QRT-shaped tables with mock DNB rules DNB001-DNB008."""
    messages: list[QRTValidationMessage] = []
    messages.extend(_rule_dnb001(pack, tolerance=tolerance))
    messages.extend(_rule_dnb002(pack, tolerance=tolerance))
    messages.extend(_rule_dnb003(pack, tolerance=tolerance))
    messages.extend(_rule_dnb004(pack, tolerance=tolerance))
    messages.extend(_rule_dnb005(pack, capital=capital, tolerance=tolerance))
    messages.extend(_rule_dnb006(pack, financial=financial, tolerance=tolerance))
    messages.extend(_rule_dnb007(pack))
    messages.extend(_rule_dnb008(pack))
    if not messages:
        return pd.DataFrame(columns=["rule_id", "severity", "template", "message"])
    return pd.DataFrame([message.to_dict() for message in messages])


def validation_summary(validation: pd.DataFrame) -> dict[str, int | str | bool]:
    """Return export-blocking status from a validation frame."""
    errors = 0 if validation.empty else int((validation["severity"] == "error").sum())
    warnings = 0 if validation.empty else int((validation["severity"] == "warning").sum())
    return {
        "status": "pass" if errors == 0 else "fail",
        "error_count": errors,
        "warning_count": warnings,
        "export_blocked": errors > 0,
    }


def has_blocking_errors(validation: pd.DataFrame) -> bool:
    """Return whether the validation report contains export-blocking errors."""
    return not validation.empty and bool((validation["severity"] == "error").any())


def _rule_dnb001(pack: dict[str, pd.DataFrame], *, tolerance: float) -> list[QRTValidationMessage]:
    s0602 = pack.get("S.06.02.01", pd.DataFrame())
    s0201 = pack.get("S.02.01.02", pd.DataFrame())
    asset_total = _sum_column(s0602, "market_value")
    investments = _item_amount(s0201, "investments_excluding_cash")
    cash = _item_amount(s0201, "cash_and_deposits")
    if _within(asset_total, investments + cash, tolerance):
        return []
    return [
        QRTValidationMessage(
            "DNB001",
            "error",
            "S.06.02.01",
            "S.06.02 asset total must reconcile to S.02.01 investments plus cash.",
        )
    ]


def _rule_dnb002(pack: dict[str, pd.DataFrame], *, tolerance: float) -> list[QRTValidationMessage]:
    s1701 = pack.get("S.17.01.02", pd.DataFrame())
    gross_best = _item_amount(s1701, "gross_best_estimate")
    net_best = _item_amount(s1701, "net_best_estimate")
    risk_margin = _item_amount(s1701, "risk_margin")
    gross_tp = _item_amount(s1701, "gross_technical_provisions")
    net_tp = _item_amount(s1701, "net_technical_provisions")
    if _within(gross_tp, gross_best + risk_margin, tolerance) and _within(net_tp, net_best + risk_margin, tolerance):
        return []
    return [
        QRTValidationMessage(
            "DNB002",
            "error",
            "S.17.01.02",
            "S.17.01 total technical provisions must equal best estimate plus risk margin.",
        )
    ]


def _rule_dnb003(pack: dict[str, pd.DataFrame], *, tolerance: float) -> list[QRTValidationMessage]:
    s0201 = pack.get("S.02.01.02", pd.DataFrame())
    total_assets = _item_amount(s0201, "total_assets")
    total_liabilities = _item_amount(s0201, "total_liabilities")
    excess = _item_amount(s0201, "excess_assets_over_liabilities")
    if _within(total_assets - total_liabilities, excess, tolerance):
        return []
    return [
        QRTValidationMessage(
            "DNB003",
            "error",
            "S.02.01.02",
            "S.02.01 assets minus liabilities must equal excess assets over liabilities.",
        )
    ]


def _rule_dnb004(pack: dict[str, pd.DataFrame], *, tolerance: float) -> list[QRTValidationMessage]:
    s0201 = pack.get("S.02.01.02", pd.DataFrame())
    s2301 = pack.get("S.23.01.01", pd.DataFrame())
    excess = _item_amount(s0201, "excess_assets_over_liabilities")
    eligible = _item_amount(s2301, "eligible_own_funds_to_meet_scr")
    if _within(excess, eligible, tolerance):
        return []
    return [
        QRTValidationMessage(
            "DNB004",
            "error",
            "S.23.01.01",
            "S.23.01 eligible own funds must reconcile to excess assets over liabilities.",
        )
    ]


def _rule_dnb005(
    pack: dict[str, pd.DataFrame],
    *,
    capital: CapitalWorkflowResult,
    tolerance: float,
) -> list[QRTValidationMessage]:
    s2801 = pack.get("S.28.01.01", pd.DataFrame())
    final_mcr = _item_amount(s2801, "final_mcr")
    if _within(final_mcr, float(capital.mcr.mcr), tolerance):
        return []
    return [
        QRTValidationMessage(
            "DNB005",
            "error",
            "S.28.01.01",
            "S.28.01 MCR must equal the MCR module output.",
        )
    ]


def _rule_dnb006(
    pack: dict[str, pd.DataFrame],
    *,
    financial: FinancialReportingResult,
    tolerance: float,
) -> list[QRTValidationMessage]:
    s0501 = pack.get("S.05.01.02", pd.DataFrame())
    income = financial.income_statement.set_index("line_item")["amount"].to_dict()
    checks = {
        "gross_written_premium": income["gross_written_premium"],
        "gross_earned_premium": income["gross_earned_premium"],
        "gross_claims_incurred": income["gross_claims_incurred"],
        "expenses": income["expenses"],
    }
    mismatches = [
        name
        for name, expected in checks.items()
        if not _within(_sum_column(s0501, name), float(expected), tolerance)
    ]
    if not mismatches:
        return []
    return [
        QRTValidationMessage(
            "DNB006",
            "warning",
            "S.05.01.02",
            f"S.05.01 premium, claims, or expenses totals differ from financial reporting: {', '.join(mismatches)}.",
        )
    ]


def _rule_dnb007(pack: dict[str, pd.DataFrame]) -> list[QRTValidationMessage]:
    s0101 = pack.get("S.01.01.02", pd.DataFrame())
    if s0101.empty or not {"template", "status"}.issubset(s0101.columns):
        return [
            QRTValidationMessage(
                "DNB007",
                "error",
                "S.01.01.02",
                "S.01.01 must explicitly flag not-applicable templates.",
            )
        ]
    status_by_template = s0101.set_index("template")["status"].to_dict()
    missing = [
        template
        for template, status in TEMPLATE_STATUS.items()
        if status == "not applicable" and status_by_template.get(template) != "not applicable"
    ]
    if not missing:
        return []
    return [
        QRTValidationMessage(
            "DNB007",
            "error",
            "S.01.01.02",
            f"Not-applicable templates are not explicitly flagged: {', '.join(missing)}.",
        )
    ]


def _rule_dnb008(pack: dict[str, pd.DataFrame]) -> list[QRTValidationMessage]:
    messages: list[QRTValidationMessage] = []
    for template, frame in pack.items():
        if frame.empty:
            continue
        columns = monetary_columns(frame)
        if not columns:
            continue
        if "currency" not in frame.columns or set(frame["currency"].dropna()) != {REPORTING_CURRENCY}:
            messages.append(
                QRTValidationMessage(
                    "DNB008",
                    "error",
                    template,
                    "Monetary QRT values must carry EUR currency.",
                )
            )
            continue
        for column in columns:
            values = pd.to_numeric(frame[column], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) and not np.allclose(values, np.round(values), atol=1e-9):
                messages.append(
                    QRTValidationMessage(
                        "DNB008",
                        "error",
                        template,
                        f"Monetary column {column} must be rounded according to export convention.",
                    )
                )
                break
    return messages


def _item_amount(frame: pd.DataFrame, item: str) -> float:
    if frame.empty or "item" not in frame.columns or "amount" not in frame.columns:
        return 0.0
    values = frame.loc[frame["item"] == item, "amount"]
    if values.empty:
        return 0.0
    return float(pd.to_numeric(values, errors="coerce").fillna(0.0).sum())


def _sum_column(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _within(actual: float, expected: float, tolerance: float) -> bool:
    return abs(float(actual) - float(expected)) <= float(tolerance)
