"""Honest backtest of the delta-neutral carry strategy over real funding history.

Validates the *strategy* (entry/exit thresholds, sign-guard unwind, rebalance
band) on historical BTC perp funding — a transparent proxy for CBTC (which tracks
BTC; clean CBTC perp history isn't public yet). Honest by construction:

  - NON-LOOKAHEAD: the position held during interval t was decided using funding
    observed up to t-1. We accrue interval t's funding on the carried position,
    THEN decide for t+1 using funding[t]. No future information is used.
  - REAL COSTS: every open/resize/unwind pays a trading cost in bps on routed
    notional, so churn is penalised (validates the rebalance band).
  - CARRY ONLY ON THE SHORT LEG: the vault is short the perp, so it receives
    funding when the rate is positive and pays when negative; the long spot leg
    cancels delta and earns ~0 funding. No basis term here (we only have funding)
    — so this UNDERSTATES the real strategy, which also captures basis.

Pure functions of (data, params) — fully offline-testable with synthetic data.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Action, MarketSnapshot, PositionState, Underlying, VaultState
from .strategy import StrategyParams, decide

INTERVALS_PER_YEAR = 3 * 365  # 8h funding => 3/day
_MS_PER_YEAR = 365 * 24 * 3600 * 1000


@dataclass(frozen=True)
class FundingPoint:
    time: int          # ms epoch
    funding_rate: float  # per 8h interval, fraction
    mark_price: float


@dataclass(frozen=True)
class BacktestResult:
    start: int
    end: int
    years: float
    nav_start: float
    nav_final: float
    total_return: float
    apy: float
    max_drawdown: float
    pct_time_deployed: float
    intervals: int
    opens: int
    resizes: int
    unwinds: int
    gross_funding: float       # funding accrued (can be negative on the lag interval)
    total_costs: float
    naive_always_on_apy: float          # contrast: short every interval, no guard
    naive_always_on_max_drawdown: float  # ...and the risk it carries
    nav_curve: list[list[float]]  # [ [time_ms, nav], ... ] downsampled


def load_funding(path: str | Path) -> list[FundingPoint]:
    rows = json.loads(Path(path).read_text())
    return [FundingPoint(int(r["time"]), float(r["fundingRate"]),
                         float(r.get("markPrice") or 0.0)) for r in rows]


def _max_drawdown(navs: list[float]) -> float:
    peak = navs[0]
    mdd = 0.0
    for v in navs:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak > 0 else 0.0)
    return mdd


def run_backtest(
    data: list[FundingPoint],
    params: StrategyParams = StrategyParams(),
    nav_start: float = 1_000_000.0,
    cost_bps: float = 2.0,            # trading cost per unit notional routed
    funding_ema_intervals: int = 9,   # ~3 days; act on TRAILING funding, not noise
    curve_points: int = 240,
) -> BacktestResult:
    if len(data) < 2:
        raise ValueError("need at least 2 funding points")

    nav = nav_start
    short_notional = 0.0              # current short-leg notional (0 == flat)
    opens = resizes = unwinds = deployed = 0
    gross_funding = total_costs = 0.0
    navs: list[float] = []
    times: list[int] = []
    cost = cost_bps / 10_000.0
    ema: float | None = None
    alpha = 2.0 / (funding_ema_intervals + 1.0)

    for pt in data:
        # 1) accrue THIS interval's ACTUAL funding on the carried short leg
        if short_notional > 0:
            gain = short_notional * pt.funding_rate
            nav += gain
            gross_funding += gain
            deployed += 1

        navs.append(nav)
        times.append(pt.time)

        # 2) update the TRAILING funding signal with funding observed up to now
        #    (non-lookahead), then decide for the next interval on the smoothed
        #    signal — avoids whipsawing on single-interval sign flips.
        ema = pt.funding_rate if ema is None else alpha * pt.funding_rate + (1 - alpha) * ema
        market = MarketSnapshot(
            underlying=Underlying.CBTC,
            price=pt.mark_price or 1.0,
            funding_rate=ema * INTERVALS_PER_YEAR,  # annualized trailing funding
            basis=0.0,
            age_seconds=0.0,
        )
        vault = VaultState("bt", Underlying.CBTC, total_assets=nav, total_shares=nav_start)
        position = None if short_notional <= 0 else PositionState(
            "bt-pos", Underlying.CBTC, short_notional, short_notional,
            pt.mark_price or 1.0)

        d = decide(market, vault, position, params)
        if d.action is Action.PROPOSE and d.plan is not None:
            routed = 2.0 * d.plan.notional if short_notional == 0 else \
                abs(d.plan.notional - short_notional) * 2.0
            fee = routed * cost
            nav -= fee
            total_costs += fee
            if short_notional == 0:
                opens += 1
            else:
                resizes += 1
            short_notional = d.plan.notional
        elif d.action is Action.UNWIND and short_notional > 0:
            fee = 2.0 * short_notional * cost
            nav -= fee
            total_costs += fee
            unwinds += 1
            short_notional = 0.0

    years = (data[-1].time - data[0].time) / _MS_PER_YEAR
    total_return = nav / nav_start - 1.0
    apy = (nav / nav_start) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    naive_apy, naive_mdd = _naive_stats(data, nav_start)

    return BacktestResult(
        start=data[0].time, end=data[-1].time, years=round(years, 3),
        nav_start=nav_start, nav_final=round(nav, 2),
        total_return=round(total_return, 6), apy=round(apy, 6),
        max_drawdown=round(_max_drawdown(navs), 6),
        pct_time_deployed=round(deployed / len(data), 4),
        intervals=len(data), opens=opens, resizes=resizes, unwinds=unwinds,
        gross_funding=round(gross_funding, 2), total_costs=round(total_costs, 2),
        naive_always_on_apy=round(naive_apy, 6),
        naive_always_on_max_drawdown=round(naive_mdd, 6),
        nav_curve=_downsample(times, navs, curve_points),
    )


def _naive_stats(data: list[FundingPoint], nav_start: float) -> tuple[float, float]:
    """Contrast: always short the perp every interval (no sign guard, no costs).
    Returns (apy, max_drawdown). Shows the negative-funding bleed + drawdown the
    sign guard avoids — the risk-adjusted case for the strategy.
    """
    nav = nav_start
    navs = [nav]
    for pt in data:
        nav += nav_start * pt.funding_rate
        navs.append(nav)
    years = (data[-1].time - data[0].time) / _MS_PER_YEAR
    apy = (nav / nav_start) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    return apy, _max_drawdown(navs)


def _downsample(times: list[int], navs: list[float], n: int) -> list[list[float]]:
    if len(times) <= n:
        return [[float(t), round(v, 2)] for t, v in zip(times, navs)]
    step = len(times) / n
    out = []
    for k in range(n):
        i = int(k * step)
        out.append([float(times[i]), round(navs[i], 2)])
    out.append([float(times[-1]), round(navs[-1], 2)])
    return out


def main() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "btc_funding.json"
    out_path = data_path.parent / "backtest_result.json"
    data = load_funding(data_path)
    res = run_backtest(data)
    out_path.write_text(json.dumps(asdict(res)))
    print(f"backtest: {res.years:.2f}y  APY {res.apy:.2%}  "
          f"maxDD {res.max_drawdown:.2%}  deployed {res.pct_time_deployed:.0%}  "
          f"opens/resizes/unwinds {res.opens}/{res.resizes}/{res.unwinds}")
    print(f"  naive always-on: APY {res.naive_always_on_apy:.2%}  "
          f"maxDD {res.naive_always_on_max_drawdown:.2%}  "
          f"(strategy trades a little APY for ~{res.naive_always_on_max_drawdown/max(res.max_drawdown,1e-9):.0f}x less drawdown)")
    print(f"  -> {out_path.relative_to(out_path.parent.parent)}")


if __name__ == "__main__":
    main()
