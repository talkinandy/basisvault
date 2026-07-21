# BasisYield on Canton — pilot plan

Three steps from hackathon MVP to a production pilot, with the required
integrations named at each step.

## Step 1 — Testnet pilot: real cBTC/cETH long leg (0–2 months)

Deploy the vault package to Canton testnet, hold **real testnet cBTC/cETH** as
the long leg, and run the short leg against the production BasisYield engine in
paper mode (its live 24/7 loop already reads real Hyperliquid funding). Onboard
**1–2 friendly fund/DAO treasuries**, each with their **own auditor party** —
prove the two claims that matter (auditable carry, counterparty privacy) on
their books, not ours.

**Required integrations:**
- Canton testnet participant + **party allocation** (issuer, holders, observer)
- **cBTC testnet** mint/transfer via BitSafe's developer flow (`cbtc-lib` SDK,
  published DARs, testnet guide); cETH via OnRails' integration/access flow
- **CIP-56 token standard** interfaces for the spot holding
  (`Holding`, `TransferInstruction` — the vault holds cBTC/cETH as standard
  token holdings, not bespoke contracts)
- JSON Ledger API wiring for the engine (bridge already written and running:
  `web/ledger_bridge.py` — the demo drives a Canton ledger with real txs today)
- An oracle **`RateFeed`/`PriceFeed`** publisher (Chainlink already ships cBTC
  feeds on Canton; funding feed operated by us for the pilot)

## Step 2 — Live capital, hedged execution (2–5 months)

Arm the short leg on Hyperliquid mainnet with the production execution stack
(agent-key trade-only wallet, IOC-limit orders, leg-sync guard, killswitch) and
size the vault's first real capital. Add the **collateral balancer** — the
cross-venue shuttle that keeps HL margin and Canton custody in ratio as price
moves (the design already exists in the production repo).

**Required integrations:**
- Hyperliquid agent-key onboarding for the operator entity (master key never on
  a server; revocable; trade-only)
- Custodian signing workflow for the Canton operator party (HSM/KMS keys)
- BTC/ETH bridge/OTC path for rebalancing between HL margin and cBTC/cETH
  custody (BitSafe mint/burn is the native cBTC path)
- Ops runbook: killswitch gauges, daily-loss halt, drift reconciliation

## Step 3 — The stacking phase: gold + RWA margin (5–9 months)

As tokenized RWAs ship on Canton, extend the same seams: **DBS gold token**
(H2 2026) becomes the third carry pair (gold spot on Canton vs XAU perp), and
**tokenized T-bills** (DTCC, Oct 2026) become margin that earns base yield
*while* backing the carry — backtested +5.2%/yr on the carry sleeve. Turn on
the fee switch (realized NAV growth only) and package the vault as a reusable
Daml yield primitive other Canton apps compose against.

**Required integrations:**
- The RWA issuer's Daml package (CIP-56 asset + transfer interfaces)
- A Canton-native perp venue as it matures (Canborsa is in beta) for a
  fully-on-Canton pair — until then HL remains the funding leg
- Chainlink rate/mark feeds per instrument
- Reporting exports for institutional ops (the observer view → PDF/API)

---
*Every external dependency (venue, asset, oracle, testnet) sits behind a seam
that already runs end-to-end in the demo — the pilot replaces seams one at a
time, never blocking on all of them at once.*
