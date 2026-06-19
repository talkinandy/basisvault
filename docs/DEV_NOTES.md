# BasisVault — dev notes (versions, links, open blockers)

Extracted from the HackCanton build into this standalone repo on 2026-06-19.
Source of the original skeleton: the `canton-hackathon` branch of the private
fundingcarry monorepo (kept private — proprietary trading code; not in this repo).

## SDK / version pinning

- **Canton Network is Daml 3.x.** Mainnet runs **Canton 3.5.x / Splice 0.6.x**
  (latest stable at extraction: Canton 3.5.3, Splice 0.6.9).
- We pin **`sdk-version: 3.4.11`** in `daml.yaml` — the latest *stable open-source*
  Daml SDK (3.5.x is snapshot-only on public GitHub). Per the Canton docs,
  ".dar files built by older 3.x Daml SDKs are generally compatible with the
  Canton version used in the current Splice release," so 3.4.11 is the right
  build target for our greenfield contracts.
- The classic `daml` assistant is **deprecated** in favour of **DPM** (Daml
  Package Manager); `daml` is removed in 3.5 but still builds 3.4.x.
- **If HackCanton's testnet pins a specific 3.5.x snapshot** for venue interop,
  bump `sdk-version` and set `build-options: [--target=2.3]` to match their
  Daml-LF version (3.5 enables LF 2.3; 3.4 builds LF 2.2).

Install (Linux x86_64, needs JDK 17):
```bash
curl -sSL -o daml-sdk-3.4.11.tar.gz \
  https://github.com/digital-asset/daml/releases/download/v3.4.11/daml-sdk-3.4.11-linux-x86_64.tar.gz
tar xzf daml-sdk-3.4.11.tar.gz && (cd sdk-3.4.11 && ./install.sh)
export PATH="$HOME/.daml/bin:$PATH"
```

## Canton docs (clean markdown — fetch directly)

- Index: https://docs.canton.network/llms.txt
- Choose your path: https://docs.canton.network/appdev/get-started/choose-your-path.md
- Dev stack: https://docs.canton.network/appdev/modules/m1-development-stack.md
- For EVM devs: https://docs.canton.network/appdev/modules/m2-canton-for-ethereum-devs.md
- **Privacy model** (our wedge): https://docs.canton.network/appdev/deep-dives/privacy-model.md
- Authorization: https://docs.canton.network/appdev/deep-dives/authorization.md
- Explicit contract disclosure: https://docs.canton.network/appdev/deep-dives/explicit-contract-disclosure.md
- Token standard: https://docs.canton.network/appdev/deep-dives/token-standard.md
- JSON Ledger API tutorial: https://docs.canton.network/appdev/modules/m4-json-api-tutorial.md
- App rewards (volume pool): https://docs.canton.network/appdev/app-rewards.md
- Installing a compatible Daml SDK: https://docs.canton.network/global-synchronizer/understand/installing-daml-sdk.md
- Release notes (Canton): https://docs.canton.network/global-synchronizer/release-notes/canton.md
- Release notes (Splice): https://docs.canton.network/global-synchronizer/release-notes/splice.md

## HackCanton Season 2 — CONFIRMED (2026-06-19, registered)

"HackCanton League" Season #2 — hosted by NODERS, online, **business-first**.
Timeline (UTC):

| Phase | Dates | Notes |
|---|---|---|
| 1 · Registration & Team Formation | May 22 → Jul 3 | opening ceremony Jul 3, 15:00 |
| 2 · Delivery | Jul 4 → Jul 26 | workshops, onboarding, mentor support; closing Jul 25, 15:00 |
| **Submission deadline** | **Jul 25, 23:59 UTC** | |
| 3 · Async Judging | Jul 27 → Aug 2 | Top 5–10 finalists announced Aug 2 |
| 4 · Grand Final (Top 5–10) | Aug 3 → Aug 5 | live final Aug 5, 14:00 UTC |

Prize pool: **TBA**. We're building during registration → ahead of schedule.

**Tracks (S2 differ from S1):** **Real-World Asset (RWA) & Business Workflows
(our primary — Canton's flagship use case)** · Financial Applications:
DeFi/Exchanges/Prediction · Investment Infrastructure (Funds/DAOs/Governance,
our secondary framing) · Data/Analytics/Dashboards · Open. See `SUBMISSION.md`
for the deliverable map.

**Positioning (pivoted 2026-06-19):** hero = tokenized-RWA yield (Treasury repo +
MMF), per Canton's RWA-first roadmap; delta-neutral BTC basis kept as one
secondary source. Build for the infra Canton is shipping, not only what's live.

## Open items (pursue via program onboarding / mentors during Delivery)

The Delivery phase provides onboarding materials, quickstart, examples, and
tech+business mentors — the likely channel to clear these:

1. **Venue Daml interfaces** — `.dar`s/signatures for the real legs (Canborsa
   perps, Helvet Swap AMM, Cantex spot, Temple CLOB). Until then: mock adapters.
2. **Testnet access** — JSON Ledger API endpoint + auth (party allocation, JWT),
   shared devnet vs self-hosted LocalNet.
3. **SDK version** the program pins (if a specific 3.5.x snapshot — for interop).
4. **Oracle** — Chainlink (live on Canton) feed package/contract IDs for CBTC
   marks + funding/basis.
5. **RWA stretch** — any tokenized-RWA collateral asset on testnet (RWA track).

## Reuse plan (Day-3, off-chain engine)

Selected modules from the private BasisYield codebase port into `engine/`:
`analytics.py`, `signals/allocation.py`, the dashboard templates — adapted from
funding-rate inputs to Canton funding/basis, reading vault state via the JSON
Ledger API (e.g. DAZL). Copy **selectively and scrub** — do not bring proprietary
trading/execution code (engine, exchange, relayer, killswitch, onboarding) into
this repo.
