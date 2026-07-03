# BasisYield on Canton — business brief (1 page)

**What it is.** A privacy-preserving, auditable **tokenized-RWA yield vault** on the
Canton Network. Capital is allocated across tokenized-Treasury **repo** carry and
**money-market** base yield, with an optional **RWA-collateralized delta-neutral
carry** sleeve (the margin is a tokenized T-bill that earns base yield *while* it
backs the trade). Every position is marked to an oracle rate; NAV only ever grows
by **realized** yield. Live demo: https://canton.basisyield.com

## ICP — who it's for

1. **Primary: regulated institutions, funds, and corporate/DAO treasuries** holding
   idle cash/stablecoins who need on-chain yield they can **audit and keep
   confidential** — a real-time observer (auditor) view for compliance, zero
   visibility for counterparties.
2. Secondary: crypto-native treasuries seeking market-neutral, capital-preserving
   yield without directional exposure.

## Use case

Park treasury cash into the vault → the strategy allocates into tokenized-Treasury
repo / MMF yield (backtested **8.7% APY blended, 4.5–14.5% rolling-1y range, 0.02%
max drawdown** on 5y of real data) → yield accrues to NAV, realized-only → transfer
holdings peer-to-peer or redeem at NAV. The fund's **auditor sees the entire book
in real time**; other participants see only what they must (need-to-know).

## Who pays

- **Institutions** pay a management + performance fee on **realized** NAV growth
  (no fee on projections — aligned with the no-phantom-yield design).
- **Canton network rewards**: every allocation/rebalance is genuine on-chain
  volume, earning the app a share of the network reward pool (CIP-0104) — a second
  revenue leg that subsidizes early TVL.

## Why Canton

- **Privacy by construction** — sub-transaction need-to-know disclosure. The
  auditor role sees everything; counterparties see nothing; there is no public
  mempool leaking the book. Not achievable on a transparent EVM chain.
- **Authorization-first Daml** — issuer (custodian) / holder / observer roles are
  enforced by the ledger itself: the strategy engine can *propose* but can never
  move funds. A fund structure compliance can sign off on.
- **The RWA supply lives here** — ~$344B of represented RWA value is already on
  Canton; DTCC launches tokenized US Treasuries on Canton in Oct 2026 (50+ firms
  incl. BlackRock, JPMorgan); 24/7 atomic on-chain UST repo has already run live.
  BasisYield's yield sources are Canton's flagship assets, behind drop-in seams.

---
*HackCanton League S2 · RWA & Business Workflows track · repo: github.com/talkinandy/basisvault ·
demo project — not an offer of any financial product.*
