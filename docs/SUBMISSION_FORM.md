# Submission form — copy-paste pack

Track: **Financial Applications: DeFi, Exchanges & Prediction Markets**
(switched from RWA & Business Workflows, 2026-07-22 — the carry hero is a
financial application demonstrating real economic activity; RWA is our next
phase, not our MVP).

## Project name

```
BasisYield
```

## Elevator pitch (one-liner, lands in 30s)

```
Leveraged traders pay rent every hour to hold their positions — BasisYield collects it. We short the BTC/ETH perp on Hyperliquid and hold cBTC/cETH in Canton custody, so price risk cancels and funding is all that remains: 12.2% APY backtested on 3.2 years of real Hyperliquid data, 0.21% max drawdown, every demo step a real Daml transaction. The auditor sees everything, counterparties see nothing — the live basisyield.com engine, brought on-chain.
```

Shorter alternate (~15s):

```
BasisYield turns the hourly funding leveraged traders pay into market-neutral, auditable yield on Canton — short the Hyperliquid perp, long cBTC/cETH in Canton custody. 12.2% APY on 3.2 years of real data, private by Canton, no phantom yield.
```

## Long-form description (if the form has a separate description/about field)

```
BasisYield is a market-neutral yield vault on Canton that collects the "rent" leveraged traders pay: it shorts BTC/ETH perpetuals on Hyperliquid (earning the hourly funding longs pay) while holding cBTC/cETH in Canton custody — price risk cancels, funding is all that remains. It is the on-chain productization of our live basisyield.com engine.

Everything in the demo is real. The six-step lifecycle (deposit USDCx → open carry pairs → accrue funding → transfer shares → sign-guard unwind → redeem) executes as actual Daml transactions on a Canton ledger via the JSON Ledger API v2 — real transaction ids on every event, pairs opened at live Hyperliquid marks. Privacy is enforced by Canton itself, not the UI: the auditor party sees the full book, each holder sees only their own holding, and an outsider sees zero contracts. That need-to-know disclosure is what makes running a delta-neutral book on-chain viable at all — a public book gets traded against.

Honest economics: backtested on every hourly funding print Hyperliquid has ever paid over 3.2 years — 12.2% APY, 0.21% max drawdown, rolling-1y range 4.5–22.6%, with today's compressed regime (~4.5%) stated plainly at the bottom of the range. NAV only grows by realized funding marked to oracle feeds — no phantom yield. Fees accrue on realized growth only.

Composability and network activity: vault shares are transferable Daml holdings; the spot leg targets CIP-56 token-standard holdings (BitSafe cBTC, OnRails cETH); every deposit, rebalance, accrual and transfer is genuine Canton activity. Next phase: DBS tokenized gold becomes the third carry pair, and DTCC tokenized T-bills become margin that earns base yield while backing the trade — a structural edge no crypto venue can offer, because their idle margin earns zero.

Live demo: https://canton.basisyield.com
```

(~1,850 chars — fits the 2,000 limit.)

## Tech stack (tags — press Enter after each)

```
Daml 3.x
Canton Network
JSON Ledger API v2
CIP-56 Token Standard
Python
FastAPI
Hyperliquid API
cBTC (BitSafe)
cETH (OnRails)
USDCx
```

## Tech stack (description, if a longer field exists)

```
On-chain: Daml 3.x (SDK 3.4.11) — Vault, ShareHolding, DeltaNeutralPosition, oracle Price/RateFeeds; authorization-first propose→approve flows (the strategy engine can propose but never move funds); net-delta ≈ 0 and realized-only accrual asserted in the templates. Runs on a Canton ledger via the JSON Ledger API v2 (sandbox today; the bridge is env-configurable for a DevNet validator participant — onboarding guide in the repo).

Off-chain: Python strategy engine ported from our production basisyield.com system — trailing funding APR, funding-sign auto-unwind guard, liquidation-buffer leverage (5×, 83% capital efficiency), and honest backtests over 3.2y of real Hyperliquid hourly funding (27,534 prints per asset, non-lookahead, both-legs costs). 38 tests + 7 Daml scripts green.

App: FastAPI dashboard + ledger bridge (submit-and-wait transactions, per-party ACS queries so role views are Canton-enforced); single-page product site; nginx + TLS; live BTC/ETH marks from the Hyperliquid API.

Integration targets (pilot): CIP-56 Holding/TransferInstruction for the cBTC/cETH long leg (BitSafe cbtc-lib SDK + published DARs), Chainlink cBTC feeds on Canton, Splice validator on DevNet.
```
