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

from .allocator import AllocatorParams, blended_yield, needs_rebalance, target_allocation
from .models import (
    Action,
    MarketSnapshot,
    PositionState,
    Underlying,
    VaultState,
    YieldQuote,
    YieldSourceKind,
)
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


# --------------------------------------------------------------------------- #
# RWA allocation backtest (the hero) — replay the allocator over real repo/MMF
# rate history. Honest: yield is the blended rate ACTUALLY earned each day on the
# deployed allocation; rebalances pay a turnover cost; idle cash earns 0.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RatePoint:
    time: int          # ms epoch (daily)
    repo_rate: float   # annualized fraction (SOFR proxy)
    mmf_rate: float    # annualized fraction (3M T-bill proxy)


@dataclass(frozen=True)
class RwaBacktestResult:
    start: int
    end: int
    years: float
    nav_start: float
    nav_final: float
    total_return: float
    apy: float
    max_drawdown: float
    avg_blended_yield: float
    pct_deployed: float
    rebalances: int
    total_costs: float
    avg_repo_rate: float
    avg_mmf_rate: float
    nav_curve: list[list[float]]


def load_rates(path: str | Path) -> list[RatePoint]:
    rows = json.loads(Path(path).read_text())
    return [RatePoint(int(r["time"]), float(r["repo_rate"]), float(r["mmf_rate"]))
            for r in rows]


def run_rwa_backtest(
    data: list[RatePoint],
    params: AllocatorParams = AllocatorParams(),
    nav_start: float = 1_000_000.0,
    cost_bps: float = 1.0,            # turnover cost when the portfolio shifts
    curve_points: int = 240,
) -> RwaBacktestResult:
    if len(data) < 2:
        raise ValueError("need at least 2 rate points")

    nav = nav_start
    current: dict[str, float] = {}    # asset -> notional
    rates_by_asset: dict[str, float] = {}
    rebalances = 0
    total_costs = 0.0
    by_sum = deployed_sum = 0.0
    cost = cost_bps / 10_000.0
    navs: list[float] = []
    times: list[int] = []

    for i, pt in enumerate(data):
        quotes = [
            YieldQuote(YieldSourceKind.REPO, "USTB-3M", pt.repo_rate, 1.0),
            YieldQuote(YieldSourceKind.MMF, "MMF-USD", pt.mmf_rate, 1.0),
        ]
        targets = target_allocation(quotes, nav, params)
        rates_by_asset = {t.asset: t.annualized_rate for t in targets}

        if needs_rebalance(current, targets, params):
            tgt = {t.asset: t.target_notional for t in targets}
            turnover = sum(abs(tgt.get(a, 0.0) - current.get(a, 0.0))
                           for a in set(current) | set(tgt))
            fee = turnover * cost
            nav -= fee
            total_costs += fee
            current = tgt
            rebalances += 1

        # accrue today's yield on the deployed allocation (1 day)
        dt_years = ((data[i + 1].time - pt.time) / _MS_PER_YEAR) if i + 1 < len(data) else 0.0
        day_gain = sum(current.get(a, 0.0) * rates_by_asset.get(a, 0.0)
                       for a in current) * dt_years
        nav += day_gain

        deployed = sum(current.values())
        by_sum += blended_yield(targets, nav)
        deployed_sum += deployed / nav if nav > 0 else 0.0
        navs.append(nav)
        times.append(pt.time)

    years = (data[-1].time - data[0].time) / _MS_PER_YEAR
    apy = (nav / nav_start) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    n = len(data)
    return RwaBacktestResult(
        start=data[0].time, end=data[-1].time, years=round(years, 3),
        nav_start=nav_start, nav_final=round(nav, 2),
        total_return=round(nav / nav_start - 1.0, 6), apy=round(apy, 6),
        max_drawdown=round(_max_drawdown(navs), 6),
        avg_blended_yield=round(by_sum / n, 6),
        pct_deployed=round(deployed_sum / n, 4),
        rebalances=rebalances, total_costs=round(total_costs, 2),
        avg_repo_rate=round(sum(p.repo_rate for p in data) / n, 6),
        avg_mmf_rate=round(sum(p.mmf_rate for p in data) / n, 6),
        nav_curve=_downsample(times, navs, curve_points),
    )


# --------------------------------------------------------------------------- #
# HL CARRY backtest (THE HERO this phase) — the production BasisYield cash-and-
# carry ported to Canton's live asset menu: SHORT the BTC/ETH perp on
# Hyperliquid (receive funding), LONG cBTC/cETH spot custodied on Canton
# (cancel price). Mechanism mirrors the live fundingcarry engine:
#   - trailing funding APR over a rolling window (never a single print),
#   - ENTER when trailing APR >= entry_apr, UNWIND BOTH legs below exit_apr
#     (the funding-sign guard: a short must never pay through a negative regime),
#   - perp leverage L chosen so the liquidation distance survives a configured
#     adverse up-move:  L <= 1/(maint + move); capture on deployed capital is
#     funding × L/(L+1) (spot 1x + margin 1/L) — the capital-efficiency term.
# Honest by construction: REAL Hyperliquid funding prints (variable intervals,
# annualized by actual elapsed time), realized funding only, both-legs trading
# costs on every open/unwind, non-lookahead (decide on the trailing window,
# accrue the NEXT print).
# --------------------------------------------------------------------------- #
HOURS_PER_YEAR = 24.0 * 365.0


def optimal_leverage(maint_margin: float, max_adverse_move: float,
                     max_leverage: int) -> int:
    """Highest perp leverage whose liquidation distance (~1/L - maint) still
    survives an adverse up-move before a rebalance: L <= 1/(maint + move)."""
    if maint_margin + max_adverse_move <= 0:
        return max_leverage
    return max(1, min(max_leverage, int(1.0 / (maint_margin + max_adverse_move))))


def capital_efficiency(leverage: int) -> float:
    """Fraction of deployed capital earning funding: spot uses 1x notional,
    perp margin notional/L, so earning_notional/capital = L/(L+1)."""
    return leverage / (leverage + 1.0)


@dataclass(frozen=True)
class CarrySleeveStats:
    asset: str                 # "CBTC" / "CETH"
    apy: float
    gross_funding: float
    total_costs: float
    opens: int
    unwinds: int
    pct_time_deployed: float
    avg_funding_annual: float  # mean annualized funding over the whole window


@dataclass(frozen=True)
class HlCarryBacktestResult:
    start: int
    end: int
    years: float
    nav_start: float
    nav_final: float
    apy: float                    # blended two-asset portfolio
    max_drawdown: float
    leverage: int
    capital_efficiency: float
    sleeves: list[CarrySleeveStats]
    annual_range: list[float]     # [min, median, max] rolling-1y blended return
    today_apy: float              # trailing-1y blended (current regime)
    nav_curve: list[list[float]]


def _trailing_apr(window: list[FundingPoint]) -> float | None:
    """Annualized funding over a trailing slice: sum of prints / elapsed time.
    None with fewer than 3 prints (mirrors the live engine's data floor)."""
    if len(window) < 3:
        return None
    span_years = (window[-1].time - window[0].time) / _MS_PER_YEAR
    if span_years <= 0:
        return None
    return sum(p.funding_rate for p in window) / span_years


def run_hl_carry_backtest(
    funding_by_asset: dict[str, list[FundingPoint]],
    nav_start: float = 1_000_000.0,
    entry_apr: float = 0.05,          # production cash_carry.entry_apr
    exit_apr: float = 0.02,           # production cash_carry.exit_apr
    window_h: int = 72,               # trailing funding window (3d: cuts churn)
    maint_margin: float = 0.02,
    max_adverse_move: float = 0.15,
    max_leverage: int = 10,
    cost_bps: float = 2.0,            # per unit notional routed, both legs
    curve_points: int = 260,
) -> HlCarryBacktestResult:
    assets = sorted(funding_by_asset)
    if not assets:
        raise ValueError("need at least one funding series")
    lev = optimal_leverage(maint_margin, max_adverse_move, max_leverage)
    eff = capital_efficiency(lev)
    cost = cost_bps / 10_000.0

    sleeves: list[CarrySleeveStats] = []
    curves: dict[str, tuple[list[int], list[float]]] = {}

    for asset in assets:
        data = funding_by_asset[asset]
        if len(data) < 2:
            raise ValueError(f"{asset}: need at least 2 funding points")
        nav = nav_start / len(assets)
        nav0 = nav
        deployed = False
        opens = unwinds = on = 0
        gross = costs = 0.0
        navs: list[float] = []
        times: list[int] = []
        window: list[FundingPoint] = []
        win_ms = window_h * 3600 * 1000

        for pt in data:
            # 1) accrue THIS print's actual funding on the carried position
            #    (decided on data strictly before it — non-lookahead)
            if deployed:
                gain = nav * eff * pt.funding_rate
                nav += gain
                gross += gain
                on += 1
            navs.append(nav)
            times.append(pt.time)

            # 2) update the trailing window, then decide for the next print
            window.append(pt)
            while window and window[0].time < pt.time - win_ms:
                window.pop(0)
            apr = _trailing_apr(window)
            if apr is None:
                continue
            if not deployed and apr >= entry_apr:
                fee = nav * eff * 2.0 * cost      # open both legs
                nav -= fee; costs += fee
                deployed = True; opens += 1
            elif deployed and apr < exit_apr:
                fee = nav * eff * 2.0 * cost      # unwind both legs
                nav -= fee; costs += fee
                deployed = False; unwinds += 1

        years = (data[-1].time - data[0].time) / _MS_PER_YEAR
        total_ann = sum(p.funding_rate for p in data) / years if years > 0 else 0.0
        sleeves.append(CarrySleeveStats(
            asset=asset, apy=round((nav / nav0) ** (1.0 / years) - 1.0, 6),
            gross_funding=round(gross, 2), total_costs=round(costs, 2),
            opens=opens, unwinds=unwinds,
            pct_time_deployed=round(on / len(data), 4),
            avg_funding_annual=round(total_ann, 6)))
        curves[asset] = (times, navs)

    # blend sleeves on the union timeline (step-interpolate each sleeve)
    all_times = sorted(set(t for ts, _ in curves.values() for t in ts))
    idx = {a: 0 for a in assets}
    blended: list[float] = []
    for t in all_times:
        total = 0.0
        for a in assets:
            ts, ns = curves[a]
            i = idx[a]
            while i + 1 < len(ts) and ts[i + 1] <= t:
                i += 1
            idx[a] = i
            total += ns[i] if ts[i] <= t else nav_start / len(assets)
        blended.append(total)

    years = (all_times[-1] - all_times[0]) / _MS_PER_YEAR
    nav_final = blended[-1]
    apy = (nav_final / nav_start) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    # rolling 1-year blended returns (timestamp-based window) -> regime range
    year_ms = 365 * 24 * 3600 * 1000
    roll: list[float] = []
    j = 0
    for k in range(len(all_times)):
        while all_times[j] < all_times[k] - year_ms:
            j += 1
        if all_times[k] - all_times[j] >= int(0.98 * year_ms) and blended[j] > 0:
            roll.append(blended[k] / blended[j] - 1.0)
    today = roll[-1] if roll else apy
    roll_sorted = sorted(roll) if roll else [apy]
    rng = [round(roll_sorted[0], 6), round(roll_sorted[len(roll_sorted) // 2], 6),
           round(roll_sorted[-1], 6)]

    return HlCarryBacktestResult(
        start=all_times[0], end=all_times[-1], years=round(years, 3),
        nav_start=nav_start, nav_final=round(nav_final, 2),
        apy=round(apy, 6), max_drawdown=round(_max_drawdown(blended), 6),
        leverage=lev, capital_efficiency=round(eff, 4),
        sleeves=sleeves, annual_range=rng, today_apy=round(today, 6),
        nav_curve=_downsample(all_times, blended, curve_points),
    )


# --------------------------------------------------------------------------- #
# STACKED backtest — the BasisYield mechanism on Canton: RWA-collateralized carry.
# Two sleeves: (1) pure RWA (repo/MMF), (2) carry sleeve whose collateral is a
# tokenized T-bill (earns base yield ALWAYS) AND margins a delta-neutral crypto
# carry (collects funding when trailing funding is positive — sign-guarded).
# The collateral-yield stacking is the Canton edge Hyperliquid lacks (idle USDC
# earns 0 there). Honest: 1x notional (no leverage), realized funding only, real
# turnover costs; reports a data-driven rolling-1y range across regimes.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StackedBacktestResult:
    start: int
    end: int
    years: float
    nav_start: float
    nav_final: float
    apy: float                    # blended portfolio
    max_drawdown: float
    carry_fraction: float
    rwa_sleeve_apy: float
    carry_sleeve_apy: float       # collateral + funding
    carry_collateral_apy: float   # the T-bill base part of the carry sleeve
    carry_funding_apy: float      # the funding-carry part of the carry sleeve
    avg_funding_annual: float
    pct_carry_deployed: float
    annual_range: list[float]     # [min, median, max] rolling-1y blended return
    today_apy: float              # trailing-1y blended (current regime)
    nav_curve: list[list[float]]


def _carry_forward(funding: list[FundingPoint], rates: list[RatePoint]
                   ) -> list[tuple[float, float]]:
    """For each funding time, the most recent (repo, mmf) rate at or before it."""
    out: list[tuple[float, float]] = []
    j = 0
    repo = mmf = 0.0
    for f in funding:
        while j < len(rates) and rates[j].time <= f.time:
            repo, mmf = rates[j].repo_rate, rates[j].mmf_rate
            j += 1
        out.append((repo, mmf))
    return out


def run_stacked_backtest(
    funding: list[FundingPoint],
    rates: list[RatePoint],
    carry_fraction: float = 0.6,      # share of capital in the carry sleeve
    nav_start: float = 1_000_000.0,
    cost_bps: float = 1.0,
    funding_ema_intervals: int = 9,
    funding_entry: float = 0.02,      # annualized trailing funding to deploy carry
    curve_points: int = 260,
) -> StackedBacktestResult:
    # overlap window only (need both funding and a known rate)
    cf = _carry_forward(funding, rates)
    pairs = [(f, r) for f, r in zip(funding, cf) if r[0] > 0 or r[1] > 0]
    if len(pairs) < 2:
        raise ValueError("need overlapping funding + rate history")

    nav_rwa = nav_start * (1.0 - carry_fraction)
    nav_carry = nav_start * carry_fraction
    coll_gain = fund_gain = rwa_gain = 0.0
    deployed = 0
    cost = cost_bps / 10_000.0
    ema: float | None = None
    alpha = 2.0 / (funding_ema_intervals + 1.0)
    was_deployed = False
    navs: list[float] = []
    times: list[int] = []

    fps = [p[0] for p in pairs]
    for i, (f, (repo, mmf)) in enumerate(pairs):
        dt = ((fps[i + 1].time - f.time) / _MS_PER_YEAR) if i + 1 < len(pairs) else 0.0
        base = mmf            # tokenized T-bill collateral / MMF base
        rwa_base = (repo + mmf) / 2.0

        # pure RWA sleeve
        g = nav_rwa * rwa_base * dt
        nav_rwa += g; rwa_gain += g

        # carry sleeve: collateral always earns; funding when trailing-positive
        gc = nav_carry * base * dt
        nav_carry += gc; coll_gain += gc

        ema = f.funding_rate if ema is None else alpha * f.funding_rate + (1 - alpha) * ema
        deploy = ema * INTERVALS_PER_YEAR >= funding_entry
        if deploy != was_deployed:
            nav_carry -= nav_carry * cost   # turnover on (un)deploy
            was_deployed = deploy
        if deploy:
            gf = nav_carry * f.funding_rate
            nav_carry += gf; fund_gain += gf; deployed += 1

        navs.append(nav_rwa + nav_carry)
        times.append(f.time)

    years = (pairs[-1][0].time - pairs[0][0].time) / _MS_PER_YEAR
    nav_final = nav_rwa + nav_carry
    apy = (nav_final / nav_start) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    rwa0 = nav_start * (1.0 - carry_fraction)
    carry0 = nav_start * carry_fraction

    def _ann(gain: float, principal: float) -> float:
        return gain / principal / years if principal > 0 and years > 0 else 0.0

    # rolling 1-year blended returns -> honest regime range
    win = INTERVALS_PER_YEAR
    roll = sorted((navs[k] / navs[k - win] - 1.0)
                  for k in range(win, len(navs)) if navs[k - win] > 0)
    if roll:
        rng = [round(roll[0], 6), round(roll[len(roll) // 2], 6), round(roll[-1], 6)]
        today = round(roll[-1], 6)
    else:
        rng = [round(apy, 6)] * 3
        today = round(apy, 6)

    return StackedBacktestResult(
        start=pairs[0][0].time, end=pairs[-1][0].time, years=round(years, 3),
        nav_start=nav_start, nav_final=round(nav_final, 2),
        apy=round(apy, 6), max_drawdown=round(_max_drawdown(navs), 6),
        carry_fraction=carry_fraction,
        rwa_sleeve_apy=round((nav_rwa / rwa0) ** (1.0 / years) - 1.0, 6),
        carry_sleeve_apy=round((nav_carry / carry0) ** (1.0 / years) - 1.0, 6),
        carry_collateral_apy=round(_ann(coll_gain, carry0), 6),
        carry_funding_apy=round(_ann(fund_gain, carry0), 6),
        avg_funding_annual=round(sum(p[0].funding_rate for p in pairs) / len(pairs)
                                 * INTERVALS_PER_YEAR, 6),
        pct_carry_deployed=round(deployed / len(pairs), 4),
        annual_range=rng, today_apy=today,
        nav_curve=_downsample(times, navs, curve_points),
    )


def main() -> None:
    base = Path(__file__).resolve().parent.parent / "data"

    # THE HERO — real Hyperliquid funding, short BTC/ETH perp + long cBTC/cETH
    hl = {u: base / f"hl_{u.lower()}_funding.json" for u in ("BTC", "ETH")}
    if all(p.exists() for p in hl.values()):
        by_asset = {("CBTC" if u == "BTC" else "CETH"): load_funding(p)
                    for u, p in hl.items()}
        c = run_hl_carry_backtest(by_asset)
        (base / "hl_carry_backtest_result.json").write_text(json.dumps(asdict(c)))
        lo, med, hi = (x * 100 for x in c.annual_range)
        print(f"[HL CARRY hero] {c.years:.2f}y  APY {c.apy:.2%}  maxDD {c.max_drawdown:.2%}  "
              f"{c.leverage}x (cap-eff {c.capital_efficiency:.0%})")
        for s in c.sleeves:
            print(f"  {s.asset}: APY {s.apy:.2%}  deployed {s.pct_time_deployed:.0%}  "
                  f"opens/unwinds {s.opens}/{s.unwinds}  avg funding {s.avg_funding_annual:.2%}")
        print(f"  rolling-1y range: {lo:.1f}% / {med:.1f}% / {hi:.1f}%  (today {c.today_apy:.2%})")

    funding_path = base / "btc_funding.json"
    rates_path = base / "rwa_rates.json"
    funding = load_funding(funding_path) if funding_path.exists() else []
    rates = load_rates(rates_path) if rates_path.exists() else []

    if funding:
        res = run_backtest(funding)
        (base / "backtest_result.json").write_text(json.dumps(asdict(res)))
        print(f"[basis/DN]     {res.years:.2f}y  APY {res.apy:.2%}  maxDD {res.max_drawdown:.2%}  "
              f"deployed {res.pct_time_deployed:.0%}")

    if rates:
        r = run_rwa_backtest(rates)
        (base / "rwa_backtest_result.json").write_text(json.dumps(asdict(r)))
        print(f"[RWA repo+MMF] {r.years:.2f}y  APY {r.apy:.2%}  maxDD {r.max_drawdown:.2%}  "
              f"blended {r.avg_blended_yield:.2%}")

    if funding and rates:
        s = run_stacked_backtest(funding, rates)
        (base / "stacked_backtest_result.json").write_text(json.dumps(asdict(s)))
        lo, med, hi = (x * 100 for x in s.annual_range)
        print(f"[STACKED RWA+carry] {s.years:.2f}y  APY {s.apy:.2%}  maxDD {s.max_drawdown:.2%}")
        print(f"  carry sleeve {s.carry_sleeve_apy:.2%} = collateral {s.carry_collateral_apy:.2%} "
              f"+ funding {s.carry_funding_apy:.2%}  |  RWA sleeve {s.rwa_sleeve_apy:.2%}")
        print(f"  rolling-1y blended range: {lo:.1f}% / {med:.1f}% / {hi:.1f}%  (today {s.today_apy:.2%})  "
              f"avg funding {s.avg_funding_annual:.2%}")


if __name__ == "__main__":
    main()
