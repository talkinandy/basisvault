# HackCanton MVP — "BasisVault" (tailored build plan)

> **⚠️ Historical (2026-06-19).** This plan captured the BTC delta-neutral framing.
> The project has since **pivoted to a tokenized-RWA yield vault as the hero**
> (Treasury repo + MMF), targeting the **RWA & Business Workflows** track, with
> delta-neutral basis kept as one secondary source. For the current positioning,
> deliverables, economic flows, and demo script see **`SUBMISSION.md`**; for status
> see the repo `README.md`. Kept here for the build history.

Tailored from public HackCanton intel (2026-06-19).

## 0. The hackathon (HackCanton, by AppsFactory + Canton Foundation + Noders)
- **Tracks:** DeFi · RWA · DAO & Governance · AI.
- **Bar:** *working apps deployable on Canton's live mainnet* — not concept decks.
- **Available infra to build on:** **PerpSwap** (levered swaps), **Helvet Swap**
  (AMM, CBTC/CC), **Temple Lightspeed** (institutional order book, sub-10ms),
  Chainlink/RedStone oracles, CIP-0104 traffic rewards.
- **Incentive:** prizes **+ ongoing network-reward-pool shares for apps that
  generate genuine transaction volume** post-deploy. A rebalancing vault earns this.
- **Judges:** Canton Foundation, DWF Ventures, LongHash, Scytale, Jsquare,
  **Quantstamp (security)**, **Chainlink Labs (oracles)**, 42 Super-Validator judges.
- **What won S1 (Confimarket):** institutional-grade + **privacy-first** +
  credible settlement. *That is the pattern to hit.*

## 1. Correction to SCOPING.md §1
Earlier I assumed "no perps/funding on Canton." **Wrong at the app layer** —
PerpSwap (levered swaps) + Helvet Swap (AMM) + Temple (order book) give Canton a
real trading stack. So BasisYield's **actual** mechanism — delta-neutral
funding/basis carry — **ports faithfully**, not just "DNA reframed."

## 2. Concept — BasisVault
**Track:** DeFi (primary), RWA (secondary framing via tokenized collateral).

> A **privacy-preserving, auditable delta-neutral yield vault** on Canton.
> It captures funding/basis carry — **short PerpSwap + long Helvet/spot on the
> same underlying (CBTC)** so price nets to ~zero and the funding level is
> collected — and shows institutions a yield they can **audit**, while keeping
> positions **counterparty-private** via Canton's need-to-know disclosure.

Why it fits the winning pattern:
- **Institutional-grade:** Daml roles (Investor / Manager / Custodian / Auditor), authorization-first.
- **Privacy-first (the Confimarket axis):** Auditor sees the full book; an Investor sees only their shares; counterparties see nothing.
- **Auditable yield:** our whole honesty thesis — no phantom yield, regime-aware sizing, explicit risk guards, oracle-anchored marks (not last-trade). Directly answers Quantstamp/VC scrutiny.
- **Generates volume → reward-pool eligible:** every rebalance trades on PerpSwap/Helvet — a concrete, judge-rewarded metric.

## 3. Architecture
**On-chain (Daml — new):**
- `Vault` — deposits, NAV/share accounting, role parties (Investor, Manager, Custodian, Auditor).
- `Position` + `Rebalance` choreography — Manager *proposes* a delta-neutral pair; Vault authorizes the two legs.
- **Venue adapters** — call PerpSwap (short leg) and Helvet Swap or spot (long leg) via their Daml interfaces. *(Confirm interfaces/testnet access — §7.)*
- Privacy: position/observer disclosure scoped per role.

**Off-chain (reuse BasisYield — high reuse):**
- **Strategy engine** (Python): funding/basis signal, delta-neutral sizing, regime-aware allocation, funding-sign auto-unwind, kill-switch. Reads/writes the vault via Canton's **JSON Ledger API** (e.g. DAZL).
- **Oracle:** Chainlink/RedStone for marks + funding/basis input.
- **Dashboard** (reuse templates): auditable-yield panel, honest backtest band, privacy-aware position views, live volume counter.

## 4. Hackathon-window plan (deployable, per the "working app" bar)
- **Day 1 — Daml + privacy core:** SDK + Canton sandbox; `Vault` + roles; deposit/withdraw; **privacy demo** (Investor vs Auditor vs Counterparty views). De-risks the biggest unknown (Daml) first.
- **Day 2 — the carry, on-chain:** short leg on **PerpSwap** + long leg on **Helvet/spot** (CBTC); `Rebalance` choreography; oracle mark; assert net-delta ≈ 0.
- **Day 3 — strategy engine + UI:** wire the Python engine via JSON Ledger API (propose→authorize rebalances); repoint the dashboard at live vault state.
- **Day 4 — proof + story:** backtest on historical CBTC funding/basis; demo script; volume counter for the reward-pool pitch; security/honesty framing.
- **Stretch:** tokenized-RWA collateral leg → crosses into the **RWA track**.

## 5. Demo script (≈3 min)
1. Institution deposits → `Vault` contract.
2. Engine sees positive funding/basis → proposes delta-neutral pair.
3. Vault authorizes + executes short PerpSwap / long Helvet → show net delta ≈ 0, funding accruing.
4. **Privacy:** Auditor view (full book) vs Counterparty view (nothing). ← the wow moment.
5. Dashboard: auditable yield, honest backtest band, "no phantom yield" risk panel, **transaction-volume counter** (→ network rewards).
6. Funding flips negative → **auto-unwind** (sign guard) — disciplined, not greedy.

## 6. Judging-dimension map
| Judge cares about | We show |
|---|---|
| Institutional-grade (Foundation, VCs) | Daml custodian/auditor roles, authorization model |
| **Privacy-first** (the S1 winner axis) | per-party need-to-know position disclosure |
| Oracles (Chainlink) | Chainlink/RedStone marks + funding input |
| Security (Quantstamp) | deterministic Daml, oracle-anchored marks, explicit guards, no phantom yield |
| Real + volume (reward pool) | deployed app; rebalances generate measurable volume |

## 7. Unknowns to confirm (paste logged-in page / check docs)
- [ ] Season 2 live? **deadline**, **prize pool**, eligibility, submission format.
- [ ] PerpSwap / Helvet Swap / Temple **Daml interfaces + testnet access + docs**.
- [ ] Tokenized-RWA collateral available on testnet (for the RWA-track stretch)?
- [ ] JSON Ledger API / DAZL client version for the off-chain engine.

## 8. Reuse ledger
High reuse: strategy engine, backtest harness, dashboard/templates, honesty narrative.
New: Daml contracts + venue adapters (PerpSwap/Helvet). Net: a faithful port of
BasisYield's edge onto Canton, with privacy + auditability as the wedge.
