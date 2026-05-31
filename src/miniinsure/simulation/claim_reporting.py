"""Claim reporting delay simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd

REPORTING_DELAY_MEAN_DAYS = {
    "liability_property_damage": 7,
    "own_damage_attritional": 5,
    "theft_fire": 3,
    "attritional_bi": 18,
    "large_bi": 28,
    "catastrophe_allocated": 4,
}


def apply_reporting_delay(
    claims: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Add report dates that cannot precede accident dates."""
    reported = claims.copy()
    if reported.empty:
        reported["report_date"] = pd.Series(dtype="datetime64[ns]")
        return reported

    means = reported["claim_type"].map(REPORTING_DELAY_MEAN_DAYS).fillna(7).astype(float)
    delay = rng.gamma(shape=2.0, scale=means / 2.0).round().astype(int)
    delay = np.maximum(delay, 0)
    reported["report_date"] = pd.to_datetime(reported["accident_date"]) + pd.to_timedelta(delay, unit="D")
    return reported
