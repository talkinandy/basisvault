# BasisVault — HackCanton Season 2 submission

**Track:** Financial Applications: DeFi, Exchanges & Prediction Markets
*(switched from RWA & Business Workflows 2026-07-22 — the carry hero is a
financial application; RWA is our next phase. Form pack: [`SUBMISSION_FORM.md`](SUBMISSION_FORM.md))*
**Deadline:** 2026-07-25, 23:59 UTC · **Grand Final:** 2026-08-05, 14:00 UTC
**Repo:** github.com/talkinandy/basisvault · **Live:** https://canton.basisyield.com

**Track fit** — the track asks for financial applications demonstrating *real
economic activity, liquidity flows, and composability across Canton-based
infrastructure*:
- **Real economic activity** — the demo executes real Daml transactions on a
  Canton ledger (deposits, carry opens at live HL marks, funding accrual,
  transfers, redemptions — real tx ids in the UI); the yield source is a real
  structural flow (perp funding, ~14%/yr avg on 3.2y of HL data).
- **Liquidity flows** — USDCx in → cBTC/cETH spot + HL perp margin → funding →
  NAV → redemption; share transfers move claims peer-to-peer.
- **Composability** — vault shares are transferable Daml holdings; the spot leg
  targets CIP-56 `Holding`/`TransferInstruction`; the vault is a reusable
  yield primitive other Canton apps can compose against.

> **BasisYield on Canton** — a privacy-preserving, auditable **market-neutral
> yield vault**. It runs the production [basisyield.com](https://basisyield.com)
> cash-and-carry on Canton's live asset menu: **short the BTC/ETH perp on
> Hyperliquid** (collect hourly funding) + **long cBTC/cETH custodied on Canton**
> (cancel price risk). Net delta ≈ 0 enforced on-chain, realized funding only,
> need-to-know privacy. Next phase: tokenized-RWA margin (DBS gold, T-bills)
> stacking base yield on the carry.

---

## Deliverables map

Business-first deliverables (the S2 pattern: MVP + economic-flows explanation +
network-activity demonstration + GTM/ICP). The table below was built to the RWA
track's end-to-end-workflow bar — it only strengthens a FinApps entry:

| Required | BasisVault delivers | Status |
|---|---|---|
| **MVP: ≥1 end-to-end workflow** (create → update status → transfer/fulfill → audit/report) | full carry lifecycle on-chain: `Vault_ProposeRebalance`→`RebalanceProposal_Approve` (create: open the pair at the oracle mark, net-delta guard) → **`Vault_AccrueFunding`** (update: realized funding → NAV) → `ShareHolding_ProposeTransfer`→`Accept`→`Settle` (transfer) → **`Vault_UnwindPosition`** + redeem (fulfill) → observer sees all (audit). 7 Daml scripts green | ✅ |
| **Lightweight UI demonstrating roles** (issuer / holder / observer) | the **"Run it yourself" lifecycle panel** on the live site — 6 steps **executing as real Daml transactions on Canton DevNet** (NODERS shared validator, JSON Ledger API v2, OIDC): real tx ids on every event; per-role contract counts are the ledger's own ACS answers — **need-to-know enforced by Canton, not the UI**. Mock fallback if the sandbox is down | ✅ live on Canton DevNet |
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
Hyperliquid has paid for BTC and ETH (3.2 years, 27,534 prints each)** —
non-lookahead (decide on the trailing 3-day window, accrue the next print),
both-legs costs on every open/unwind, sign-guarded, realized funding only:

| | APY | Max drawdown | Deployed | Round trips |
|---|---|---|---|---|
| **cBTC sleeve** | 12.31% | — | 84% of hours | 28 |
| **cETH sleeve** | 12.10% | — | 81% of hours | 36 |
| **Blended vault (hero)** | **12.20%** | **0.21%** | — | — |

Rolling-1y range **4.5% / 11.7% / 22.6%** (min/median/max); **today's trailing
1y ≈ 4.5%** — the current compressed-funding regime is the bottom of the range
and we say so. Next-phase projection (RWA-margin stacking, 5y of BTC funding +
FRED rates): blended 8.7% APY with a ~5% collateral floor.

Reproduce: `python scripts/fetch_hl_funding.py && python -m basisvault_engine.backtest`.

## 3. Business brief — see [`BUSINESS_BRIEF.md`](BUSINESS_BRIEF.md)

## 4. Pilot plan — see [`PILOT_PLAN.md`](PILOT_PLAN.md)

## 5. Demo script (≈3 min)

**Pre-flight (off camera):** open canton.basisyield.com → role tab **Observer**
→ ↺ Reset once and let it finish → do one full warm-up run, then Reset again
(warms the node + HL marks cache, so on-camera steps land in ~2s) → scroll so
the lifecycle panel fills the frame. Every claim below is on-screen — no slides.

---

**[0:00–0:20 · Hook — the badge]**
> "Leveraged traders pay rent every hour to hold their positions. BasisYield
> collects it: short the BTC/ETH perp on Hyperliquid, long cBTC and cETH in
> Canton custody — price risk cancels, funding remains. And this is not a
> simulation —" *(point at the badge)* "— everything you're about to see
> executes on **Canton DevNet**, on the network's own validator."

**[0:20–0:40 · Step 1 — Deposit]**
Click **▶ Deposit**; let the *"submitting to Canton…"* spinner be visible.
> "Alice deposits a million USDCx. Watch the button — that's a real ~2-second
> round trip to the participant, and here's the transaction id the ledger
> returned." *(scroll briefly to the **On-the-wire panel**)* "This panel is the
> raw JSON Ledger API traffic — the exact command we sent, and Canton's
> response: update id, offset, record time. No facade."

**[0:40–1:00 · Step 2 — Open carry]**
Click **▶ Open carry**.
> "The strategy engine proposes two pairs — it can only *propose*; the
> custodian approves. Both open at **live Hyperliquid mid marks**, and the
> net-delta-zero hedge isn't a policy — it's **asserted in the Daml template**.
> If the legs don't cancel, the transaction fails."

**[1:00–1:45 · Step 3 — Accrue + the anatomy cards (centerpiece)]**
Click **▶ Accrue funding**; the two anatomy cards + the gold next-phase strip
appear.
> "Here's why this is yield and not a bet. Left leg: spot cBTC in Canton
> custody — earns nothing, cancels price. Right leg: the short perp — 400k of
> notional margined by just **80k at 5×** — you can *see* the leverage, that's
> the one-fifth-filled bar. And the only thing that moves NAV is this —"
> *(trace the animated funding flow)* "— funding paid by leveraged longs at
> the **real trailing Hyperliquid rate**: $8,861 on BTC this quarter — **7.4%
> a year on the pair's capital**, and the strip up top annualizes the whole
> vault at ~6.7%. Realized only — the template cannot book yield that wasn't
> received.
>
> And below, in gold, clearly marked *not part of this run* — the roadmap in
> the same picture-language. **The third pair: gold.** See the two legs? The
> short leg is **solid — it's live today**: Hyperliquid's XAU perp, 168
> million of open interest, 6.8% a year backtested on its entire funding
> history. The long leg is **dashed** — the DBS gold token, H2 2026. One leg
> exists; we're waiting on the other. And next to it, the RWA upgrade as four
> bars: today's margin earns **zero**, like every crypto venue — tokenized
> T-bill margin earns **5.2% while backing the carry**, stack the funding on
> top and the sleeve backtests at **11.6%**. Dead margin is a fee; Canton
> removes it."

**[1:45–2:15 · The privacy flip — three sets of eyes]**
Flip role tabs: **Issuer → Holder → Outsider**, ending back on Observer.
> "Same vault, three sets of eyes — and the contract counts you see are
> **Canton's own answers**, per party, from the ledger's active-contract set —
> not UI filtering. The issuer sees everything it signs. The **holder** —"
> *(pause on Holder)* "— always knows the mandate; it's public and the
> accounting rules are on-chain. What's confidential is only the live blotter,
> because a visible delta-neutral book gets traded against — and it's not
> hidden from everyone: **the fund auditor sees it live**, on the holder's
> behalf. The **outsider** sees zero contracts. This is the thing a
> transparent chain cannot do, and it's why this strategy can exist on-chain
> at all."

**[2:15–2:35 · Steps 4–6 — Transfer, unwind, redeem]**
Click through **Transfer**, **Unwind**, **Redeem**.
> "Shares are transferable Daml holdings — Alice's position moves to Bob,
> propose-accept-settle. The sign guard unwinds both legs — the short never
> pays through a negative regime. And Bob redeems at the higher NAV:
> **$1,016,760 out**. Vault empty, books exact."

**[2:35–3:00 · Honest numbers + close]**
Scroll to the backtest section.
> "The full numbers: our production rules replayed over **every hourly
> funding print Hyperliquid has ever paid** — 3.2 years, both assets:
> **12.2% APY, 0.21% max drawdown**, rolling one-year range 4.5 to 22.6 —
> and today's compressed regime is the *bottom* of that range; we say so on
> the page. This is the live basisyield.com engine brought on-chain, with
> gold and RWA margin already validated behind the same seams. Leveraged
> traders pay rent every hour. Now there's an auditable place to collect it."

---

Fallback: if DevNet hiccups mid-recording, `systemctl revert
basisvault-dashboard && systemctl restart basisvault-dashboard` flips to the
local sandbox — same flow, same script, drop the word "DevNet".

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
