"""Off-chain mirrors of the on-chain Daml types (BasisVault.Types / Vault /
Position). Plain dataclasses so the strategy is pure and unit-testable without a
ledger or any third-party deps.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Underlying(str, Enum):
    CBTC = "CBTC"
    CC = "CC"


class Venue(str, Enum):
    # Names mirror the Daml `Venue` enum. Which one is the *real* leg depends on
    # what HackCanton exposes — the design is venue-agnostic. Candidates seen in
    # the wild: Canborsa (perps), Helvet Swap (AMM CBTC/CC), Temple Lightspeed
    # (CLOB), Cantex (spot DEX). Map these to the real adapter at integration.
    PERP_SWAP = "PerpSwap"
    HELVET_SWAP = "HelvetSwap"
    TEMPLE_LIGHTSPEED = "TempleLightspeed"


class Side(str, Enum):
    LONG = "Long"
    SHORT = "Short"


class Action(str, Enum):
    PROPOSE = "PROPOSE"   # open / resize a delta-neutral pair
    HOLD = "HOLD"         # leave the book as-is
    UNWIND = "UNWIND"     # close the position (sign guard / kill switch / stale)


@dataclass(frozen=True)
class MarketSnapshot:
    """Oracle-anchored market inputs for one underlying at one tick.

    `funding_rate` is the per-interval funding the SHORT perp leg receives
    (annualized fraction, e.g. 0.12 == 12%/yr). `basis` is (perp - spot)/spot.
    `price` is the oracle mark (Chainlink/RedStone), NOT last-trade.
    `age_seconds` lets the engine reject stale data.
    """
    underlying: Underlying
    price: float
    funding_rate: float
    basis: float
    age_seconds: float


@dataclass(frozen=True)
class VaultState:
    """Current on-chain vault, as read from the ledger."""
    contract_id: str
    underlying: Underlying
    total_assets: float   # NAV in quote units
    total_shares: float

    @property
    def price_per_share(self) -> float:
        return self.total_assets / self.total_shares if self.total_shares > 0 else 1.0


@dataclass(frozen=True)
class PositionState:
    """A live DeltaNeutralPosition, as read from the ledger (None if flat)."""
    contract_id: str
    underlying: Underlying
    short_notional: float
    long_notional: float
    mark_price: float

    @property
    def net_delta(self) -> float:
        return self.long_notional - self.short_notional

    @property
    def gross_notional(self) -> float:
        return self.short_notional + self.long_notional


@dataclass(frozen=True)
class RebalancePlan:
    """Mirrors the Daml `RebalancePlan` handed to Vault_ProposeRebalance."""
    underlying: Underlying
    short_venue: Venue
    long_venue: Venue
    notional: float       # equal-notional both legs => net delta ~= 0


@dataclass(frozen=True)
class Decision:
    """What the strategy wants to do this tick, with a human-readable reason."""
    action: Action
    plan: RebalancePlan | None
    reason: str
