# BasisYield on Canton — business brief (1 page)

**What it is.** A privacy-preserving, auditable **market-neutral yield vault** on
Canton, running the production [BasisYield](https://basisyield.com) cash-and-carry:
**short the BTC/ETH perp on Hyperliquid** (collect the hourly funding leveraged
longs pay) + **long cBTC/cETH custodied on Canton** (cancel the price risk). Net
delta ≈ 0 is enforced on-chain; NAV only ever grows by **realized** funding.
Live demo: https://canton.basisyield.com

**Why this, why now.** Canton's live asset menu today is stablecoins (USDCx),
cBTC (BitSafe) and cETH (OnRails) — and no mature Canton perp venue exists yet.
Cash-and-carry is the institutional yield you can actually run on that menu
*today*: spot leg in Canton custody, funding leg on the deepest perp venue there
is. Backtested on **every hourly funding print Hyperliquid has paid over 3.2
years**: **12.2% APY, 0.21% max drawdown**, rolling-1y range **4.5–22.6%**
(today's compressed regime sits at the bottom of the range — stated, not hidden).

## ICP — who it's for

1. **Primary: crypto-native treasuries, funds and DAO treasuries** holding
   BTC/ETH/stablecoins who want market-neutral on-chain yield **with a real
   audit trail** — an observer (auditor) party that sees the whole book live.
2. **Secondary: regulated institutions entering via Canton custody.** A
   delta-neutral book that is *public* gets traded against; need-to-know
   disclosure is what makes running this strategy on-chain viable at all.

## Use case

Deposit USDCx → the vault opens sign-guarded carry pairs (equal-notional short
perp + long cBTC/cETH) → funding accrues to NAV, marked to an oracle feed,
**realized only** → transfer holdings peer-to-peer or redeem at NAV. If trailing
funding decays, the sign guard unwinds both legs — the short never pays through
a negative regime. The **auditor sees every position, leg and holding in real
time**; counterparties and other investors see nothing.

## Who pays

- **Holders** pay a management + performance fee on **realized** NAV growth only
  (no fee on projections — aligned with the no-phantom-yield design).
- **Canton network rewards**: deposits, rebalances and accruals are genuine
  on-chain volume earning the app a share of the reward pool (CIP-0104).
- The yield source is structural, not emissions: perp longs paid **~14%/yr
  average funding** (3.2-yr HL mean) to hold their positions. Somebody has to
  be the landlord.

## Why Canton

- **Privacy by construction** — sub-transaction need-to-know disclosure: auditor
  sees everything, counterparties nothing, no public mempool leaking the book.
- **Authorization-first Daml** — issuer/holder/observer roles enforced by the
  ledger: the strategy engine *proposes*, it can never move funds.
- **Institutional custody for the spot leg** — cBTC/cETH are CIP-56 tokens
  (BitSafe: threshold-signature custody, Quantstamp-audited, Chainlink feeds)
  instead of an exchange balance.
- **The stacking roadmap** — as tokenized RWAs ship (DBS gold token H2 2026,
  DTCC tokenized Treasuries Oct 2026), the *margin itself* earns ~5%/yr base
  yield while backing the carry (backtested: carry sleeve 11.6%/yr over 5y) —
  an edge no crypto venue offers, since idle USDC margin earns 0 there.

---
*HackCanton League S2 · RWA & Business Workflows track · repo:
github.com/talkinandy/basisvault · the mechanism is the live BasisYield engine
(24/7 paper-trading on real Hyperliquid prints), not a hackathon sketch ·
demo project — not an offer of any financial product.*
