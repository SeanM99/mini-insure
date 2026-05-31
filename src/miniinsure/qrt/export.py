"""Mock QRT pack generation and export helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd

from miniinsure.assumptions import Assumptions, stable_assumption_hash
from miniinsure.qrt import (
    qrt_s0101,
    qrt_s0102,
    qrt_s0201,
    qrt_s0501,
    qrt_s0602,
    qrt_s0603,
    qrt_s0801,
    qrt_s1701,
    qrt_s2301,
    qrt_s2801,
)
from miniinsure.qrt.mappings import export_names, mapping_table
from miniinsure.qrt.validation import has_blocking_errors, validate_qrt_pack
from miniinsure.reporting import FinancialReportingResult
from miniinsure.risk_engine.capital_workflow import CapitalWorkflowResult


def generate_qrt_pack(
    *,
    capital: CapitalWorkflowResult,
    financial: FinancialReportingResult,
    assumptions: Assumptions,
    scenario_name: str,
) -> dict[str, pd.DataFrame]:
    """Generate the complete mock QRT-shaped pack."""
    assumption_hash = stable_assumption_hash(assumptions)
    return {
        "S.01.01.02": qrt_s0101.generate(),
        "S.01.02.01": qrt_s0102.generate(
            assumptions,
            scenario_name=scenario_name,
            assumption_hash=assumption_hash,
        ),
        "S.02.01.02": qrt_s0201.generate(capital, financial),
        "S.05.01.02": qrt_s0501.generate(financial),
        "S.06.02.01": qrt_s0602.generate(capital),
        "S.06.03.01": qrt_s0603.generate(),
        "S.08.01.01": qrt_s0801.generate(),
        "S.17.01.02": qrt_s1701.generate(capital),
        "S.23.01.01": qrt_s2301.generate(capital, financial),
        "S.28.01.01": qrt_s2801.generate(capital),
        "Mappings": mapping_table(),
    }


def qrt_pack_to_excel_bytes(pack: dict[str, pd.DataFrame]) -> bytes:
    """Serialize the mock QRT pack to an Excel workbook."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, frame in pack.items():
            frame.to_excel(writer, sheet_name=_sheet_name(sheet_name), index=False)
    return buffer.getvalue()


def qrt_pack_to_zip_bytes(
    *,
    pack: dict[str, pd.DataFrame],
    board_report_markdown: str,
    scenario_metadata_json: str,
    scenario_name: str,
) -> bytes:
    """Serialize the mock QRT workbook, board report, and metadata to a ZIP file."""
    names = export_names(scenario_name)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(names.qrt_xlsx, qrt_pack_to_excel_bytes(pack))
        archive.writestr(names.board_report_md, board_report_markdown)
        archive.writestr(names.metadata_json, scenario_metadata_json)
    return buffer.getvalue()


def export_qrt_pack_to_xlsx(
    pack: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    """Write a mock QRT Excel workbook to disk."""
    path = Path(output_path)
    path.write_bytes(qrt_pack_to_excel_bytes(pack))
    return path


def export_qrt_pack_to_zip(
    *,
    pack: dict[str, pd.DataFrame],
    board_report_markdown: str,
    scenario_metadata_json: str,
    scenario_name: str,
    output_dir: str | Path,
    capital: CapitalWorkflowResult,
    financial: FinancialReportingResult,
) -> Path:
    """Write a mock QRT ZIP to disk after blocking validation errors."""
    validation = validate_qrt_pack(pack, capital=capital, financial=financial)
    if has_blocking_errors(validation):
        raise ValueError("QRT export blocked by validation errors")
    names = export_names(scenario_name)
    path = Path(output_dir) / names.qrt_zip
    path.write_bytes(
        qrt_pack_to_zip_bytes(
            pack=pack,
            board_report_markdown=board_report_markdown,
            scenario_metadata_json=scenario_metadata_json,
            scenario_name=scenario_name,
        )
    )
    return path


def _sheet_name(template_name: str) -> str:
    return template_name[:31]
