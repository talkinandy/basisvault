"""The delta-neutral carry strategy — pure decision logic.

Port of the BasisYield discipline to Canton's funding/basis: deploy only when the
carry clears a threshold, size equal-notional so price nets to ~0, and unwind on
the funding-sign guard / stale data / kill switch. No phantom yield: we act on
observed funding+basis only, never projected.

Pure functions of (market, vault, position, params) -> Decision. No I/O, so the
whole thing is unit-testable without a ledger.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import (
    Action,
    Decision,
    MarketSnapshot,
    PositionState,
    RebalancePlan,
    Side,
    Venue,
    VaultState,
)


@dataclass(frozen=True)
class StrategyParams:
    # Annualized expected carry (funding + basis) required to OPEN a position.
    entry_carry_threshold: float = 0.05      # 5%/yr
    # Carry below which we UNWIND an open position (hysteresis vs entry).
    exit_carry_threshold: float = 0.01       # 1%/yr
    # Hard sign guard: if realized funding turns negative, always unwind.
    unwind_on_negative_funding: bool = True
    # Fraction of NAV to deploy as gross-per-leg notional when carry clears entry.
    target_deploy_fraction: float = 0.90
    # Reject market data older than this (stale-data guard).
    max_data_age_seconds: float = 60.0
    # Don't churn: only re-propose if target notional moves more than this
    # fraction of the current leg notional.
    rebalance_band: float = 0.10             # 10%
    # Default venues for the two legs (mapped to real adapters at integration).
    short_venue: Venue = Venue.PERP_SWAP
    long_venue: Venue = Venue.HELVET_SWAP


def expected_carry(market: MarketSnapshot) -> float:
    """Annualized carry from holding short-perp / long-spot.

    The short perp leg receives `funding_rate`; the basis (perp richness) is
    additionally captured as it converges. Both are already annualized fractions.
    """
    return market.funding_rate + market.basis


def target_notional(vault: VaultState, params: StrategyParams) -> float:
    """Per-leg notional to deploy (equal on both legs => net delta ~= 0)."""
    return max(0.0, vault.total_assets * params.target_deploy_fraction)


def decide(
    market: MarketSnapshot,
    vault: VaultState,
    position: PositionState | None,
    params: StrategyParams = StrategyParams(),
    kill_switch: bool = False,
) -> Decision:
    """Single-tick decision. Guards first, then carry logic."""
    have_position = position is not None and position.gross_notional > 0.0

    # --- guards (these override carry) ---
    if kill_switch:
        return _hold_or_unwind(have_position, "kill switch engaged")

    if market.age_seconds > params.max_data_age_seconds:
        return _hold_or_unwind(
            have_position,
            f"stale market data ({market.age_seconds:.0f}s > "
            f"{params.max_data_age_seconds:.0f}s)",
        )

    if params.unwind_on_negative_funding and market.funding_rate < 0.0:
        return _hold_or_unwind(
            have_position,
            f"funding turned negative ({market.funding_rate:.2%}) — sign guard",
        )

    carry = expected_carry(market)

    # --- carry logic ---
    if have_position:
        if carry < params.exit_carry_threshold:
            return Decision(
                Action.UNWIND, None,
                f"carry {carry:.2%} below exit threshold "
                f"{params.exit_carry_threshold:.2%}",
            )
        # Position healthy — resize only if drift exceeds the rebalance band.
        target = target_notional(vault, params)
        assert position is not None  # narrowed by have_position
        current = position.short_notional
        if current > 0 and abs(target - current) / current <= params.rebalance_band:
            return Decision(
                Action.HOLD, None,
                f"carry {carry:.2%} healthy; within rebalance band",
            )
        return Decision(
            Action.PROPOSE,
            _plan(vault, params, target),
            f"carry {carry:.2%}; resize leg {current:.0f} -> {target:.0f}",
        )

    # Flat — open only if carry clears the entry threshold.
    if carry >= params.entry_carry_threshold:
        target = target_notional(vault, params)
        if target <= 0.0:
            return Decision(Action.HOLD, None, "no deployable NAV")
        return Decision(
            Action.PROPOSE,
            _plan(vault, params, target),
            f"carry {carry:.2%} >= entry {params.entry_carry_threshold:.2%}; open",
        )

    return Decision(
        Action.HOLD, None,
        f"carry {carry:.2%} below entry {params.entry_carry_threshold:.2%}",
    )


def _plan(vault: VaultState, params: StrategyParams, notional: float) -> RebalancePlan:
    return RebalancePlan(
        underlying=vault.underlying,
        short_venue=params.short_venue,
        long_venue=params.long_venue,
        notional=round(notional, 8),
    )


def _hold_or_unwind(have_position: bool, reason: str) -> Decision:
    return Decision(Action.UNWIND if have_position else Action.HOLD, None, reason)
