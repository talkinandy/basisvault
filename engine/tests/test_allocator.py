"""Allocator unit tests — no I/O, deterministic."""
from __future__ import annotations

from basisvault_engine.allocator import (
    AllocatorParams,
    blended_yield,
    needs_rebalance,
    target_allocation,
)
from basisvault_engine.models import YieldQuote, YieldSourceKind

P = AllocatorParams()
NAV = 1_000_000.0


def q(kind, asset, rate, rw=1.0) -> YieldQuote:
    return YieldQuote(kind, asset, rate, rw)


def test_ranks_by_risk_adjusted_yield():
    quotes = [
        q(YieldSourceKind.MMF, "MMF-USD", 0.045),
        q(YieldSourceKind.REPO, "USTB-3M", 0.0525),
        q(YieldSourceKind.BASIS, "CBTC-DN", 0.12, rw=0.3),  # high rate, low weight
    ]
    targets = target_allocation(quotes, NAV, P)
    # repo (0.0525) ranks above basis (0.12*0.3=0.036) above mmf (0.045)?
    # risk-adjusted: repo .0525, mmf .045, basis .036 -> order repo, mmf, basis
    assert [t.asset for t in targets][:2] == ["USTB-3M", "MMF-USD"]


def test_respects_cash_buffer_and_source_cap():
    quotes = [
        q(YieldSourceKind.REPO, "USTB-3M", 0.0525),
        q(YieldSourceKind.MMF, "MMF-USD", 0.045),
    ]
    targets = target_allocation(quotes, NAV, P)
    deployed = sum(t.target_notional for t in targets)
    assert deployed <= NAV * (1 - P.cash_buffer_fraction) + 1e-6
    assert all(t.target_notional <= NAV * P.max_source_fraction + 1e-6 for t in targets)
    # with a 50% cap and 95% deployable, two sources => ~50% + ~45%
    assert len(targets) == 2


def test_floor_excludes_low_yield():
    quotes = [q(YieldSourceKind.MMF, "MMF-USD", 0.005)]  # below 2% floor
    assert target_allocation(quotes, NAV, P) == []


def test_blended_yield_accounts_for_idle_cash():
    quotes = [q(YieldSourceKind.REPO, "USTB-3M", 0.05)]
    targets = target_allocation(quotes, NAV, P)
    by = blended_yield(targets, NAV)
    # only ~50% (cap) deployed at 5% => blended ~2.5%, strictly below the raw rate
    assert 0.0 < by < 0.05


def test_zero_nav_allocates_nothing():
    assert target_allocation([q(YieldSourceKind.REPO, "USTB-3M", 0.05)], 0.0) == []


def test_needs_rebalance_band():
    quotes = [q(YieldSourceKind.REPO, "USTB-3M", 0.05)]
    targets = target_allocation(quotes, NAV, P)
    tgt = targets[0].target_notional
    assert needs_rebalance({}, targets, P)                      # nothing -> open
    assert not needs_rebalance({"USTB-3M": tgt}, targets, P)    # on target
    assert not needs_rebalance({"USTB-3M": tgt * 1.05}, targets, P)  # within band
    assert needs_rebalance({"USTB-3M": tgt * 1.5}, targets, P)  # beyond band
