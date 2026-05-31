"""Mock S.06.03.01 derivatives template."""

from __future__ import annotations

import pandas as pd


def generate() -> pd.DataFrame:
    """Generate a no-derivatives marker row for the conditional template."""
    return pd.DataFrame(
        [
            {
                "template_status": "conditional",
                "derivative_count": 0,
                "message": "No derivatives are modelled in MiniInsure Europe NL.",
                "source_field": "project scope",
            }
        ]
    )
