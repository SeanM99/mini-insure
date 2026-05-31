from __future__ import annotations

import pytest

from miniinsure.mcr import calculate_mcr


def test_mcr_floor_and_lower_corridor() -> None:
    result = calculate_mcr(nwp=1_000_000.0, net_claims_be=1_000_000.0, scr=10_000_000.0)

    assert result.mcr_linear == pytest.approx(260_000.0)
    assert result.mcr_combined == pytest.approx(2_500_000.0)
    assert result.mcr == pytest.approx(4_000_000.0)


def test_mcr_upper_corridor() -> None:
    result = calculate_mcr(nwp=30_000_000.0, net_claims_be=1_000_000.0, scr=10_000_000.0)

    assert result.mcr_linear == pytest.approx(4_900_000.0)
    assert result.mcr_combined == pytest.approx(4_500_000.0)
    assert result.mcr == pytest.approx(4_500_000.0)


def test_mcr_inside_corridor() -> None:
    result = calculate_mcr(nwp=20_000_000.0, net_claims_be=3_000_000.0, scr=10_000_000.0)

    assert result.mcr_linear == pytest.approx(3_500_000.0)
    assert result.mcr_combined == pytest.approx(3_500_000.0)
    assert result.mcr == pytest.approx(4_000_000.0)
