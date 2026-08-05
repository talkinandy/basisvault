<p align="center">
  <img src="web/assets/basisyield-logo.png" width="88" alt="BasisYield" />
</p>

<h1 align="center">BasisYield · on Canton Network</h1>

<p align="center">
  <b>Leveraged traders pay rent every hour to hold their positions. This vault collects it — auditably.</b><br/>
  Short the BTC/ETH perp on Hyperliquid · long cBTC/cETH in Canton custody · price risk cancels, funding remains.<br/><br/>
  <a href="https://canton.basisyield.com"><b>▶ Live demo — canton.basisyield.com</b></a>
</p>

---

## For judges — verify it in 5 minutes

1. **Open [canton.basisyield.com](https://canton.basisyield.com)** and scroll to
   **"Run it yourself."** Click **▶ Next step** six times: deposit → open carry →
   accrue funding → transfer → unwind → redeem. Every event shows a **real Daml
   transaction id** — the demo executes on **Canton DevNet** (the HackCanton shared validator, JSON
   Ledger API v2), and the carry pairs open at **live Hyperliquid marks**.
2. **Flip the role tabs** (Observer / Issuer / Holder / Outsider). The
   "N contract(s) visible to this role" badge is **Canton's own per-party ACS
   answer**, not UI filtering: after a full run — issuer 5 · observer 1 ·
   holder 0 · outsider 0. This is the privacy thesis, enforced by the ledger.
3. **Check the numbers aren't invented** — reproduce the headline backtest:
   ```bash
   cd engine && python -m basisvault_engine.backtest
   # [HL CARRY hero] 3.21y  APY 12.20%  maxDD 0.21%  5x (cap-eff 83%)
   ```
   The dataset (`engine/data/hl_*_funding.json`, committed) is **every hourly
   funding print Hyperliquid has paid for BTC and ETH since May 2023** — the
   venue our short leg actually trades on, not a proxy.
4. **Read the Daml** — the whole model is ~600 lines:
   [`Vault.daml`](daml/BasisVault/Vault.daml) (roles, carry workflow, NAV),
   [`Position.daml`](daml/BasisVault/Position.daml) (net-delta guard, realized
   funding), [`VaultTest.daml`](daml/Test/VaultTest.daml) (7 green scripts incl.
   the privacy proofs).
5. **The business one-pagers** (also uploaded to the submission form):
   [value/problem](docs/basisyield-value-statement.pdf) ·
   [ICP/audience](docs/basisyield-icp-audience.pdf) ·
   [metrics/validation](docs/basisyield-metrics-validation.pdf) ·
   [GTM](docs/basisyield-gtm.pdf) ·
   [business brief](docs/BUSINESS_BRIEF.md) · [pilot plan](docs/PILOT_PLAN.md).

**Track:** Financial Applications: DeFi, Exchanges & Prediction Markets ·
HackCanton League S2 · [full submission map](docs/SUBMISSION.md)

---

## The product, in one breath

Perp funding is a structural cash flow: leveraged longs paid shorts **~14%/yr on
average across 3.2 years of Hyperliquid's existence** — rent for holding
levered positions. BasisYield is a vault that collects that rent with **zero
net market exposure**: it shorts the BTC/ETH perp on Hyperliquid and holds
equal-notional **cBTC/cETH custodied on Canton**, so price moves cancel and the
funding stream is all that's left. Deposit USDCx, receive shares at NAV, redeem
any time; NAV only ever grows by **realized, oracle-marked funding** — never a
projection.

It is the on-chain productization of **[basisyield.com](https://basisyield.com)**
— our production funding-carry system that runs 24/7 against live Hyperliquid
data — with the spot leg, the fund structure and the audit trail moved onto
Canton.

## Why this needs Canton (and can't exist elsewhere)

A delta-neutral book has a paradox: **institutions can't run it publicly**
(a transparent chain leaks every position to be traded against) **and can't
prove it privately** (an exchange sub-account gives auditors and LPs nothing
to verify). Canton's need-to-know disclosure is the only place both sides
resolve at once:

| Party | Sees | Can do |
|---|---|---|
| **Issuer / operator** (custodian) | everything it signs | approve pairs, accrue, unwind, mint/burn |
| **Manager** (strategy engine) | vault state | **propose only — can never move funds** |
| **Observer / auditor** | **the entire book, live** | nothing (watch-only by construction) |
| **Holder** (investor) | only their own holding + NAV | deposit, transfer, redeem |
| **Outsider / counterparty** | **zero contracts** | — |

Two more Canton-only properties: the **net-delta ≈ 0 hedge is asserted
on-chain** at approval (not a policy, a template guard), and vault shares are
transferable Daml holdings — any Canton app can compose an "earn" feature
against the vault as a primitive.

## Honest numbers (and what we don't claim)

Backtest = the production entry/exit rules replayed over **27,534 hourly
funding prints × 2 assets** (all of HL history): non-lookahead, both-legs costs
on every round trip, sign-guarded (never holds through negative funding), 5×
perp leverage bounded by the liquidation buffer → 83% of capital earning.

| | APY | Max DD | Notes |
|---|---|---|---|
| **cBTC + cETH carry (hero)** | **12.2%** | **0.21%*** | sleeves 12.3% / 12.1%; deployed ~82% of hours |
| Rolling-1y range | **4.5% – 22.6%** | | median 11.7% — **today's regime ≈ 4.5%, the bottom; stated, not hidden** |
| Next phase: RWA-margin stacking | 8.7% *(projection)* | 0.02% | T-bill margin earns ~5% **while** backing the carry |

**Not claimed:** *the 0.21% drawdown is the funding model's — it excludes cross-venue basis, liquidation and execution risk (a live two-leg pilot measures those before we market any risk figure). Also not claimed: any real-money track record (the production engine paper-trades),
stable APYs (funding is regime-dependent), or on-Canton perp execution (the HL
short is attested on-ledger as a `VenueLeg`; execution stays un-armed in a demo).

## What's real vs. mocked — exactly

| Component | Status |
|---|---|
| Canton ledger + all 6 lifecycle steps as Daml txs | ✅ **real — Canton DevNet** (NODERS validator, JSON Ledger API v2) |
| Per-role privacy (ACS counts in the UI) | ✅ **real, ledger-enforced** |
| Funding dataset + backtest | ✅ **real** (HL's own prints, committed) |
| Live BTC/ETH marks in the demo | ✅ **real** (HL API, 60s cache) |
| Production engine provenance | ✅ **real** (basisyield.com, 24/7 paper) |
| HL order execution | 🔶 mocked as on-ledger `VenueLeg` attestation |
| cBTC/cETH as CIP-56 holdings | 🔶 modeled; pilot step 1 (BitSafe `cbtc-lib` + testnet) |
| DevNet deployment | ✅ **live** — DAR on the HackCanton shared validator; 7 parties; the public demo runs on it |

## The end-to-end workflow (on-chain)

| Step | Daml | Authority |
|---|---|---|
| create | `Vault_ProposeRebalance` → `RebalanceProposal_Approve` at the oracle `PriceFeed`; net-delta ≈ 0 asserted | manager proposes → operator approves |
| update | `Vault_AccrueFunding` — realized funding → NAV at the oracle `RateFeed` | operator |
| transfer | `ShareHolding_ProposeTransfer` → `Accept` → `Settle` | holder ↔ holder, operator settles |
| fulfill | `Vault_UnwindPosition` (sign guard) · `RedeemRequest_Accept` | operator |
| audit | observer sees every contract throughout | auditor |

## Layout

```
daml/BasisVault/        Vault + roles · DeltaNeutralPosition (fundingAccrued) · oracle feeds
daml/Test/              7 scripts: carry lifecycle, two-asset book, transfer, privacy proofs
engine/basisvault_engine/  backtests (HL carry hero, RWA, stacked) · strategy · allocator
engine/scripts/         fetch_hl_funding.py (Hyperliquid) · fetch_rates.py (FRED)
engine/data/            committed real datasets + results (reproducible)
web/                    product site · app.py (lifecycle API) · ledger_bridge.py (JSON Ledger API v2)
docs/                   SUBMISSION.md · one-pager PDFs · PILOT_PLAN · TESTNET.md · DEPLOY.md
```

## Build & run everything yourself

```bash
# Daml (JDK 17) — SDK 3.4.11
curl -sSL -o daml.tgz https://github.com/digital-asset/daml/releases/download/v3.4.11/daml-sdk-3.4.11-linux-x86_64.tar.gz
tar xzf daml.tgz && (cd sdk-3.4.11 && ./install.sh) && export PATH="$HOME/.daml/bin:$PATH"
daml build && daml test                      # 7 scripts green

# Engine
cd engine && python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev,ledger,dashboard]' && pytest -q     # 38 passed
python scripts/fetch_hl_funding.py && python -m basisvault_engine.backtest

# Real ledger + dashboard (what the live site runs)
cd .. && daml sandbox --port 6865 --json-api-port 7575 \
  --dar .daml/dist/basisvault-0.1.0.dar --wall-clock-time &
uvicorn web.app:app                          # localhost:8000
```

## Roadmap

**Now** — everything above, live. **Pilot 1 (0–2 mo)** — testnet cBTC/cETH via
CIP-56 + BitSafe `cbtc-lib`; two design-partner treasuries with their own
auditor parties. **Pilot 2 (2–5 mo)** — arm the HL short with the production
execution stack; collateral balancer between HL margin and Canton custody.
**Next phase** — DBS gold token as the third carry pair (H2 2026): the short
leg already exists and is validated — HL's `xyz:GOLD` perp ($168M OI; 7 months
of funding history committed, avg 8.9%/yr, carry backtest **6.8% APY @ 0.16%
maxDD** with the same rules). DTCC tokenized T-bills as **margin that earns
while backing the carry** (Oct 2026); Canton-native perp venue when one
matures. Details: [`docs/PILOT_PLAN.md`](docs/PILOT_PLAN.md).

---

*Demonstration project for HackCanton League S2 — not an offer of any financial
product. Canton is a registered trademark of Digital Asset (Switzerland) GmbH;
no affiliation or endorsement implied.*
