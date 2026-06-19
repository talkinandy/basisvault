"""BasisVault off-chain strategy engine.

Reads vault state from the Canton ledger (JSON Ledger API), runs the
delta-neutral carry strategy, and proposes/authorizes rebalances the on-chain
Daml contracts must approve. The engine NEVER holds custody or mints shares —
it only *proposes* (the `manager` role); the `operator` approves on-chain.

Mirrors the on-chain mock-adapter seam: a `LedgerClient` interface with a
`MockLedgerClient` (runs with zero creds, for demo/dry-run) and a
`JsonLedgerClient` (real Canton JSON Ledger API, needs endpoint + token + parties).
"""

__version__ = "0.1.0"
