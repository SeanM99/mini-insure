"""Minimum Capital Requirement calculations."""

from __future__ import annotations

from dataclasses import dataclass

MCR_ABSOLUTE_FLOOR = 4_000_000.0


@dataclass(frozen=True)
class MCRResult:
    """MCR calculation result."""

    mcr_linear: float
    mcr_combined: float
    mcr: float
    lower_corridor: float
    upper_corridor: float


def calculate_mcr(
    *,
    nwp: float,
    net_claims_be: float,
    scr: float,
    absolute_floor: float = MCR_ABSOLUTE_FLOOR,
) -> MCRResult:
    """Calculate MCR using the required floor and SCR corridor."""
    scr = max(float(scr), 0.0)
    mcr_linear = 0.16 * max(float(nwp), 0.0) + 0.10 * max(float(net_claims_be), 0.0)
    lower = 0.25 * scr
    upper = 0.45 * scr
    mcr_combined = min(upper, max(lower, mcr_linear))
    return MCRResult(
        mcr_linear=float(mcr_linear),
        mcr_combined=float(mcr_combined),
        mcr=float(max(mcr_combined, absolute_floor)),
        lower_corridor=float(lower),
        upper_corridor=float(upper),
    )
