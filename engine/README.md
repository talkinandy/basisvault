# BasisVault engine (off-chain)

The delta-neutral **carry strategy** that drives the vault. It reads vault state
from the Canton ledger, decides (open / hold / unwind), and **proposes**
rebalances the on-chain Daml contracts must approve. It is the `manager` role —
it never holds custody or mints; the `operator` approves on-chain.

## Design

```
models.py     dataclass mirrors of the Daml types (no deps)
strategy.py   pure decision logic: carry signal, equal-notional sizing,
              sign-guard unwind, stale-data + kill-switch guards  (no deps)
ledger.py     LedgerClient seam:
                MockLedgerClient  -> in-memory, ZERO creds (demo / CI)
                JsonLedgerClient  -> real Canton JSON Ledger API (needs creds)
engine.py     tick: read -> decide -> act (or dry-run);  python -m basisvault_engine.engine
config.py     env-driven config (secrets never committed)
tests/        strategy + mock-ledger integration tests (stdlib + pytest)
```

The `LedgerClient` seam mirrors the on-chain mock-adapter seam: the engine only
calls the interface, so swapping mock → real Canton is a one-line config change
(`BV_MODE=json`) once testnet access lands.

## The strategy (honest yield, no phantom numbers)

- **Carry** = annualized `funding_rate + basis` (funding the short perp receives +
  basis convergence). Acts on **observed** funding/basis only — never projected.
- **Open** when carry ≥ entry threshold; **size** equal-notional both legs so net
  delta ≈ 0 by construction.
- **Unwind** on the **sign guard** (funding turns negative), **stale data**, or
  the **kill switch** — the disciplined exits, not greed.
- **Hysteresis**: exit threshold < entry threshold; rebalance band avoids churn.

All thresholds live in `StrategyParams`.

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'                 # core + pytest (stdlib strategy)
pytest -q                               # 12 tests, no ledger needed

python -m basisvault_engine.engine                 # one mock tick, dry-run
BV_DRY_RUN=false python -m basisvault_engine.engine  # mock, actually act

# real ledger (when testnet creds exist):
pip install -e '.[ledger]'
BV_MODE=json BV_DRY_RUN=false \
  BV_LEDGER_URL=https://<node>/ BV_LEDGER_TOKEN=<jwt> \
  BV_MANAGER_PARTY=<party> BV_OPERATOR_PARTY=<party> \
  BV_VAULT_TID='<pkg-id>:BasisVault.Vault:Vault' \
  python -m basisvault_engine.engine
```

## Status

✅ Strategy + mock ledger + tests green (stdlib-only core). The `JsonLedgerClient`
endpoints follow the v2 JSON Ledger API shape but are **unverified until testnet
access** — confirm exact paths/payloads against the target node. Real venue
execution (Canborsa / Helvet / Cantex) drops into the on-chain `BasisVault.Venue`
adapter seam, not here.
