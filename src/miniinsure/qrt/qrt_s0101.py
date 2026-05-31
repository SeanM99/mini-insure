"""Mock S.01.01.02 content-of-submission template."""

from __future__ import annotations

import pandas as pd

from miniinsure.qrt.mappings import applicability_matrix


def generate() -> pd.DataFrame:
    """Generate the mock content-of-submission matrix."""
    return applicability_matrix()
