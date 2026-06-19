# BasisVault

**A privacy-preserving, auditable delta-neutral yield vault on the [Canton Network](https://canton.network).**

BasisVault captures funding/basis **carry** — short [PerpSwap](https://docs.canton.network) +
long [Helvet Swap](https://docs.canton.network)/spot on the same underlying (CBTC), so price nets
to ≈ 0 and the funding level is collected — and shows institutions a yield they can **audit**,
while keeping positions **counterparty-private** via Canton's need-to-know disclosure.

Built for **HackCanton** (AppsFactory + Canton Foundation + Noders). Primary track: **DeFi**.

---

## Why it fits the winning pattern

| Judges care about | BasisVault shows |
|---|---|
| **Institutional-grade** | Daml roles — Investor / Manager / Operator(custodian) / Auditor — authorization-first |
| **Privacy-first** (the Season-1 / Confimarket axis) | per-party need-to-know disclosure: auditor sees all, investor sees only their own, outsider sees **nothing** |
| **Oracles** (Chainlink Labs judge) | oracle-anchored marks for NAV + funding/basis input |
| **Security** (Quantstamp judge) | deterministic Daml, explicit guards, no phantom yield |
| **Real volume** (network reward pool) | every rebalance trades on PerpSwap/Helvet — measurable on-chain volume |

## Roles & privacy (the judging wedge)

| Party | Sees | Authorizes |
|---|---|---|
| **operator** (custodian) | everything it signs | mint/burn shares, approve rebalances |
| **manager** (off-chain strategy engine) | vault state | *proposes* rebalances (cannot mint) |
| **auditor** (regulator / fund auditor) | **everything** | nothing |
| **investor** | **only their own** holding | deposit / request redeem |
| **counterparty / outsider** | **nothing** | — |

`Test.VaultTest:testPrivacy` proves the outsider sees zero contracts — Canton's need-to-know
disclosure in action.

---

## Status

**Day-1 + Day-2 on-chain core — compiles + tests GREEN on Daml SDK 3.4.11 (Daml 3.x).**

```
daml build → basisvault-0.1.0.dar
daml test  → testDepositRedeem ✓  testPrivacy ✓  testRebalance ✓
```

Day-2 wires the carry on-chain against a **mock venue adapter** (`BasisVault.Venue`):
approving a rebalance opens a short + long leg at the **oracle mark**, guards
**net delta ≈ 0**, records a `DeltaNeutralPosition`, and `Unwind` closes both legs —
all under need-to-know privacy. The real PerpSwap/Helvet adapters drop into the
leg-execution seam with no change to the vault choreography.

Canton Network is Daml 3.x (mainnet on Canton 3.5.x / Splice 0.6.x). 3.4.11 is the latest
stable open-source SDK; per the Canton docs its `.dar`s are compatible with the current
Splice/Canton release. See [`docs/DEV_NOTES.md`](docs/DEV_NOTES.md) for version pinning and
open blockers.

## Layout

```
daml.yaml                       Daml package config (sdk-version 3.4.11)
daml/BasisVault/Types.daml      Underlying / Venue / Side / RebalancePlan (no templates)
daml/BasisVault/Vault.daml      Vault, ShareHolding, Deposit/Redeem requests, RebalanceProposal
daml/BasisVault/Venue.daml      PriceFeed (oracle mark) + VenueLeg (mock PerpSwap/Helvet adapter seam)
daml/BasisVault/Position.daml   DeltaNeutralPosition — opened on approval, net-delta-≈0 guard, Unwind
daml/Test/VaultTest.daml        deposit/redeem + privacy guarantee + delta-neutral rebalance/unwind
docs/BUILD_PLAN.md              tailored MVP, 4-day plan, demo script, judging map
docs/SCOPING.md                 feasibility + concept rationale
docs/DEV_NOTES.md               SDK/version facts, Canton docs links, open blockers
engine/                         (Day-3) off-chain strategy engine via the JSON Ledger API
web/                            (Day-3) auditable-yield dashboard
```

## Build & test

Needs a JDK (17 used here) + the Daml SDK 3.4.11 (Daml 3.x):

```bash
# install the SDK (public open-source tarball)
curl -sSL -o daml-sdk-3.4.11.tar.gz \
  https://github.com/digital-asset/daml/releases/download/v3.4.11/daml-sdk-3.4.11-linux-x86_64.tar.gz
tar xzf daml-sdk-3.4.11.tar.gz && (cd sdk-3.4.11 && ./install.sh)
export PATH="$HOME/.daml/bin:$PATH"

# from the repo root
daml build          # -> .daml/dist/basisvault-0.1.0.dar
daml test           # setupParties, testDepositRedeem, testPrivacy — all ok
daml start          # sandbox + Navigator to click through deposit/privacy
```

> Before deploying: move `daml/Test/` into its own package so the production `.dar`
> doesn't ship `daml-script` (the build emits a warning about this).

## Roadmap (per `docs/BUILD_PLAN.md`)

- **Day 1 ✅** — Daml vault + roles + deposit/redeem + privacy demo (green).
- **Day 2 ✅** — `RebalanceProposal_Approve` → short + long legs (mock adapters) →
  `DeltaNeutralPosition`, net-delta-≈0 guard, oracle-anchored mark, unwind (green).
  *Pending real PerpSwap/Helvet interfaces to replace the mock leg execution.*
- **Day 3** — off-chain strategy engine (reuse BasisYield analytics/allocation) via the
  JSON Ledger API; repoint the dashboard at live vault state.
- **Day 4** — backtest on historical CBTC funding/basis; demo script; volume counter for
  the network-reward-pool pitch.
- **Stretch** — tokenized-RWA collateral leg → crosses into the RWA track.
