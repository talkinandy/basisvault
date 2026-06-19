"""Backtest tests — deterministic, synthetic funding data, fully offline."""
from __future__ import annotations

import pytest

from basisvault_engine.backtest import (
    FundingPoint,
    RatePoint,
    run_backtest,
    run_rwa_backtest,
)

_8H = 8 * 3600 * 1000
_DAY = 86400 * 1000


def series(rates: list[float]) -> list[FundingPoint]:
    return [FundingPoint(i * _8H, r, 65_000.0) for i, r in enumerate(rates)]


def const(rate: float, n: int) -> list[FundingPoint]:
    return series([rate] * n)


def test_sustained_positive_funding_stays_deployed_and_earns():
    res = run_backtest(const(0.0005, 300), cost_bps=0.0)  # ~55%/yr annualized
    assert res.opens == 1 and res.unwinds == 0      # opens once, never churns
    assert res.apy > 0.0
    assert res.pct_time_deployed > 0.95
    assert res.max_drawdown < 0.001                 # pure positive carry, no dd


def test_sustained_negative_funding_stays_flat_and_preserves_capital():
    res = run_backtest(const(-0.0005, 300), cost_bps=2.0)
    assert res.opens == 0                            # sign guard never opens
    assert res.pct_time_deployed == 0.0
    assert res.nav_final == res.nav_start           # no accrual, no costs
    # naive always-on would have bled and drawn down
    assert res.naive_always_on_apy < 0.0
    assert res.naive_always_on_max_drawdown > res.max_drawdown


def test_trailing_signal_ignores_single_negative_blip():
    # mostly positive with one negative interval — EMA stays positive => no unwind
    rates = [0.0005] * 50 + [-0.001] + [0.0005] * 50
    res = run_backtest(series(rates), cost_bps=2.0)
    assert res.unwinds == 0                          # didn't whipsaw on the blip
    assert res.opens == 1


def test_strategy_drawdown_not_worse_than_naive():
    # regime flip: long positive run, then sustained negative
    rates = [0.0006] * 150 + [-0.0006] * 150
    res = run_backtest(series(rates), cost_bps=2.0)
    assert res.unwinds >= 1                          # guard exits when funding flips
    assert res.max_drawdown <= res.naive_always_on_max_drawdown


def test_needs_two_points():
    with pytest.raises(ValueError):
        run_backtest(const(0.0005, 1))


def test_deterministic():
    data = series([0.0005, -0.0002, 0.0007] * 40)
    assert run_backtest(data) == run_backtest(data)


# --- RWA allocation backtest ---
def rates(repo: float, mmf: float, days: int) -> list[RatePoint]:
    return [RatePoint(i * _DAY, repo, mmf) for i in range(days)]


def test_rwa_positive_rates_earn_with_no_drawdown():
    res = run_rwa_backtest(rates(0.05, 0.045, 365), cost_bps=1.0)
    assert res.apy > 0.0
    assert res.max_drawdown == 0.0           # positive carry, capital-preserving
    assert 0.90 <= res.pct_deployed <= 0.96  # ~95% deployed (5% cash buffer)
    assert res.rebalances >= 1
    # APY tracks the blended deployed yield, net of small turnover cost
    assert abs(res.apy - res.avg_blended_yield) < 0.01


def test_rwa_zero_rates_no_deployment_no_growth():
    res = run_rwa_backtest(rates(0.0, 0.0, 200))
    assert res.nav_final == res.nav_start
    assert res.pct_deployed == 0.0
    assert res.apy == 0.0


def test_rwa_needs_two_points():
    import pytest
    with pytest.raises(ValueError):
        run_rwa_backtest(rates(0.05, 0.045, 1))
