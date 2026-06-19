"""Strategy unit tests — run with no ledger and no third-party deps."""
from __future__ import annotations

from basisvault_engine.engine import tick
from basisvault_engine.ledger import MockLedgerClient
from basisvault_engine.models import (
    Action,
    MarketSnapshot,
    PositionState,
    Underlying,
    VaultState,
)
from basisvault_engine.strategy import StrategyParams, decide

PARAMS = StrategyParams()
VAULT = VaultState("v", Underlying.CBTC, total_assets=1_000_000.0, total_shares=1_000_000.0)


def mkt(funding=0.12, basis=0.01, age=5.0, price=65_000.0) -> MarketSnapshot:
    return MarketSnapshot(Underlying.CBTC, price, funding, basis, age)


def pos(short=900_000.0, long=900_000.0) -> PositionState:
    return PositionState("p", Underlying.CBTC, short, long, 65_000.0)


# --- opening / holding when flat ---
def test_opens_when_carry_clears_entry():
    d = decide(mkt(funding=0.12), VAULT, None, PARAMS)
    assert d.action is Action.PROPOSE
    assert d.plan is not None
    # equal-notional both legs => net delta zero by construction
    assert d.plan.notional == VAULT.total_assets * PARAMS.target_deploy_fraction


def test_holds_when_carry_below_entry():
    d = decide(mkt(funding=0.02, basis=0.0), VAULT, None, PARAMS)
    assert d.action is Action.HOLD


def test_holds_when_no_deployable_nav():
    empty = VaultState("v", Underlying.CBTC, 0.0, 0.0)
    d = decide(mkt(), empty, None, PARAMS)
    assert d.action is Action.HOLD


# --- guards override carry ---
def test_unwinds_on_negative_funding_sign_guard():
    d = decide(mkt(funding=-0.01), VAULT, pos(), PARAMS)
    assert d.action is Action.UNWIND
    assert "sign guard" in d.reason


def test_negative_funding_when_flat_just_holds():
    d = decide(mkt(funding=-0.01), VAULT, None, PARAMS)
    assert d.action is Action.HOLD


def test_unwinds_on_stale_data():
    d = decide(mkt(age=120.0), VAULT, pos(), PARAMS)
    assert d.action is Action.UNWIND
    assert "stale" in d.reason


def test_kill_switch_unwinds_open_position():
    d = decide(mkt(), VAULT, pos(), PARAMS, kill_switch=True)
    assert d.action is Action.UNWIND
    assert "kill switch" in d.reason


# --- managing an open position ---
def test_holds_within_rebalance_band():
    # target = 900k; current 900k => no churn
    d = decide(mkt(), VAULT, pos(short=900_000.0, long=900_000.0), PARAMS)
    assert d.action is Action.HOLD


def test_resizes_outside_rebalance_band():
    # current 500k vs target 900k => >10% drift => propose resize
    d = decide(mkt(), VAULT, pos(short=500_000.0, long=500_000.0), PARAMS)
    assert d.action is Action.PROPOSE


def test_exits_when_carry_below_exit_threshold():
    d = decide(mkt(funding=0.005, basis=0.0), VAULT, pos(), PARAMS)
    assert d.action is Action.UNWIND
    assert "exit threshold" in d.reason


# --- integration through the mock ledger ---
def test_tick_opens_then_unwinds_on_mock_ledger():
    client = MockLedgerClient(vault=VAULT)
    # tick 1: strong carry, not dry-run -> opens a position
    d1 = tick(client, mkt(funding=0.12), dry_run=False)
    assert d1.action is Action.PROPOSE
    assert client.get_position() is not None
    assert client.get_position().net_delta == 0.0  # equal-notional hedge

    # tick 2: funding flips negative -> sign guard unwinds
    d2 = tick(client, mkt(funding=-0.02), dry_run=False)
    assert d2.action is Action.UNWIND
    assert client.get_position() is None


def test_dry_run_does_not_mutate_ledger():
    client = MockLedgerClient(vault=VAULT)
    tick(client, mkt(funding=0.12), dry_run=True)
    assert client.get_position() is None  # dry-run never acted
