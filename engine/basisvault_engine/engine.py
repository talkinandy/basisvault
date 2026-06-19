"""Engine tick: read ledger state -> decide -> act (or dry-run log).

Run:
    python -m basisvault_engine.engine            # one mock tick, dry-run
    BV_DRY_RUN=false python -m basisvault_engine.engine   # mock, actually act
    BV_MODE=json BV_LEDGER_URL=... python -m basisvault_engine.engine  # real
"""
from __future__ import annotations

import logging

from .config import EngineConfig
from .ledger import JsonLedgerClient, LedgerClient, MockLedgerClient
from .models import Action, Decision, MarketSnapshot, Underlying
from .strategy import StrategyParams, decide, expected_carry

log = logging.getLogger("basisvault.engine")


def build_client(cfg: EngineConfig) -> LedgerClient:
    if cfg.mode == "json":
        return JsonLedgerClient(
            base_url=cfg.ledger_base_url,
            token=cfg.ledger_token,
            operator_party=cfg.operator_party,
            manager_party=cfg.manager_party,
            vault_template_id=cfg.vault_template_id,
        )
    return MockLedgerClient()


def tick(
    client: LedgerClient,
    market: MarketSnapshot,
    params: StrategyParams = StrategyParams(),
    *,
    dry_run: bool = True,
    kill_switch: bool = False,
) -> Decision:
    """Run one decision cycle. Returns the Decision (and acts unless dry_run)."""
    vault = client.get_vault()
    position = client.get_position()
    decision = decide(market, vault, position, params, kill_switch=kill_switch)

    log.info(
        "carry=%.2f%% delta=%.0f -> %s (%s)",
        expected_carry(market) * 100,
        position.net_delta if position else 0.0,
        decision.action.value,
        decision.reason,
    )

    if dry_run or decision.action is Action.HOLD:
        return decision

    if decision.action is Action.PROPOSE and decision.plan is not None:
        cid = client.propose_rebalance(decision.plan)
        log.info("proposed rebalance -> %s", cid)
    elif decision.action is Action.UNWIND and position is not None:
        client.unwind(position.contract_id)
        log.info("unwound position %s", position.contract_id)

    return decision


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = EngineConfig.from_env()
    client = build_client(cfg)

    # In production the snapshot comes from the oracle (Chainlink/RedStone) +
    # venue funding. Mock sample: healthy positive carry.
    market = MarketSnapshot(
        underlying=Underlying.CBTC,
        price=65_000.0,
        funding_rate=0.12,   # 12%/yr funding to the short perp
        basis=0.01,
        age_seconds=5.0,
    )
    decision = tick(client, market, dry_run=cfg.dry_run)
    print(f"{decision.action.value}: {decision.reason}")


if __name__ == "__main__":
    main()
