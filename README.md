# BasisVault

**BasisYield on Canton — a privacy-preserving, auditable market-neutral yield
vault on the [Canton Network](https://canton.network).**
Live: **https://canton.basisyield.com**

BasisVault runs the production [BasisYield](https://basisyield.com) cash-and-carry
on Canton's live asset menu: **short the BTC/ETH perp on Hyperliquid** (collect
the hourly funding leveraged longs pay) + **long cBTC/cETH custodied on Canton**
(cancel the price risk). Net delta ≈ 0 is enforced on-chain; NAV only ever grows
by **realized** funding, marked to oracle feeds. Canton's **need-to-know
disclosure** does the rest: the auditor sees the whole book, each investor sees
only their own holding, and counterparties see nothing — which is what makes
running a delta-neutral book on-chain viable at all (a public book gets traded
against).

Built for **HackCanton League — Season 2** (hosted by NODERS). Track: **Financial
Applications: DeFi, Exchanges & Prediction Markets** (real economic activity,
liquidity flows, composability). **Submission deadline: 2026-07-25 23:59 UTC** ·
Grand Final 2026-08-05. See [`docs/SUBMISSION.md`](docs/SUBMISSION.md) for the
track-requirement map and demo script.

---

## Why this shape (mentor-validated)

Canton's asset menu **today** is stablecoins (USDCx via Circle xReserve), cBTC
(BitSafe, CIP-56) and cETH (OnRails, CIP-56) — with no mature Canton perp venue
yet. So the yield you can actually run *now* is cash-and-carry: spot leg in
Canton custody, funding leg on the deepest perp venue there is. Tokenized RWAs
are the **next phase** behind the same seams: the DBS gold token (H2 2026)
becomes the third carry pair, and tokenized T-bills (DTCC, Oct 2026) become
margin that **earns base yield while backing the carry** — the stacking edge no
crypto venue offers.

| Judges care about | BasisVault shows |
|---|---|
| **Real, runnable today** | the mechanism is a live production system; the demo executes real Daml txs on a Canton ledger |
| **Privacy-first** (the S1 axis) | per-party need-to-know: auditor sees all, holder sees own, outsider sees nothing — ledger-enforced ACS counts in the UI |
| **Oracles** (Chainlink judge) | positions open at an oracle `PriceFeed` mark; funding accrues at an oracle `RateFeed` |
| **Security / honesty** (Quantstamp) | deterministic Daml, net-delta guard on-chain, **realized yield only — no phantom NAV**, regime range stated with today at the bottom |
| **RWA trajectory** | gold/T-bill margin stacking modeled + backtested behind the same seams |

## The end-to-end workflow (what the track asks for)

*create → update status → transfer → fulfill → audit/report*, with roles:

| Step | On-chain (Daml) | Role |
|---|---|---|
| **create** | `Vault_ProposeRebalance` → `RebalanceProposal_Approve` — open short-HL + long-Canton legs at the oracle mark, net-delta ≈ 0 asserted | manager proposes, operator approves |
| **update status** | `Vault_AccrueFunding` — realized funding → NAV at the oracle `RateFeed` (repeatable) | operator |
| **transfer** | `ShareHolding_ProposeTransfer` → `TransferProposal_Accept` → `AcceptedTransfer_Settle` | holder → holder, operator settles |
| **fulfill** | `Vault_UnwindPosition` (sign guard closes both legs) + `RedeemRequest_Accept` | operator |
| **audit/report** | auditor observes vault, positions, legs, feeds and holdings throughout | auditor |

## Roles & privacy (the wedge)

| Party | Role | Sees | Authorizes |
|---|---|---|---|
| **operator** | custodian / issuer | everything it signs | approve pairs, accrue, unwind, mint/burn |
| **manager** | off-chain strategy engine | vault state | *proposes* pairs (cannot move funds) |
| **auditor** | regulator / observer | **everything** | nothing |
| **investor** | holder | **only their own** holding + NAV + headline yield | deposit / transfer / request redeem |
| **outsider** | — | **nothing** | — |

`Test.VaultTest:testPrivacy` proves the outsider sees zero contracts;
`testRebalance`/`testCarryTwoAssets` prove the investor cannot see the book —
Canton need-to-know in action, and on the live demo the per-role contract counts
come from the **ledger's own ACS**, not the UI.

---

## Proof: honest backtest on the real venue's data

The production entry/exit rules replayed over **every hourly funding print
Hyperliquid has paid for BTC and ETH (3.2 years, 27,427 prints each)** —
non-lookahead, both-legs costs on every open/unwind, sign-guarded, 5× perp
leverage set by the liquidation buffer (83% capital efficiency), **realized
funding only**:

| Strategy | APY | Max DD | Notes |
|---|---|---|---|
| **HL carry, cBTC+cETH blended (hero)** | **12.2%** · rolling-1y range **4.7–22.6%** | **0.21%** | cBTC sleeve 12.3% · cETH sleeve 12.1%; deployed ~82% of hours; today's regime ≈ 4.7% (bottom of range — stated) |
| Next phase: RWA-margin stacking (projection) | 8.7% · range 4.5–14.5% | 0.02% | T-bill margin 5.2% + funding 10.0% = carry sleeve 11.6% (5y BTC funding + FRED rates) |

Reproduce: `python scripts/fetch_hl_funding.py && python -m basisvault_engine.backtest`.

## Status — all green

```
daml test  -> setupParties · testDepositRedeem · testPrivacy · testRebalance ·
              testCarryTwoAssets · testAllocation · testTransfer            (7 ✓)
pytest     -> 38 passed  (strategy · allocator · backtest incl. HL carry)
live demo  -> 6-step lifecycle as REAL Daml txs on a Canton sandbox
              (JSON Ledger API v2), per-role ACS counts ledger-enforced
```

Canton is Daml 3.x (mainnet Canton 3.5.x / Splice 0.6.x); pinned to SDK **3.4.11**
(latest stable open-source). Hyperliquid order execution stays **mocked as a
`VenueLeg` attestation** in the demo (the production execution stack exists but
is not armed here); the CIP-56 holdings for cBTC/cETH are pilot step 1 — see
[`docs/PILOT_PLAN.md`](docs/PILOT_PLAN.md).

## Layout

```
daml/BasisVault/Types.daml        Underlying (CBTC/CETH/…) · Venue (Hyperliquid/Cantex/…) · plans
daml/BasisVault/Vault.daml        Vault + roles; carry workflow (propose/approve/accrue/unwind),
                                  deposit/redeem, transfers; next-phase RWA allocation workflow
daml/BasisVault/Position.daml     DeltaNeutralPosition (+ realized fundingAccrued), net-delta guard
daml/BasisVault/Venue.daml        PriceFeed (oracle mark) + VenueLeg (venue adapter seam)
daml/BasisVault/YieldSource.daml  RateFeed (oracle funding/yield) + Allocation (next-phase RWA)
daml/Test/VaultTest.daml          7 scripts: lifecycle, privacy, two-asset book, transfer
engine/basisvault_engine/
  backtest.py                     HL carry hero + RWA + stacked backtests (real data)
  strategy.py · allocator.py      carry thresholds/sign guard · next-phase RWA allocator
  ledger.py                       LedgerClient: Mock (zero creds) + JSON Ledger API
engine/scripts/                   fetch_hl_funding.py (Hyperliquid) · fetch_rates.py (FRED) · fetch_funding.py
engine/data/                      committed real funding/rate data + backtest results
web/app.py · web/ledger_bridge.py dashboard + REAL-ledger lifecycle driver (JSON Ledger API v2)
docs/                             SUBMISSION.md · BUSINESS_BRIEF.md · PILOT_PLAN.md · DEPLOY.md · DEV_NOTES.md
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
python scripts/fetch_hl_funding.py && python -m basisvault_engine.backtest  # real-data backtests
cd .. && daml sandbox --port 6865 --json-api-port 7575 \
  --dar .daml/dist/basisvault-0.1.0.dar --wall-clock-time &   # real ledger for the demo
uvicorn web.app:app --reload   # dashboard at localhost:8000 (run from repo root)
```

> Before deploying: move `daml/Test/` into its own package so the production `.dar`
> doesn't ship `daml-script`.

## Roadmap

- **This phase ✅** — carry vault on Canton's live assets: on-chain workflow
  (7 Daml scripts), HL-carry backtest on 3.2y of real funding, real-ledger demo,
  submission pack.
- **Pilot step 1** — real testnet cBTC/cETH via CIP-56 (`Holding` /
  `TransferInstruction`) + BitSafe `cbtc-lib`; testnet participant.
- **Pilot step 2** — arm the HL short with the production execution stack
  (agent key, leg-sync, killswitch); collateral balancer between HL margin and
  Canton custody.
- **Next phase** — DBS gold token pair (H2 2026); DTCC tokenized-T-bill margin
  (Oct 2026) → the stacking edge; Canton-native perp venue when one matures.
