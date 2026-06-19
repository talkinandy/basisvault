"""BasisVault dashboard — auditable RWA yield + the privacy wow-moment.

Same vault, three role views (need-to-know, mirroring the on-chain disclosure):
  - auditor (observer)  -> full book: RWA allocations + basis position + backtest
  - investor (holder)   -> own holding + NAV + headline yield, NOT the book
  - outsider            -> nothing

Hero = tokenized-RWA yield sources (Treasury repo + MMF), allocated by the
engine's rules-based allocator on real rates; delta-neutral basis is secondary.
Runs against the engine's MockLedgerClient + committed backtest data (zero creds);
point at the JsonLedgerClient for live vault state once testnet access lands.

Run:  uvicorn web.app:app --reload    (needs the [dashboard] extra)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# allow `python -m` / uvicorn to find the engine package alongside web/
_ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(_ENGINE))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from basisvault_engine.allocator import blended_yield, target_allocation  # noqa: E402
from basisvault_engine.engine import tick  # noqa: E402
from basisvault_engine.ledger import MockLedgerClient  # noqa: E402
from basisvault_engine.models import (  # noqa: E402
    MarketSnapshot,
    Underlying,
    YieldQuote,
    YieldSourceKind,
)
from basisvault_engine.strategy import expected_carry  # noqa: E402

app = FastAPI(title="BasisVault")
_DATA = _ENGINE / "data"
_market = MarketSnapshot(Underlying.CBTC, 65_000.0, funding_rate=0.12, basis=0.01, age_seconds=5.0)
NAV = 1_000_000.0


def _seed_demo_client() -> MockLedgerClient:
    """A funded vault driven through real engine ticks so the basis position and
    the network-activity counter reflect actual routed volume."""
    client = MockLedgerClient()
    tick(client, _market, dry_run=False)
    tick(client, _market, dry_run=False)
    client._vault = client.get_vault().__class__(
        contract_id=client.get_vault().contract_id,
        underlying=Underlying.CBTC,
        total_assets=1_500_000.0, total_shares=1_000_000.0,
    )
    tick(client, _market, dry_run=False)
    return client


def _latest_rates() -> tuple[float, float]:
    """Most recent real repo/MMF rates (fallback to representative values)."""
    try:
        rows = json.loads((_DATA / "rwa_rates.json").read_text())
        return rows[-1]["repo_rate"], rows[-1]["mmf_rate"]
    except Exception:
        return 0.0464, 0.0469


def _rwa_portfolio() -> dict:
    """The hero: current RWA allocation on the latest real rates."""
    repo, mmf = _latest_rates()
    quotes = [
        YieldQuote(YieldSourceKind.REPO, "USTB-3M", repo, 1.0),
        YieldQuote(YieldSourceKind.MMF, "MMF-USD", mmf, 1.0),
    ]
    targets = target_allocation(quotes, NAV)
    return {
        "allocations": [
            {"kind": t.kind.value, "asset": t.asset,
             "annualizedRatePct": round(t.annualized_rate * 100, 2),
             "notional": round(t.target_notional, 2)}
            for t in targets
        ],
        "blendedYieldPct": round(blended_yield(targets, NAV) * 100, 2),
    }


def _backtest_band() -> dict | None:
    """The honest, auditable backtest summary (RWA repo+MMF on real rates)."""
    try:
        r = json.loads((_DATA / "rwa_backtest_result.json").read_text())
        return {
            "years": r["years"], "apyPct": round(r["apy"] * 100, 2),
            "maxDrawdownPct": round(r["max_drawdown"] * 100, 2),
            "avgBlendedYieldPct": round(r["avg_blended_yield"] * 100, 2),
            "pctDeployed": round(r["pct_deployed"] * 100, 1),
            "rebalances": r["rebalances"],
            "source": "SOFR (repo) + 3M T-bill (MMF), real history — proxy for CBTC RWA",
        }
    except Exception:
        return None


_client = _seed_demo_client()
ROLES = ("auditor", "investor", "outsider")


def state_for(role: str) -> dict:
    """What `role` is allowed to see — the need-to-know filter."""
    if role == "outsider":
        return {"role": role, "visible": False, "message": "No contracts visible."}

    vault = _client.get_vault()
    rwa = _rwa_portfolio()
    base = {
        "role": role,
        "visible": True,
        "vault": {
            "underlying": vault.underlying.value,
            "nav": vault.total_assets,
            "shares": vault.total_shares,
            "pricePerShare": round(vault.price_per_share, 6),
        },
        "headlineYieldPct": rwa["blendedYieldPct"],  # the number a holder cares about
    }
    if role == "investor":
        base["holding"] = {"shares": 50_000.0, "valueQuote": 50_000.0}
        base["note"] = ("Holder sees own holding + NAV + headline yield, "
                        "not the per-source book.")
        return base

    # auditor (observer): the full book
    base["rwaPortfolio"] = rwa                       # hero: tokenized-RWA yield
    pos = _client.get_position()
    base["basisPosition"] = None if pos is None else {  # secondary source
        "shortNotional": pos.short_notional,
        "longNotional": pos.long_notional,
        "netDelta": pos.net_delta,
        "grossNotional": pos.gross_notional,
        "carryAnnualizedPct": round(expected_carry(_market) * 100, 2),
    }
    base["backtest"] = _backtest_band()             # honest auditable band
    base["networkActivity"] = _client.metrics()     # reward-pool story
    base["note"] = "Auditor sees the full book (RWA allocations + basis + backtest)."
    return base


@app.get("/api/state")
def api_state(role: str = "auditor") -> JSONResponse:
    if role not in ROLES:
        return JSONResponse({"error": f"role must be one of {ROLES}"}, status_code=400)
    return JSONResponse(state_for(role))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


_INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>BasisVault</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 16px;color:#142}
 h1{margin-bottom:0} .sub{color:#687}
 .roles button{font:inherit;margin-right:8px;padding:8px 14px;border:1px solid #2a8;background:#fff;border-radius:8px;cursor:pointer}
 .roles button.on{background:#2a8;color:#fff}
 pre{background:#f4faf7;border:1px solid #cfe9df;border-radius:10px;padding:16px;overflow:auto}
</style></head><body>
<h1>BasisVault</h1>
<div class="sub">Privacy-preserving, auditable <b>tokenized-RWA</b> yield on Canton.
Switch role (operator/holder/observer) to see Canton's need-to-know disclosure.</div>
<p class="roles">
 <button data-r="auditor" class="on">Auditor (observer)</button>
 <button data-r="investor">Investor (holder)</button>
 <button data-r="outsider">Outsider</button>
</p>
<pre id="out">loading…</pre>
<script>
 async function load(r){
   for(const b of document.querySelectorAll('.roles button'))
     b.classList.toggle('on', b.dataset.r===r);
   const res = await fetch('/api/state?role='+r);
   document.getElementById('out').textContent = JSON.stringify(await res.json(), null, 2);
 }
 for(const b of document.querySelectorAll('.roles button'))
   b.onclick = () => load(b.dataset.r);
 load('auditor');
</script>
</body></html>"""
