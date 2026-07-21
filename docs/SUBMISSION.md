# BasisVault — HackCanton Season 2 submission

**Track:** Real-World Asset (RWA) & Business Workflows *(primary)* · Investment
Infrastructure (fund structure) *(secondary framing)*
**Deadline:** 2026-07-25, 23:59 UTC · **Grand Final:** 2026-08-05, 14:00 UTC
**Repo:** github.com/talkinandy/basisvault · **Live:** https://canton.basisyield.com

> **BasisYield on Canton** — a privacy-preserving, auditable **market-neutral
> yield vault**. It runs the production [basisyield.com](https://basisyield.com)
> cash-and-carry on Canton's live asset menu: **short the BTC/ETH perp on
> Hyperliquid** (collect hourly funding) + **long cBTC/cETH custodied on Canton**
> (cancel price risk). Net delta ≈ 0 enforced on-chain, realized funding only,
> need-to-know privacy. Next phase: tokenized-RWA margin (DBS gold, T-bills)
> stacking base yield on the carry.

---

## Track requirements → what we deliver

| Required | BasisVault delivers | Status |
|---|---|---|
| **MVP: ≥1 end-to-end workflow** (create → update status → transfer/fulfill → audit/report) | full carry lifecycle on-chain: `Vault_ProposeRebalance`→`RebalanceProposal_Approve` (create: open the pair at the oracle mark, net-delta guard) → **`Vault_AccrueFunding`** (update: realized funding → NAV) → `ShareHolding_ProposeTransfer`→`Accept`→`Settle` (transfer) → **`Vault_UnwindPosition`** + redeem (fulfill) → observer sees all (audit). 7 Daml scripts green | ✅ |
| **Lightweight UI demonstrating roles** (issuer / holder / observer) | the **"Run it yourself" lifecycle panel** on the live site — 6 steps **executing as real Daml transactions on a Canton ledger** (sandbox + JSON Ledger API v2): real tx ids on every event; per-role contract counts are the ledger's own ACS answers — **need-to-know enforced by Canton, not the UI**. Mock fallback if the sandbox is down | ✅ live, on-ledger |
| **1-page business brief** (ICP, use case, who pays, why Canton) | standalone [`BUSINESS_BRIEF.md`](BUSINESS_BRIEF.md) | ✅ |
| **Short pilot plan** (2–3 steps + required integrations) | standalone [`PILOT_PLAN.md`](PILOT_PLAN.md) — step 1 names the real cBTC/cETH testnet integrations (BitSafe `cbtc-lib`, CIP-56 `Holding`/`TransferInstruction`) | ✅ |

Cross-cutting judge axes: **privacy-first** (the book is Canton-enforced
need-to-know), **institutional-grade** (Daml authorization-first roles),
**oracle-anchored** (`PriceFeed` marks + `RateFeed` funding), **honesty**
(realized yield only — no phantom NAV; regime range stated, today's compressed
regime shown at the bottom of it), **provenance** (the mechanism is a live
production system, not a hackathon sketch).

---

## 1. The mechanism & the end-to-end workflow

**The yield.** Perp longs pay funding (~hourly on Hyperliquid) to hold leveraged
positions — a structural rent, averaging **~14%/yr on BTC and ETH over the 3.2y
of HL's existence**. The vault shorts the perp to *collect* that rent and holds
equal-notional cBTC/cETH on Canton so price moves cancel. Perp leverage is set
by a liquidation buffer (L ≤ 1/(maint+move) → 5×), so **83% of deployed capital
earns** (spot 1× + margin 1/L). When trailing funding decays below the exit
floor, the **sign guard unwinds both legs** — the short never pays through a
negative regime.

**The on-chain workflow (the deliverable):**
1. **create** — investor deposits USDCx → `Vault` mints `ShareHolding` at
   NAV/share. The **manager** (the strategy engine reading HL funding) proposes
   a `RebalancePlan` (short Hyperliquid / long Cantex, USDCx margin); the
   **operator** approves at the oracle `PriceFeed` → `DeltaNeutralPosition`
   with both `VenueLeg`s (net-delta ≈ 0 asserted on-chain).
2. **update status** — `Vault_AccrueFunding` marks the *realized* funding
   received at the oracle `RateFeed` to NAV (repeatable; no phantom yield).
3. **transfer** — holdings move peer-to-peer: propose → accept → operator
   settles; only the two holders, operator and auditor ever see it.
4. **fulfill** — `Vault_UnwindPosition` closes both legs (sign guard); investors
   redeem at the higher NAV/share.
5. **audit/report** — the **auditor** observes the vault, every position, leg,
   feed and holding throughout; a report is a query of the auditor's view.

## 2. Proof — honest backtest on the real venue's data

The production entry/exit rules replayed over **every hourly funding print
Hyperliquid has paid for BTC and ETH (3.2 years, 27,427 prints each)** —
non-lookahead (decide on the trailing 3-day window, accrue the next print),
both-legs costs on every open/unwind, sign-guarded, realized funding only:

| | APY | Max drawdown | Deployed | Round trips |
|---|---|---|---|---|
| **cBTC sleeve** | 12.33% | — | 84% of hours | 28 |
| **cETH sleeve** | 12.11% | — | 81% of hours | 36 |
| **Blended vault (hero)** | **12.22%** | **0.21%** | — | — |

Rolling-1y range **4.7% / 11.7% / 22.6%** (min/median/max); **today's trailing
1y ≈ 4.7%** — the current compressed-funding regime is the bottom of the range
and we say so. Next-phase projection (RWA-margin stacking, 5y of BTC funding +
FRED rates): blended 8.7% APY with a ~5% collateral floor.

Reproduce: `python scripts/fetch_hl_funding.py && python -m basisvault_engine.backtest`.

## 3. Business brief — see [`BUSINESS_BRIEF.md`](BUSINESS_BRIEF.md)

## 4. Pilot plan — see [`PILOT_PLAN.md`](PILOT_PLAN.md)

## 5. Demo script (≈3 min, Grand Final)

1. **The pitch** (20s) — "Leveraged traders pay rent every hour. This vault
   collects it: short the HL perp, long cBTC/cETH on Canton, price cancels,
   funding remains. It's the live basisyield.com mechanism with the spot leg in
   Canton custody."
2. **Deposit** — Alice deposits $1M USDCx → shares minted at NAV (real tx id on
   screen).
3. **Open carry (create)** — manager proposes both pairs at live HL marks;
   operator approves at the oracle feed; net-delta guard on-chain.
4. **Accrue (update status)** — a quarter of real trailing funding accrues:
   NAV/share rises; show it's notional × oracle rate × time, nothing invented.
5. **Privacy wow-moment** — flip roles: **observer sees the whole book (ledger
   says N contracts), holder sees only their holding, outsider sees zero** —
   and point out the counts come from Canton's ACS, not the UI.
6. **Transfer + sign-guard unwind + redeem (fulfill)** — holding moves
   Alice→Bob; guard unwinds both legs; Bob redeems at the higher NAV.
7. **Honest numbers** (20s) — 3.2y of real HL funding: 12.2% APY, 0.21% maxDD,
   range 4.7–22.6%, today ~4.7%. Next phase: DBS gold + T-bill margin stacks
   ~5% on top — margin that earns is the edge no crypto venue has.

## 6. Deliverable checklist

- [x] MVP — end-to-end carry workflow in Daml (open/accrue/transfer/unwind/redeem/audit), 7 scripts green
- [x] Roles UI — lifecycle panel + privacy book, ledger-enforced per-role ACS counts
- [x] Real-ledger execution — sandbox + JSON Ledger API v2, real tx ids in the UI
- [x] Business brief — `BUSINESS_BRIEF.md`
- [x] Pilot plan — `PILOT_PLAN.md`
- [x] Honest backtest on **real Hyperliquid funding** — 12.2% APY @ 0.21% maxDD (3.2y, both assets)
- [x] Next-phase stacking backtest (RWA margin) — 8.7% APY projection, labelled as projection
- [x] Demo script — §5
- [ ] **Submission video / writeup** per the final submission form (format TBC)
- [ ] *(onboarding)* real testnet cBTC/cETH holdings via CIP-56 + BitSafe testnet; swap sandbox → testnet participant

## 7. Risks / honesty notes

- **The short leg is off-Canton** (Hyperliquid) — executed by the operator's
  trade-only agent key and attested on-ledger as a `VenueLeg`. That is also how
  the production system works; a fully-on-Canton pair waits for a mature Canton
  perp venue (Canborsa is in beta).
- **Venue execution is mocked in the demo** — the Canton ledger, the workflow,
  the privacy and the funding data are real; HL order placement is not armed
  (the production execution stack exists but stays out of a hackathon demo).
- **Funding is regime-dependent** — the range (4.7–22.6% rolling-1y) is the
  honest statement; today sits at the bottom. The sign guard means compressed
  funding degrades toward 0%, not negative.
- **cETH integration is access-gated** (OnRails contact flow) — pilot step 1
  starts with cBTC (public testnet guide + SDK) and adds cETH on access.
