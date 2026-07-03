# BasisYield on Canton — pilot plan

Three steps from hackathon MVP to a production pilot, with the required
integrations named at each step.

## Step 1 — Testnet pilot with design partners (0–2 months)

Deploy the vault package to Canton testnet and onboard **1–2 friendly fund/DAO
treasuries** as design partners, each with their **own auditor party** connected —
prove the two claims that matter (auditable yield, counterparty privacy) on their
books, not ours.

**Required integrations:**
- Canton testnet participant node + **party allocation** (issuer, holders, observer)
- **JSON Ledger API** wiring for the strategy engine (client already written:
  `engine/basisvault_engine/ledger.py::JsonLedgerClient`)
- An oracle **`RateFeed`** publisher (Chainlink — already live on Canton — or a
  signed feed we operate for the pilot)
- A tokenized cash/RWA test asset for deposits (testnet instrument or mock issuer)

## Step 2 — Real RWA yield sources (2–5 months)

Swap the mock allocation seam for **live tokenized-RWA instruments** as they ship
on Canton mainnet — tokenized-Treasury repo first (DTCC's tokenized USTs target
Oct 2026), tokenized MMF second. Enable the RWA-collateralized carry sleeve where
a perp venue (e.g. Canborsa) accepts tokenized-T-bill margin.

**Required integrations:**
- The RWA issuer's Daml package (asset + transfer interfaces; CIP-0056 token
  standard where applicable)
- Issuer/venue onboarding + KYC for the operator entity
- Chainlink rate/mark feeds for each instrument
- Custodian signing workflow (the operator party) — HSM/KMS-backed keys

## Step 3 — Fee switch + scale (5–9 months)

Turn on the management/performance fee (on **realized** NAV growth only), publish
live NAV + the honest backtest publicly, and package the vault as a **reusable
Daml yield primitive** other Canton apps can compose against. Use network-reward
earnings (CIP-0104 volume) to subsidize early TVL.

**Required integrations:**
- Fee accounting in the vault templates (accrual-safe, auditor-visible)
- Mainnet participant hosting (managed node provider or self-hosted validator)
- Reporting exports for institutional ops (the observer view → PDF/API)

---
*Fallbacks are honest by design: every external dependency (RWA asset, venue,
oracle, testnet) sits behind a mock seam that already runs end-to-end — the pilot
replaces seams one at a time, never blocking on all of them at once.*
