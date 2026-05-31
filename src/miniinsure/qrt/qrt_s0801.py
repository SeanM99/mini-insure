"""Mock S.08.01.01 empty derivatives template."""

from __future__ import annotations

import pandas as pd


def generate() -> pd.DataFrame:
    """Generate an empty but explicit derivatives template marker."""
    return pd.DataFrame(
        columns=[
            "derivative_id",
            "instrument_type",
            "notional_amount",
            "market_value",
            "currency",
            "source_field",
        ]
    )
