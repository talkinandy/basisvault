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

**[0:00–0:25 · The hook — a strange fact, no product yet]**
Nothing clicked yet; just the hero on screen.
> "Here's a strange fact about crypto markets: every single hour, traders who
> borrow money to bet on Bitcoin pay a fee for the privilege. Not sometimes —
> every hour, around the clock. Over the last three years that fee has averaged
> **fourteen percent a year**. Somebody gets to collect it. Almost nobody does —
> because collecting it safely means holding two opposite positions at once, on
> two different systems, without anyone seeing your book. That's what we built."

**[0:25–0:45 · What it is, in plain words]**
> "BasisYield is a vault on the Canton Network. You put dollars in; it collects
> that hourly fee — think of it as **rent** — and your share grows. No price
> bets: the vault owns Bitcoin and bets *against* Bitcoin at the same time, so
> whether the price goes up or down, the moves cancel and the rent is all
> that's left. Let me show you — and everything you're about to see is running
> **live on Canton's DevNet**" *(point at the badge)* "— not a mockup."

**[0:45–1:05 · Step 1 — an investor puts money in]**
Click **▶ Deposit**; let the spinner breathe.
> "An investor — Alice — puts in one million digital dollars. That little
> spinner is a real two-second round trip to the Canton network, and this is
> the receipt the ledger sent back." *(flash the On-the-wire panel)* "For the
> technical judges: that panel is the raw API traffic. Every number on this
> page comes from a real transaction."

**[1:05–1:50 · Steps 2–3 — the machine, shown not told (centerpiece)]**
Click **▶ Open carry**, then **▶ Accrue funding**; the anatomy cards appear.
> "Here's the machine. Left box: the vault holds real Bitcoin — as cBTC, in
> Canton custody. Right box: an equal-sized bet *against* Bitcoin on
> Hyperliquid, the biggest venue for these bets. Price moves cancel — and the
> ledger itself **refuses the trade** if the two sides don't match. Now watch
> the money: leveraged traders pay their hourly rent straight into our
> position — this week it's running about **8% a year on Bitcoin, 10% on
> Ethereum** — and a quarter's worth just landed: **eighteen and a half
> thousand dollars**, share price up. Only money actually *received* counts;
> the rules are code — the vault cannot invent yield. And this gold preview
> below, marked *not part of this run*: that's what plugs in next. **Gold** —
> the betting side already exists today — and **Treasury-bill margin that
> earns while it works**."

**[1:50–2:25 · The privacy story — three sets of eyes]**
Flip role tabs: **Issuer → Holder → Outsider**, end on Observer.
> "Now the part that makes Canton the only place this can live. A fund's
> positions are like a poker hand — show them, and you get played. So: three
> sets of eyes. The operator sees everything it signs. The **investor** —"
> *(Holder tab)* "— always knows the strategy and their own money, and their
> **auditor watches the entire book, live, on their behalf**. And a
> stranger —" *(Outsider tab)* "— sees zero. Literally zero contracts — and
> that number comes from the network itself, not from our website. Public
> blockchains cannot do this. It's why this strategy has never lived on-chain
> before."

**[2:25–2:45 · Steps 4–6 — hands change, vault steps out, cash out]**
Click **Transfer**, **Unwind**, **Redeem**.
> "Shares can change hands — Alice passes hers to Bob, peer to peer. When the
> rent dries up, the vault automatically steps out of the trade — it never
> pays rent in reverse. And Bob cashes out: **one million eighteen thousand**
> — the deposit plus the rent, exact to the cent."

**[2:45–3:00 · Close — the honest numbers]**
Scroll briefly across the backtest + rent-through-time chart.
> "Three point two years of real data — every hourly payment this market has
> ever made — says this earns about **12% a year** with almost no downside
> wobble. Some years four, some years twenty-two; we publish the whole range,
> and here's the rent through time for every asset, including the two we
> haven't switched on yet. It's the engine we already run at basisyield.com,
> moved on-chain. Leveraged traders pay rent every hour. Now there's a place
> to collect it — **with an audit trail**."

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
- **Funding is regime-dependent** — the range (4.5–22.6% rolling-1y) is the
  honest statement; today sits at the bottom. The sign guard means compressed
  funding degrades toward 0%, not negative.
- **cETH integration is access-gated** (OnRails contact flow) — pilot step 1
  starts with cBTC (public testnet guide + SDK) and adds cETH on access.
