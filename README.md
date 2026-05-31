# MiniInsure Europe NL

MiniInsure Europe NL is an educational Solvency II-style actuarial platform for a synthetic Netherlands-based motor insurer. This first phase establishes the modular monolith foundation, a placeholder Streamlit entry point, and audit documentation for later actuarial modules.

## Scope

- Synthetic Netherlands motor insurer context.
- Valuation date: 2026-12-31.
- Reporting quarter: 2026 Q4.
- Actuarial and business logic will live under `src/miniinsure`.
- Streamlit UI files live under `app` and only handle UI controls, scenario state, cached calls, formatting, charts, and downloads.

## Educational Limitation

This project is for education and demonstration only. It is not actuarial advice, regulatory advice, financial reporting software, or a production risk system.

Real XBRL and real regulatory filing are out of scope. Any future QRT-style output must be clearly marked as mock/QRT-shaped only and must not be represented as an official Solvency II filing.

## Install

```bash
pip install -e .
```

## Test

```bash
pytest
```

## Run The App

```bash
streamlit run app/Home.py
```

## Streamlit Community Cloud Deployment

- Repository: `SeanM99/mini-insure`
- Branch: `main`
- Main file path: `app/Home.py`
- Python version: Python 3.12 or later
- Dependencies: install from `pyproject.toml`

Generated outputs are educational and mock-only. QRT-shaped downloads are not real regulatory filings, and the app does not produce real XBRL.
