"""RWA yield-source allocator — the hero strategy.

Given oracle-anchored yields for Canton's tokenized-RWA sources (Treasury repo,
MMF, credit) plus the secondary delta-neutral basis source, decide how much vault
capital to deploy to each. Rules-based and transparent (no black box), regime-
aware, diversified, capital-preserving:

  - only deploy a source whose yield clears a floor (no chasing dust);
  - rank by RISK-ADJUSTED yield (rate * risk_weight), best first;
  - cap any single source at `max_source_fraction` of NAV (diversification);
  - keep a `cash_buffer_fraction` idle for redemptions;
  - the on-chain `Vault_AccrueAllocation` only ever books REALIZED yield, so a
    too-optimistic quote can't create phantom NAV.

Pure functions of (quotes, nav, params) — fully unit-testable, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import AllocationTarget, YieldQuote


@dataclass(frozen=True)
class AllocatorParams:
    min_yield_floor: float = 0.02       # 2%/yr — below this, don't bother
    max_source_fraction: float = 0.50   # no source > 50% of NAV (diversify)
    cash_buffer_fraction: float = 0.05  # keep 5% idle for redemptions
    rebalance_band: float = 0.10        # ignore drift under 10% of a line


def target_allocation(
    quotes: list[YieldQuote],
    nav: float,
    params: AllocatorParams = AllocatorParams(),
) -> list[AllocationTarget]:
    """The target portfolio: a list of per-source notionals summing to at most
    (1 - cash_buffer) * NAV, greedily filling best risk-adjusted yield first.
    """
    if nav <= 0:
        return []
    deployable = nav * (1.0 - params.cash_buffer_fraction)
    cap = nav * params.max_source_fraction

    eligible = [q for q in quotes if q.annualized_rate >= params.min_yield_floor]
    eligible.sort(key=lambda q: q.annualized_rate * q.risk_weight, reverse=True)

    targets: list[AllocationTarget] = []
    remaining = deployable
    for q in eligible:
        if remaining <= 0:
            break
        notional = min(cap, remaining)
        if notional <= 0:
            continue
        targets.append(AllocationTarget(q.kind, q.asset, q.annualized_rate, notional))
        remaining -= notional
    return targets


def blended_yield(targets: list[AllocationTarget], nav: float) -> float:
    """NAV-weighted annualized yield of the target portfolio (idle cash earns 0)."""
    if nav <= 0:
        return 0.0
    return sum(t.target_notional * t.annualized_rate for t in targets) / nav


def needs_rebalance(
    current: dict[str, float],          # asset -> current notional
    targets: list[AllocationTarget],
    params: AllocatorParams = AllocatorParams(),
) -> bool:
    """True if any line drifts beyond the band, or a source should open/close —
    keeps the engine from churning (each rebalance is an on-chain cost)."""
    target_by_asset = {t.asset: t.target_notional for t in targets}
    assets = set(current) | set(target_by_asset)
    for a in assets:
        cur = current.get(a, 0.0)
        tgt = target_by_asset.get(a, 0.0)
        if cur == 0.0 or tgt == 0.0:
            if abs(tgt - cur) > 0:
                return True
        elif abs(tgt - cur) / cur > params.rebalance_band:
            return True
    return False
