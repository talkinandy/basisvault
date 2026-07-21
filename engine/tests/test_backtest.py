"""Backtest tests — deterministic, synthetic funding data, fully offline."""
from __future__ import annotations

import pytest

import pytest

from basisvault_engine.backtest import (
    FundingPoint,
    RatePoint,
    capital_efficiency,
    optimal_leverage,
    run_backtest,
    run_hl_carry_backtest,
    run_rwa_backtest,
    run_stacked_backtest,
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
    with pytest.raises(ValueError):
        run_rwa_backtest(rates(0.05, 0.045, 1))


# --- stacked backtest (RWA-collateralized carry) ---
def funding_const(fr: float, days: int) -> list[FundingPoint]:
    return [FundingPoint(i * _8H, fr, 65_000.0) for i in range(3 * days)]


def rates_const(repo: float, mmf: float, days: int) -> list[RatePoint]:
    return [RatePoint(d * _DAY, repo, mmf) for d in range(days)]


def test_stacked_positive_funding_stacks_collateral_plus_funding():
    res = run_stacked_backtest(
        funding_const(0.0001, 365), rates_const(0.05, 0.045, 365),
        carry_fraction=0.6, cost_bps=0.0)
    # collateral earns ~ the T-bill (mmf) rate; funding adds on top
    assert res.carry_collateral_apy == pytest.approx(0.045, abs=0.006)
    assert res.carry_funding_apy > 0.05
    # the stacking: carry sleeve clears the pure-RWA sleeve
    assert res.carry_sleeve_apy > res.rwa_sleeve_apy
    assert res.rwa_sleeve_apy == pytest.approx(0.0475, abs=0.01)  # (repo+mmf)/2
    assert res.max_drawdown < 0.005                                # market-neutral
    assert res.annual_range[0] <= res.annual_range[1] <= res.annual_range[2]


def test_stacked_negative_funding_falls_back_to_collateral_only():
    res = run_stacked_backtest(
        funding_const(-0.0001, 365), rates_const(0.05, 0.045, 365), cost_bps=1.0)
    assert res.carry_funding_apy == pytest.approx(0.0, abs=0.002)   # sign guard
    assert res.pct_carry_deployed < 0.05
    assert res.carry_sleeve_apy == pytest.approx(res.carry_collateral_apy, abs=0.01)


def test_stacked_needs_overlap():
    with pytest.raises(ValueError):
        run_stacked_backtest([FundingPoint(0, 0.0001, 65_000.0)],
                             [RatePoint(0, 0.05, 0.045)])


# --- HL carry backtest (the hero: short HL perp + long cBTC/cETH on Canton) ---
_1H = 3600 * 1000


def hourly(rate: float, hours: int, start: int = 0) -> list[FundingPoint]:
    return [FundingPoint(start + i * _1H, rate, 0.0) for i in range(hours)]


def test_optimal_leverage_matches_liquidation_buffer():
    # L <= 1/(maint + move): 1/(0.02+0.15) = 5.88 -> 5
    assert optimal_leverage(0.02, 0.15, 10) == 5
    assert optimal_leverage(0.02, 0.15, 3) == 3       # exchange cap wins
    assert capital_efficiency(5) == pytest.approx(5 / 6)


def test_carry_positive_funding_deploys_and_earns_at_capital_efficiency():
    hours = 24 * 365
    rate = 0.10 / (24 * 365)                          # 10%/yr paid hourly
    res = run_hl_carry_backtest({"CBTC": hourly(rate, hours)}, cost_bps=0.0)
    s = res.sleeves[0]
    assert s.opens == 1 and s.unwinds == 0            # steady regime, no churn
    # earns funding on eff (~83%) of capital, compounding hourly
    assert res.apy == pytest.approx(0.10 * res.capital_efficiency, abs=0.01)
    assert res.max_drawdown == 0.0


def test_carry_negative_funding_never_deploys():
    hours = 24 * 90
    rate = -0.10 / (24 * 365)
    res = run_hl_carry_backtest({"CBTC": hourly(rate, hours)})
    s = res.sleeves[0]
    assert s.opens == 0 and s.pct_time_deployed == 0.0
    assert res.nav_final == res.nav_start             # sign guard: never pays


def test_carry_sign_guard_unwinds_on_regime_flip():
    hours = 24 * 60
    pos = 0.20 / (24 * 365)                           # rich funding, then flips
    neg = -0.05 / (24 * 365)
    data = hourly(pos, hours) + hourly(neg, hours, start=hours * _1H)
    res = run_hl_carry_backtest({"CBTC": data}, cost_bps=0.0)
    s = res.sleeves[0]
    assert s.opens == 1 and s.unwinds == 1            # exited when trailing decayed
    # kept most of the positive-regime gains (paid only the trailing-window lag)
    assert res.nav_final > res.nav_start * 1.02


def test_carry_costs_are_charged_on_both_legs():
    hours = 24 * 365
    rate = 0.10 / (24 * 365)
    free = run_hl_carry_backtest({"CBTC": hourly(rate, hours)}, cost_bps=0.0)
    paid = run_hl_carry_backtest({"CBTC": hourly(rate, hours)}, cost_bps=10.0)
    assert paid.nav_final < free.nav_final
    assert paid.sleeves[0].total_costs > 0.0


def test_carry_blends_two_assets_and_reports_range():
    hours = 24 * 400
    btc = hourly(0.15 / (24 * 365), hours)
    eth = hourly(0.05 / (24 * 365), hours)
    res = run_hl_carry_backtest({"CBTC": btc, "CETH": eth}, cost_bps=0.0)
    assert len(res.sleeves) == 2
    apys = {s.asset: s.apy for s in res.sleeves}
    assert apys["CBTC"] > apys["CETH"]                # sleeves independent
    assert apys["CETH"] < res.apy < apys["CBTC"]      # blend in between
    assert res.annual_range[0] <= res.annual_range[1] <= res.annual_range[2]
    assert res.today_apy >= 0.0


def test_carry_needs_data():
    with pytest.raises(ValueError):
        run_hl_carry_backtest({})
    with pytest.raises(ValueError):
        run_hl_carry_backtest({"CBTC": hourly(0.0001, 1)})
