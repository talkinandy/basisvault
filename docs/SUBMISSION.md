# BasisVault — HackCanton Season 2 submission

**Track:** Financial Applications: DeFi, Exchanges & Prediction Markets *(primary)*
· RWA & Business Workflows framing *(secondary)*
**Deadline:** 2026-07-25, 23:59 UTC · **Grand Final:** 2026-08-05, 14:00 UTC
**Repo:** github.com/talkinandy/basisvault

> **BasisVault** — a privacy-preserving, auditable **delta-neutral yield vault**
> on Canton. It earns funding/basis carry (short perp + long spot on CBTC, net
> delta ≈ 0) and gives institutions a yield they can **audit**, while keeping
> positions **counterparty-private** via Canton's need-to-know disclosure.

---

## Track requirements → what we deliver

The DeFi track asks for four things. Map:

| Required (DeFi track) | BasisVault delivers | Status |
|---|---|---|
| **MVP financial product** (DEX module / lending / prediction / **yield tool**) | Daml vault + roles + delta-neutral rebalance + oracle mark; off-chain carry engine; privacy dashboard | ✅ built, green |
| **Clear explanation of economic flows & user incentives** | §1 below | ✅ |
| **Demonstration of meaningful network activity** | §2 below (every rebalance trades on-chain → reward-pool eligible) | ◻ wire volume counter (Day-4) |
| **GTM outline + target user profile** | §3 below | ✅ |

Plus the cross-cutting judge axes (from S1): **privacy-first** (the Confimarket
winner axis), **institutional-grade** (Daml roles), **oracle-anchored**
(Chainlink), **security/honesty** (deterministic Daml, no phantom yield).

---

## 1. Economic flows & user incentives

**The carry.** A delta-neutral pair on one underlying (CBTC): **short** a perp
(receives funding when funding is positive) + **long** spot/AMM of equal notional
(cancels price exposure). Net delta ≈ 0, so the vault is not betting on price — it
**harvests the funding rate + basis convergence**. This is the institutional twin
of cash-and-carry.

**Flow of value.**
1. **Investor** deposits quote units → `Vault` mints `ShareHolding` at NAV/share.
2. **Manager** (off-chain engine) reads funding/basis; when annualized carry clears
   the entry threshold it **proposes** a `RebalancePlan` (it cannot mint or move
   funds — authorization-first).
3. **Operator** (custodian) **approves** on-chain → opens both legs at the
   **oracle mark** → records a `DeltaNeutralPosition` (net-delta-≈0 guard enforced
   in Daml).
4. Funding/basis accrues to the vault → NAV/share rises → investors redeem at the
   higher NAV.
5. **Sign guard:** if funding turns negative (or data goes stale / kill switch),
   the engine unwinds — disciplined exit, not greed.

**Who pays / who earns.**
- *Investors* earn market-neutral carry (target the low-teens %/yr when funding is
  positive), net of fees, without taking directional BTC risk.
- *Operator/protocol* takes a management + performance fee on realized NAV growth
  (honest: fee on **realized** carry only — no phantom yield).
- *The funding counterparty* (longs on the perp venue) pays the funding the vault
  collects — a real, observable cash flow, not an emission.

**No phantom yield.** Yield is the *observed* funding + basis actually accrued and
marked against the **oracle**, never a projected or last-trade number. This is the
hardened-honesty thesis and the direct answer to security/VC scrutiny.

## 2. Network activity (reward-pool story)

Canton rewards apps that generate **genuine on-chain transaction volume**
(CIP-0104 traffic / network reward pool). BasisVault is structurally a
**volume engine**:

- Every **open / resize / unwind** executes two on-chain legs on Canton venues
  (Canborsa/Helvet/Cantex) + a vault state transition — measurable volume per
  rebalance.
- Rebalances recur as funding/basis moves (regime-aware, bounded by a churn band),
  so volume is **continuous**, not one-shot.
- Illustrative: a $10M vault rebalancing on ~10% of NAV a few times a week =
  $-millions/week of routed notional — a concrete, judge-rewarded metric.
- **Day-4 deliverable:** a live **transaction-volume counter** on the dashboard
  (cumulative routed notional + rebalance count) to make this legible in the demo.

## 3. GTM outline & target user (ICP)

**ICP — primary:** crypto-native **treasuries, funds, and DAOs** holding idle CBTC
/ stablecoins that want **market-neutral on-chain yield they can audit and keep
confidential**. Secondary: **regulated institutions** piloting Canton who need
per-counterparty privacy + an auditor view by design.

**Why Canton (not an EVM L2):**
- **Privacy by construction** — positions are counterparty-private; the auditor
  sees the full book, investors see only their own. No public mempool leaking the
  book. This is impossible to do cleanly on a transparent L2.
- **Authorization-first Daml** — custodian/manager/auditor roles are enforced by
  the ledger, not bolted-on access control. Institutions get a fund structure they
  can actually run.
- **Atomic settlement + institutional venues** (Temple, Helvet, Canborsa) live on
  the same network → real composability for the two legs.

**GTM (3 steps):**
1. **Land** — onboard 1–2 friendly DAO/fund treasuries to the testnet vault during
   the program; prove auditable carry + privacy with their own auditor party.
2. **Expand** — turn on the management/performance fee; publish the honest
   backtest + live NAV; use network-reward-pool earnings to subsidize early TVL.
3. **Standardize** — offer the vault as a reusable Daml package other Canton apps
   compose against (yield primitive), and add the RWA-collateral leg (RWA track).

## 4. Demo script (≈3 min, Grand Final)

1. **Deposit** — investor deposits → `Vault` mints shares. (institutional onboarding)
2. **Signal → propose** — engine sees positive funding/basis → proposes a
   delta-neutral pair. (off-chain strategy, `manager` role)
3. **Approve → open** — operator approves → short + long legs open at the **oracle
   mark**; show **net delta ≈ 0** and funding accruing. (on-chain, authorization-first)
4. **Privacy wow-moment** — same vault, flip the dashboard role: **auditor sees the
   full book**, **investor sees only their holding**, **outsider sees nothing.**
5. **Auditable yield** — NAV/share rising on *realized* carry; "no phantom yield"
   risk panel; **transaction-volume counter** ticking (→ network rewards).
6. **Sign guard** — funding flips negative → **auto-unwind**. Disciplined, not greedy.

## 5. Deliverable checklist

- [x] MVP financial product — Daml core (Day-1/2) + engine (Day-3), all green
- [x] Privacy demonstration — dashboard role views (auditor/investor/outsider)
- [x] Economic flows & incentives — §1
- [x] GTM outline + ICP — §3
- [x] Demo script — §4
- [ ] **Network-activity counter** on the dashboard (Day-4)
- [ ] **Honest backtest** on historical CBTC funding/basis (Day-4) — needs data
- [ ] **Submission video / writeup** per the final submission form (TBC format)
- [ ] *(if onboarding lands)* swap mock venue adapters → real legs; deploy to testnet
- [ ] *(stretch)* tokenized-RWA collateral leg → RWA track crossover

## 6. Risks / honesty notes

- **Mock seams** for venue execution + live ledger until program onboarding gives
  real Daml interfaces + testnet creds. We say so plainly; the architecture is
  built so the real adapters drop in unchanged.
- **"Delta-neutral" is honest here** because Canton genuinely has a short perp
  venue (Canborsa) + a long spot/AMM (Helvet/Cantex) — unlike the original Canton
  assumption. Carry is funding/basis, marked to oracle, counted only when realized.
