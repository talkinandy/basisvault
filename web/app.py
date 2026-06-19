"""BasisYield on Canton — MVP dashboard.

A designed, user-facing product page (BasisYield "Sunrise" brand) over the
BasisVault on-chain vault + off-chain allocator. Serves:
  - GET /                 the landing/dashboard page (web/index.html)
  - GET /api/state?role=  public product overview + role-gated live book

Privacy demo = the role switch. The marketing page is public; the *live book*
(allocations, positions, holdings) is need-to-know:
  - auditor (observer) -> full book   · investor (holder) -> own holding only
  - outsider           -> nothing

Runs against the engine's MockLedgerClient + committed real-rate backtest (zero
creds); swap to JsonLedgerClient for live Canton state once onboarding lands.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE.parent / "engine"
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

app = FastAPI(title="BasisYield on Canton")
_DATA = _ENGINE / "data"
_market = MarketSnapshot(Underlying.CBTC, 65_000.0, funding_rate=0.12, basis=0.01, age_seconds=5.0)
AUM = 1_500_000.0
ROLES = ("auditor", "investor", "outsider")


def _seed_client() -> MockLedgerClient:
    c = MockLedgerClient()
    tick(c, _market, dry_run=False)
    tick(c, _market, dry_run=False)
    c._vault = c.get_vault().__class__(
        contract_id=c.get_vault().contract_id, underlying=Underlying.CBTC,
        total_assets=AUM, total_shares=1_000_000.0)
    tick(c, _market, dry_run=False)
    return c


def _latest_rates() -> tuple[float, float]:
    try:
        rows = json.loads((_DATA / "rwa_rates.json").read_text())
        return rows[-1]["repo_rate"], rows[-1]["mmf_rate"]
    except Exception:
        return 0.0464, 0.0469


def _portfolio() -> dict:
    repo, mmf = _latest_rates()
    quotes = [
        YieldQuote(YieldSourceKind.REPO, "USTB-3M (tokenized Treasury repo)", repo, 1.0),
        YieldQuote(YieldSourceKind.MMF, "MMF-USD (tokenized money-market fund)", mmf, 1.0),
    ]
    targets = target_allocation(quotes, AUM)
    return {
        "allocations": [
            {"kind": t.kind.value, "asset": t.asset,
             "ratePct": round(t.annualized_rate * 100, 2),
             "notional": round(t.target_notional, 2),
             "weightPct": round(t.target_notional / AUM * 100, 1)}
            for t in targets
        ],
        "blendedYieldPct": round(blended_yield(targets, AUM) * 100, 2),
    }


def _pct(x: float) -> float:
    return round(x * 100, 2)


def _stacked() -> dict:
    """The headline: RWA-collateralized carry (collateral T-bill yield + funding),
    blended with a pure-RWA sleeve. Leads with the honest data-driven range."""
    try:
        s = json.loads((_DATA / "stacked_backtest_result.json").read_text())
        lo, med, hi = s["annual_range"]
        return {
            "blendedApyPct": _pct(s["apy"]),
            "lowPct": _pct(lo), "highPct": _pct(hi),
            "todayPct": _pct(s["today_apy"]),
            "floorPct": _pct(s["carry_collateral_apy"]),       # ~ RWA base floor
            "maxDrawdownPct": _pct(s["max_drawdown"]),
            "years": s["years"],
            "stacking": {
                "rwaSleevePct": _pct(s["rwa_sleeve_apy"]),
                "carrySleevePct": _pct(s["carry_sleeve_apy"]),
                "collateralPct": _pct(s["carry_collateral_apy"]),
                "fundingPct": _pct(s["carry_funding_apy"]),
                "avgFundingPct": _pct(s["avg_funding_annual"]),
                "carryFractionPct": _pct(s["carry_fraction"]),
            },
            "navCurve": s["nav_curve"], "navStart": s["nav_start"],
            "source": "Real BTC funding (Binance) + SOFR/T-bill (FRED), 5y — public proxy for Canton RWA-collateralized carry",
        }
    except Exception:
        return {}


_client = _seed_client()


def state_for(role: str) -> dict:
    port = _portfolio()
    overview = {
        "aumUsd": AUM,
        "currentYieldPct": port["blendedYieldPct"],
        "stacked": _stacked(),
    }
    if role == "outsider":
        book = {"visible": False,
                "message": "Need-to-know: an outsider sees no vault, no positions, no holdings."}
    elif role == "investor":
        shares = 50_000.0
        book = {
            "visible": True,
            "scope": "holder",
            "holding": {
                "shares": shares,
                "valueUsd": round(shares * _client.get_vault().price_per_share, 2),
                "yourYieldPct": port["blendedYieldPct"],
            },
            "note": "A holder sees their own holding + NAV + headline yield — not the strategy book.",
        }
    else:  # auditor
        pos = _client.get_position()
        book = {
            "visible": True,
            "scope": "auditor",
            "allocations": port["allocations"],
            "blendedYieldPct": port["blendedYieldPct"],
            "basisPosition": None if pos is None else {
                "shortNotional": pos.short_notional, "longNotional": pos.long_notional,
                "netDelta": pos.net_delta, "carryPct": round(expected_carry(_market) * 100, 2),
            },
            "networkActivity": _client.metrics(),
            "holders": 1,
            "note": "The auditor sees the full book — every allocation, position and holding.",
        }
    return {"role": role, "overview": overview, "book": book}


@app.get("/api/state")
def api_state(role: str = "auditor") -> JSONResponse:
    if role not in ROLES:
        return JSONResponse({"error": f"role must be one of {ROLES}"}, status_code=400)
    return JSONResponse(state_for(role))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_HERE / "index.html").read_text()
