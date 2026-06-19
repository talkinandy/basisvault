"""BasisVault dashboard — auditable yield + the privacy wow-moment.

Same vault, three role views (need-to-know, mirroring the on-chain disclosure):
  - auditor   -> full book (vault NAV + position + legs)
  - investor  -> own holding + vault NAV, NOT the strategy book
  - outsider  -> nothing

Runs against the engine's MockLedgerClient by default (zero creds); point it at
the JsonLedgerClient for live vault state once testnet access lands.

Run:  uvicorn web.app:app --reload    (needs the [dashboard] extra)
"""
from __future__ import annotations

import sys
from pathlib import Path

# allow `python -m` / uvicorn to find the engine package alongside web/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from basisvault_engine.ledger import MockLedgerClient  # noqa: E402
from basisvault_engine.models import MarketSnapshot, PositionState, Underlying  # noqa: E402
from basisvault_engine.strategy import expected_carry  # noqa: E402

app = FastAPI(title="BasisVault")

# Demo state: a funded vault with a live, delta-neutral position.
_client = MockLedgerClient(
    position=PositionState("pos-1", Underlying.CBTC, 900_000.0, 900_000.0, 65_000.0)
)
_market = MarketSnapshot(Underlying.CBTC, 65_000.0, funding_rate=0.12, basis=0.01, age_seconds=5.0)

ROLES = ("auditor", "investor", "outsider")


def state_for(role: str) -> dict:
    """What `role` is allowed to see — the need-to-know filter."""
    if role == "outsider":
        return {"role": role, "visible": False, "message": "No contracts visible."}

    vault = _client.get_vault()
    base = {
        "role": role,
        "visible": True,
        "vault": {
            "underlying": vault.underlying.value,
            "nav": vault.total_assets,
            "shares": vault.total_shares,
            "pricePerShare": round(vault.price_per_share, 6),
        },
    }
    if role == "investor":
        base["holding"] = {"shares": 50_000.0, "valueQuote": 50_000.0}
        base["note"] = "Investor sees own holding + NAV, not the strategy book."
        return base

    # auditor: full book
    pos = _client.get_position()
    base["position"] = None if pos is None else {
        "shortNotional": pos.short_notional,
        "longNotional": pos.long_notional,
        "netDelta": pos.net_delta,
        "grossNotional": pos.gross_notional,
        "markPrice": pos.mark_price,
    }
    base["carryAnnualizedPct"] = round(expected_carry(_market) * 100, 2)
    base["note"] = "Auditor sees the full book (vault + position + carry)."
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
<div class="sub">Privacy-preserving, auditable delta-neutral yield on Canton.
Switch role to see Canton's need-to-know disclosure.</div>
<p class="roles">
 <button data-r="auditor" class="on">Auditor</button>
 <button data-r="investor">Investor</button>
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
