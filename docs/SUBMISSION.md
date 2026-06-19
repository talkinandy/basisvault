# BasisVault — HackCanton Season 2 submission

**Track:** Real-World Asset (RWA) & Business Workflows *(primary)* · Investment
Infrastructure (fund structure) *(secondary framing)*
**Deadline:** 2026-07-25, 23:59 UTC · **Grand Final:** 2026-08-05, 14:00 UTC
**Repo:** github.com/talkinandy/basisvault

> **BasisVault** — a privacy-preserving, auditable **tokenized-RWA yield vault**
> on Canton. It allocates capital across tokenized-Treasury **repo** carry and
> **money-market-fund** base yield (tokenized credit as a stretch), marks every
> position to an **oracle rate**, and gives institutions on-chain yield they can
> **audit** while keeping the book **counterparty-private** via Canton's
> need-to-know disclosure. A delta-neutral **basis** strategy is one secondary
> source.

---

## Track requirements → what we deliver

The RWA & Business Workflows track asks for four things:

| Required | BasisVault delivers | Status |
|---|---|---|
| **MVP: ≥1 end-to-end workflow** (create → update status → transfer/fulfill → audit/report) | the allocation lifecycle (§1): `ProposeAllocation`→`Approve` → `AccrueAllocation` → `CloseAllocation`, auditor observes throughout | ✅ built, green |
| **Lightweight UI demonstrating roles** (issuer / holder / observer) | dashboard role views: operator(issuer) / investor(holder) / auditor(observer), with the privacy filter | ✅ |
| **1-page business brief** (ICP, use case, who pays, why Canton) | §3 below | ✅ |
| **Short pilot plan** (2–3 steps + required integrations) | §4 below | ✅ |

Cross-cutting judge axes (from S1): **privacy-first** (the Confimarket axis),
**institutional-grade** (Daml roles), **oracle-anchored** (Chainlink `RateFeed`),
**security/honesty** (deterministic Daml, **realized yield only — no phantom NAV**),
**real network activity** (allocations + rebalances on-chain, live counter).

---

## 1. The end-to-end workflow & economic flows

**The yield.** Vault capital is allocated across Canton-native low-risk RWA yield
sources — **tokenized-Treasury repo** carry and **tokenized MMF** base yield — by a
rules-based, regime-aware allocator (rank by risk-adjusted yield, per-source cap to
diversify, cash buffer for redemptions, yield floor). This is the institutional
yield Canton is built for: ~T-bill/repo returns, capital-preserving, auditable.

**The on-chain workflow (the deliverable):**
1. **create** — investor deposits → `Vault` mints `ShareHolding` at NAV/share. The
   **manager** (off-chain allocator) reads oracle rates and **proposes** an
   `AllocationPlan`; the **operator** approves it at the rate feed →
   `Allocation` (authorization-first: the manager can't move funds).
2. **update status** — `Vault_AccrueAllocation` marks the *realized* yield earned
   at the oracle rate to NAV (repeatable as time passes / rates update).
3. **fulfill** — `Vault_CloseAllocation` returns the capital to idle NAV; investors
   redeem at the higher NAV/share.
4. **audit/report** — the **auditor** observes the vault and every allocation +
   accrued yield throughout; a report is a query of the auditor's view.

**Who pays / who earns.**
- *Investors (holders)* earn capital-preserving RWA yield (repo/MMF ~4–5%/yr),
  net of fee, with per-counterparty privacy.
- *Operator/protocol* takes a management + performance fee on **realized** NAV
  growth only.
- *The yield is real cash flow* from the underlying RWA (repo interest, MMF
  distributions), marked to an oracle `RateFeed` — never an emission or a guess.

**No phantom yield.** `Allocation.accrued` only ever increases by
`principal × oracle_rate × elapsed` — observed, realized, on-chain. Direct answer
to Quantstamp/VC scrutiny.

## 2. Proof — honest backtest on real rates

Allocator replayed over **3y of real SOFR (repo) + 3M T-bill (MMF)** — a
transparent public proxy for Canton's tokenized-RWA yields (non-lookahead, real
turnover costs, idle cash earns 0, realized yield only):

| Strategy | APY | Max drawdown | Deployed |
|---|---|---|---|
| **RWA repo + MMF (hero)** | **4.45%** | **0.00%** | 94% |
| Basis / delta-neutral (secondary) | 3.95% | 0.07% | 63% |

Reproduce: `python -m basisvault_engine.backtest`. The result feeds the dashboard's
auditable "backtest band."

## 3. Business brief (1 page)

**ICP — primary:** **regulated institutions, funds, and DAO treasuries** that want
on-chain RWA yield (tokenized Treasuries/repo/MMF) they can **audit and keep
confidential** — auditor sees everything, counterparties see nothing. Secondary:
crypto-native treasuries seeking capital-preserving, market-neutral on-chain yield.

**Use case:** park idle cash/stablecoins into a tokenized-Treasury/MMF vault; earn
auditable repo/MMF carry; redeem at NAV; give your auditor a full real-time view
without exposing positions to counterparties.

**Why Canton (not an EVM L2):**
- **Privacy by construction** — positions counterparty-private; auditor full view.
  No public mempool leaking the book. Not cleanly possible on a transparent L2.
- **Authorization-first Daml** — custodian/manager/auditor/holder roles enforced by
  the ledger; a real fund structure, not bolted-on access control.
- **RWA-native** — Canton is where tokenized Treasuries, repo, and MMFs are being
  issued with atomic settlement; the yield sources live on the same network.

**Who pays:** institutions pay a management/performance fee on realized yield; the
app also earns Canton network rewards for the on-chain volume it generates.

## 4. Pilot plan (2–3 steps + integrations)

1. **Testnet pilot** — deploy the vault + allocation workflow; onboard 1–2 friendly
   fund/DAO treasuries with their own auditor party; prove auditable yield +
   privacy. *Integrations:* JSON Ledger API + party allocation; a tokenized-RWA
   asset (or mock) + an oracle `RateFeed` (Chainlink).
2. **Real RWA sources** — swap the mock `Allocation` seam for live tokenized-Treasury
   repo / MMF tokens as they ship on Canton. *Integrations:* the RWA issuer's Daml
   package + rate feed.
3. **Scale** — enable fees; publish live NAV + the honest backtest; offer the vault
   as a reusable Daml yield primitive other Canton apps compose against.

## 5. Demo script (≈3 min, Grand Final)

1. **Deposit** — investor deposits → `Vault` mints shares (institutional onboarding).
2. **Allocate (create)** — allocator sees repo/MMF rates → manager proposes an
   `AllocationPlan`; operator approves at the oracle `RateFeed`.
3. **Accrue (update status)** — `Vault_AccrueAllocation` marks realized yield → NAV
   rises. Show it's `principal × rate × time`, nothing invented.
4. **Privacy wow-moment** — flip the dashboard role: **auditor sees the full RWA
   book + backtest**, **holder sees only their holding + headline yield**,
   **outsider sees nothing.**
5. **Auditable yield** — the backtest band (4.45% APY @ 0% maxDD on real rates) +
   the live **network-activity counter** (→ Canton rewards).
6. **Fulfill** — `Vault_CloseAllocation` returns capital; redeem at higher NAV.

## 6. Deliverable checklist

- [x] MVP — end-to-end RWA allocation workflow in Daml (create/accrue/close/audit), green
- [x] Roles UI — dashboard operator/holder/observer views with privacy filter
- [x] Business brief — §3 (ICP, use case, who pays, why Canton)
- [x] Pilot plan — §4
- [x] Privacy demonstration — `testPrivacy` + `testAllocation` (holder can't see the book)
- [x] Honest backtest on **real RWA rates** — 4.45% APY @ 0% maxDD (3y SOFR+T-bill)
- [x] Network-activity counter on the dashboard
- [x] Demo script — §5
- [ ] **Submission video / writeup** per the final submission form (format TBC)
- [ ] *(onboarding)* real tokenized-RWA assets + rate feeds; testnet deploy; swap mock seams
- [ ] *(stretch)* tokenized credit source; deeper Investment-Infrastructure framing

## 7. Risks / honesty notes

- **Mock seams** for the RWA assets, venue legs, and live ledger client until
  Canton's tokenized-RWA rails + program onboarding (Delivery phase, Jul 4+) provide
  real Daml interfaces + testnet creds. Stated plainly; the architecture is built so
  the real pieces drop in unchanged.
- **Building for Canton's trajectory, not only today** — tokenized-RWA yield is
  Canton's stated flagship; some sources aren't live yet. We model them behind the
  same seam so BasisVault is ready as they ship.
- **Backtest uses BTC funding / TradFi rates as proxies** for CBTC basis and Canton
  RWA yields (clean Canton history isn't public yet) — labelled as such; it
  validates the *strategy + workflow*, and understates (no basis term, fees modest).
