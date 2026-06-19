# Canton Network Hackathon — Feasibility & MVP Scope

Branch: `canton-hackathon` (worktree off `fundingcarry`). Status: scoping draft, 2026-06-19.

> "Canon Network" = **Canton Network**. The hackathon host **AppsFactory**
> (`appsfactory.cc`, OG tag: *"A One-Stop Canton Ecosystem Portal"*) is built by
> the Noders team on a Firebase backend that is **auth-gated** — live tracks /
> prize pool / deadlines / judging could not be retrieved without a logged-in
> session, and a `hackathon-feature-availability` flag suggests it may be
> waitlist/login-gated. **Action: paste the logged-in hackathon page so this doc
> can be tailored to the real tracks & prizes.**

## 1. What Canton is (and why it changes our concept)

| | Hyperliquid (BasisYield today) | Canton Network |
|---|---|---|
| Type | Permissionless retail perp DEXs | Public-but-institutional L1 for regulated finance |
| Smart contracts | EVM-ish / HL API, Python + EIP-712 | **Daml** (deterministic, multi-party, authorization-first) |
| Privacy | Public | **Privacy-by-design** (need-to-know disclosure) |
| Native yield primitive | Perp **funding rates** | **Repo financing on tokenized Treasuries**, tokenized MMF, RWA credit |
| Assets | Perps on stocks/indices/commodities | **~$6T tokenized RWA**: Treasuries, repos, MMFs, syndicated loans, mortgages |
| Pricing/oracle | HL marks/oracle | RedStone (live on Canton since Dec 2025) |
| Ethos | Retail, permissionless, anonymous | Institutional, compliant, auditable |

**Consequence (REVISED — see BUILD_PLAN.md §1):** my first pass assumed Canton
had no perps. That's wrong at the **app layer**: HackCanton exposes **PerpSwap**
(levered swaps), **Helvet Swap** (AMM, CBTC/CC), and **Temple Lightspeed**
(order book). So short-perp + long-spot **cash-and-carry ports faithfully** —
not just "DNA reframed." The Hyperliquid Python *strategy/analytics* reuses;
the on-chain layer is new Daml. **The tailored MVP lives in `BUILD_PLAN.md`.**

## 2. What DOES port: the DNA

Our transferable competency is not "funding arb" — it is:
1. **Carry / basis yield construction** (cash-and-carry's institutional twin is **repo**, which is Canton's flagship live use case — on-chain 24/7 Treasury repo, atomic settlement).
2. **Honest, auditable yield** — the exact thing we hardened this cycle: no phantom yield, regime-aware allocation, stale-data guards, transparent backtests. On an institutional chain that sells *compliance and auditability*, this is a real differentiator, not a nice-to-have.
3. **A working analytics/dashboard stack** (FastAPI + the BasisYield dashboard/templates) we can repoint at Canton's ledger.

## 3. Primary MVP — "BasisVault on Canton"

A **transparent, market-neutral tokenized-RWA yield vault** whose pitch is
*"institutional on-chain yield you can actually audit."*

- **Heart (the carry):** allocate vault capital across Canton's native low-risk
  yield sources — **tokenized-Treasury repo carry**, tokenized MMF base yield,
  (optionally) tokenized credit — with a rules-based, regime-aware allocator
  (the two-tier allocation logic from BasisYield, reframed).
- **Differentiator (the moat):** the transparency/risk layer — live allocation
  panel, honest backtest over historical RWA/repo rates, kill-switch / stale-data
  guards, and **Canton privacy**: per-participant need-to-know disclosure of
  positions (a regulated fund can show auditors everything and counterparties
  nothing).
- **Honesty note:** pitch as **market-neutral / capital-preserving** (the assets
  are already low-vol: T-bills, MMF), NOT "delta-neutral funding arbitrage."
  True delta-hedging needs a short venue Canton doesn't have. The "carry" is
  repo/basis, not perp funding.

### Architecture
- **On-chain (Daml, greenfield ~100% new):** `Vault`, `Deposit`/`Withdraw`,
  `Position`, a `YieldSource` interface with 1–2 implementations (mock repo +
  mock MMF for the hackathon), allocation/rebalance choreography. Daml's
  authorization + multi-party workflow model fits fund/custodian/auditor roles
  cleanly.
- **Oracle:** RedStone price/rate feeds on Canton.
- **Off-chain (reuse BasisYield ~40–50% of product surface):** FastAPI service +
  the existing dashboard/templates, repointed at Canton's **JSON Ledger API**
  (Python client e.g. DAZL) to read vault state; reuse the allocation engine,
  backtest harness, and risk framing as an off-ledger advisor that proposes
  rebalances the Daml contracts authorize.

### Realistic hackathon-window scope
- ✅ Daml vault + 2 mock yield sources + rules-based allocation + Daml Script tests.
- ✅ Transparency dashboard (reuse) reading live vault state from the ledger.
- ✅ Backtest on historical Treasury/MMF/repo rates (off-chain, real data).
- ✅ Privacy demo: same vault, two viewers (auditor sees all, counterparty sees subset).
- ⛔ Don't attempt: real institutional repo integration, live RWA custody, audited compliance — mock/stub these and *say so* (honesty is on-brand).

### Reuse ledger
| Layer | Reusable from BasisYield? |
|---|---|
| On-chain contracts | 0% (new Daml) |
| Allocation engine / backtest (Python) | High — adapt inputs from funding→RWA rates |
| Dashboard / templates / UX | High — repoint data source |
| Narrative ("auditable yield, no phantom numbers") | High — and stronger here |

## 4. Alternatives (rank below primary)
- **B. On-chain repo/basis intelligence layer** — analytics + automation around
  tokenized-Treasury repo carry. Leans on both the carry expertise *and* the
  KarbonLens-style data-intelligence skill. Less "build on-chain," more tooling —
  weaker if judges reward Daml building.
- **C. Tokenized-equity credit with market-neutral collateral** — lend tokenized
  stocks, borrow stablecoins, manage collateral risk. Maps to Canton's stated
  "tokenized equities infrastructure" want; more moving parts.

## 5. Key risks / unknowns
1. **Daml learning curve** in a hackathon window — the single biggest risk. Budget day 1 entirely to Daml SDK + Canton sandbox + the `YieldSource` interface skeleton.
2. **Access**: confirm hackathon onboarding gives devnet + SDK + (per §0) what the tracks/prizes actually are.
3. **Repositioning**: our public BasisYield framing is retail-permissionless — the opposite of Canton. The submission must speak institutional/compliance/privacy.
4. **"Delta-neutral" claim**: drop it; say market-neutral/repo-carry. Overclaiming here is exactly the phantom-yield trap we just spent days eliminating.

## 6. Next steps
- [ ] **(blocking)** Get the live hackathon tracks/prizes/deadline (paste logged-in page) → tailor §3 to a specific track.
- [ ] Stand up Daml SDK + Canton sandbox; build the `Vault`/`YieldSource` skeleton.
- [ ] Repoint the FastAPI dashboard at the JSON Ledger API (read-only first).
- [ ] Source historical Treasury/MMF/repo rate data for the backtest.

_Sources: canton.network (FAQ, ecosystem, on-chain Treasury repo press release); CoinDesk (RedStone→Canton, Dec 2025); appsfactory.cc page metadata. Hackathon specifics pending an authenticated session._
