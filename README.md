# BasisVault

**A privacy-preserving, auditable tokenized-RWA yield vault on the [Canton Network](https://canton.network).**

BasisVault gives institutions **on-chain yield they can audit** — and keep
confidential. It allocates vault capital across Canton's tokenized real-world-asset
yield sources — **tokenized-Treasury repo carry** and **money-market-fund base
yield** (with tokenized credit as a stretch) — via a rules-based, regime-aware
allocator, and marks every position to an **oracle rate** so the yield is real, not
projected. A delta-neutral **basis** strategy (short perp + long spot) is included
as one secondary source. Canton's **need-to-know disclosure** does the rest: the
auditor sees the whole book, each investor sees only their own holding, and
counterparties see nothing.

Built for **HackCanton League — Season 2** (hosted by NODERS). Track: **Real-World
Asset (RWA) & Business Workflows**. **Submission deadline: 2026-07-25 23:59 UTC** ·
Grand Final 2026-08-05. See [`docs/SUBMISSION.md`](docs/SUBMISSION.md) for the
track-requirement map, economic flows, GTM, and demo script.

---

## Why it fits Canton (and the winning pattern)

Canton's flagship use case is **institutional, regulated, tokenized RWA** —
Treasuries, repo, MMFs, credit. "Auditable, privacy-preserving yield on tokenized
Treasuries you can show your auditor and hide from counterparties" is exactly the
institutional-first, privacy-first axis that won Season 1 (Confimarket).

| Judges care about | BasisVault shows |
|---|---|
| **RWA / institutional** | tokenized-Treasury repo + MMF yield as the hero; fund roles enforced by Daml |
| **Privacy-first** (the S1 axis) | per-party need-to-know: auditor sees all, holder sees own, outsider sees nothing |
| **Oracles** (Chainlink judge) | every allocation marked to an oracle `RateFeed`; basis source marked to price |
| **Security / honesty** (Quantstamp) | deterministic Daml, explicit guards, **realized yield only — no phantom NAV** |
| **Real volume** (network reward pool) | allocations + rebalances are on-chain activity; live counter on the dashboard |

## The RWA workflow (what the track asks for)

The RWA track wants one end-to-end workflow — *create → update status → fulfill →
audit/report* — with roles. BasisVault's allocation lifecycle **is** that workflow:

| Step | On-chain (Daml) | Role |
|---|---|---|
| **create** | `Vault_ProposeAllocation` → `AllocationProposal_Approve` (at the oracle rate feed) | manager proposes, operator approves |
| **update status** | `Vault_AccrueAllocation` — marks *realized* yield to NAV (repeatable) | operator |
| **fulfill** | `Vault_CloseAllocation` — capital returns to idle NAV | operator |
| **audit/report** | auditor observes vault + every allocation + accrued yield throughout | auditor |

## Roles & privacy (the wedge)

| Party | Role | Sees | Authorizes |
|---|---|---|---|
| **operator** | custodian / issuer | everything it signs | approve allocations, accrue, close, mint/burn |
| **manager** | off-chain allocator | vault state | *proposes* allocations (cannot mint) |
| **auditor** | regulator / observer | **everything** | nothing |
| **investor** | holder | **only their own** holding + NAV + headline yield | deposit / request redeem |
| **outsider** | — | **nothing** | — |

`Test.VaultTest:testPrivacy` proves the outsider sees zero contracts; `testAllocation`
proves the investor cannot see the strategy book — Canton need-to-know in action.

---

## Proof: honest backtest on 5 years of real data

The headline is **RWA-collateralized carry** — the BasisYield (Hyperliquid)
mechanism, made better by Canton: a delta-neutral carry whose **margin is a
tokenized T-bill**, so the collateral earns base yield *while* it backs the trade
(idle margin earns 0 on a crypto venue). Replayed over **5y of real BTC funding
(Binance) + SOFR/3M-T-bill (FRED)**:

| Strategy | APY (5y) | Max DD | Notes |
|---|---|---|---|
| **Stacked RWA-collateralized carry (headline)** | **8.7%** · rolling-1y range **4.5–14.5%** | **0.02%** | T-bill collateral **5.2%** + funding **10.0%** = carry sleeve **11.6%**; blended 60/40 with pure RWA |
| Pure RWA repo + MMF | 3.4% | 0.00% | capital-preserving floor |
| Delta-neutral basis only | 6.1% | 0.18% | funding carry, sign-guarded |

The collateral-yield **stacking** is the structural edge Hyperliquid can't offer.
Non-lookahead, real turnover costs, sign-guarded funding, idle cash earns 0,
**realized yield only**, 1× notional (no leverage). Funding is regime-dependent —
the range is data-driven, not cherry-picked. Reproduce: `python -m basisvault_engine.backtest`.

## Status — all green

```
daml test     -> setupParties · testDepositRedeem · testPrivacy · testRebalance · testAllocation   (5 ✓)
pytest        -> 28 passed  (strategy · allocator · backtest · ledger · dashboard)
```

Canton is Daml 3.x (mainnet Canton 3.5.x / Splice 0.6.x); pinned to SDK **3.4.11**
(latest stable open-source; `.dar`s compatible per the Canton docs). RWA assets and
venue legs that aren't live on Canton yet sit behind **mock seams** — real
tokenized-RWA tokens, venue adapters, and the live JSON-Ledger-API client drop in
unchanged as the infrastructure ships / onboarding lands. See
[`docs/DEV_NOTES.md`](docs/DEV_NOTES.md).

## Layout

```
daml/BasisVault/Types.daml        Underlying/Venue/Side + YieldSourceKind + Allocation/RebalancePlan
daml/BasisVault/YieldSource.daml  RateFeed (oracle yield) + Allocation (RWA source) — the hero
daml/BasisVault/Vault.daml        Vault + roles; allocation workflow + deposit/redeem + basis rebalance
daml/BasisVault/Venue.daml        PriceFeed + VenueLeg (mock perp/spot adapter seam — basis source)
daml/BasisVault/Position.daml     DeltaNeutralPosition (basis source), net-delta-≈0 guard, Unwind
daml/Test/VaultTest.daml          deposit/redeem · privacy · rebalance · RWA allocation lifecycle
engine/basisvault_engine/
  allocator.py                    rules-based RWA allocation (the hero strategy)
  strategy.py                     delta-neutral carry logic (secondary basis source)
  backtest.py                     RWA + basis backtests (real rate/funding data)
  ledger.py                       LedgerClient: Mock (zero creds) + JSON Ledger API
  models.py · engine.py · config.py
engine/scripts/                   fetch_rates.py (FRED SOFR/T-bill), fetch_funding.py (Binance)
engine/data/                      committed real rate/funding data + backtest results
web/app.py                        dashboard: RWA portfolio + backtest band + role views
docs/                             SUBMISSION.md (submission pack) · SCOPING · BUILD_PLAN · DEV_NOTES
```

## Build & test

```bash
# Daml (needs JDK 17)
curl -sSL -o daml-sdk-3.4.11.tar.gz \
  https://github.com/digital-asset/daml/releases/download/v3.4.11/daml-sdk-3.4.11-linux-x86_64.tar.gz
tar xzf daml-sdk-3.4.11.tar.gz && (cd sdk-3.4.11 && ./install.sh)
export PATH="$HOME/.daml/bin:$PATH"
daml build && daml test

# Engine + dashboard
cd engine && python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev,ledger,dashboard]'
pytest -q
python scripts/fetch_rates.py 3 && python -m basisvault_engine.backtest   # real-data backtest
uvicorn web.app:app --reload   # dashboard at localhost:8000 (run from repo root)
```

> Before deploying: move `daml/Test/` into its own package so the production `.dar`
> doesn't ship `daml-script`.

## Roadmap

- **On-chain ✅** — vault + roles + privacy; RWA allocation workflow (create/accrue/close);
  basis source (delta-neutral rebalance/unwind). 5 Daml scripts green.
- **Off-chain ✅** — RWA allocator + delta-neutral strategy + real-data backtests + mock/JSON
  ledger clients; 28 tests green.
- **Dashboard ✅** — RWA portfolio + auditable backtest band + network-activity, role-filtered.
- **Submission packaging** — `docs/SUBMISSION.md`: track map, economic flows, GTM/ICP, demo script.
- **Pending onboarding (Delivery phase, Jul 4+)** — real tokenized-RWA assets + rate feeds, testnet
  + JSON Ledger API creds, deploy; swap mock seams for live.

> **Canton RWA / venue reality (researched 2026-06-19):** Canton's tokenized-RWA
> rails are still rolling out; live trading venues include **Canborsa** (perps),
> **Helvet Swap** (CBTC/CC AMM), **Cantex** (spot DEX), **Temple Lightspeed** (CLOB),
> with **Chainlink** oracles live. None publish open Daml interfaces or testnet creds
> yet — hence the mock seams. Building for the infrastructure Canton is shipping, not
> only what exists today.
