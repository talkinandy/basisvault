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
from fastapi.staticfiles import StaticFiles  # noqa: E402

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
app.mount("/assets", StaticFiles(directory=str(_HERE / "assets")), name="assets")
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


# --------------------------------------------------------------------------- #
# Interactive lifecycle — the RWA track's end-to-end workflow, clickable:
#   create (deposit+allocate) -> update status (accrue) -> transfer -> fulfill
#   (close+redeem) -> audit (the observer feed sees everything, need-to-know
#   filters the rest). Each step names the REAL Daml choices it exercises.
# Backed by the mock ledger driver; swaps to JsonLedgerClient on the sandbox.
# --------------------------------------------------------------------------- #
LC_ROLES = ("issuer", "holder", "observer", "outsider")
LC_STEPS = ["deposit", "allocate", "accrue", "transfer", "close", "redeem"]


def _fresh_lc() -> dict:
    return {"i": 0, "aum": 0.0, "shares": 0.0, "alice": 0.0, "bob": 0.0,
            "allocs": [], "accrued": 0.0, "events": []}


_LC = _fresh_lc()


def _lc_pps() -> float:
    return _LC["aum"] / _LC["shares"] if _LC["shares"] > 0 else 1.0


def _lc_event(step: str, title: str, detail: str, daml: str, visible: list[str]) -> None:
    _LC["events"].append({"step": step, "title": title, "detail": detail,
                          "daml": daml, "visibleTo": visible})


def _lc_run(step: str) -> None:
    repo, mmf = _latest_rates()
    if step == "deposit":
        _LC["aum"] = 1_000_000.0
        _LC["shares"] = 1_000_000.0
        _LC["alice"] = 1_000_000.0
        _lc_event(step, "Alice deposits $1.00M", "1,000,000 shares minted at NAV/share 1.0000",
                  "DepositRequest_Accept → Vault_MintShares", ["issuer", "holder", "observer"])
    elif step == "allocate":
        quotes = [
            YieldQuote(YieldSourceKind.REPO, "USTB-3M tokenized-Treasury repo", repo, 1.0),
            YieldQuote(YieldSourceKind.MMF, "MMF-USD tokenized money-market fund", mmf, 1.0),
        ]
        targets = target_allocation(quotes, _LC["aum"])
        _LC["allocs"] = [{"asset": t.asset, "rate": t.annualized_rate,
                          "notional": t.target_notional} for t in targets]
        for a in _LC["allocs"]:
            _lc_event(step, f"Allocate ${a['notional']/1e6:.2f}M → {a['asset']}",
                      f"approved at the oracle rate {a['rate']*100:.2f}%/yr",
                      "Vault_ProposeAllocation → AllocationProposal_Approve",
                      ["issuer", "observer"])
    elif step == "accrue":
        earned = sum(a["notional"] * a["rate"] * 0.25 for a in _LC["allocs"])
        _LC["aum"] += earned
        _LC["accrued"] += earned
        _lc_event(step, f"One quarter of yield accrues: +${earned:,.0f}",
                  f"realized only — principal × oracle rate × 0.25y; NAV/share → {_lc_pps():.4f}",
                  "Vault_AccrueAllocation", ["issuer", "observer"])
        _lc_event(step, "Your holding grew",
                  f"your {_LC['alice']:,.0f} shares are now worth ${_LC['alice']*_lc_pps():,.0f}",
                  "(your view of the same accrual)", ["holder"])
    elif step == "transfer":
        _LC["bob"] = _LC["alice"]
        _LC["alice"] = 0.0
        _lc_event(step, "Alice transfers her holding to Bob",
                  "propose → Bob accepts → issuer settles; share count unchanged. "
                  "Only Alice, Bob, issuer and the observer ever see this.",
                  "ShareHolding_ProposeTransfer → TransferProposal_Accept → AcceptedTransfer_Settle",
                  ["issuer", "holder", "observer"])
    elif step == "close":
        _lc_event(step, "Allocations closed — capital back to idle NAV",
                  f"realized yield (${_LC['accrued']:,.0f}) already in NAV; nothing invented",
                  "Vault_CloseAllocation", ["issuer", "observer"])
        _LC["allocs"] = []
    elif step == "redeem":
        value = _LC["bob"] * _lc_pps()
        _lc_event(step, f"Bob redeems at the higher NAV: ${value:,.0f}",
                  f"entered via transfer at NAV/share {_lc_pps():.4f} — yield travelled with the shares",
                  "RedeemRequest_Accept → Vault_BurnShares", ["issuer", "observer"])
        _LC["aum"] -= value
        _LC["shares"] = 0.0
        _LC["bob"] = 0.0


def _lc_view(role: str) -> dict:
    # issuer signs everything and the observer audits everything — they see ALL
    # events (the whole thesis); the holder sees only their own; outsider none.
    if role in ("issuer", "observer"):
        visible = list(_LC["events"])
    elif role == "holder":
        visible = [e for e in _LC["events"] if "holder" in e["visibleTo"]]
    else:
        visible = []
    hidden = len(_LC["events"]) - len(visible)
    pps = _lc_pps()
    rnd = lambda x, n=2: round(x, n) or 0.0  # noqa: E731 — kill negative zero
    return {
        "steps": LC_STEPS, "next": LC_STEPS[_LC["i"]] if _LC["i"] < len(LC_STEPS) else None,
        "done": _LC["i"],
        "state": {"aumUsd": rnd(_LC["aum"]), "navPerShare": rnd(pps, 4),
                  "aliceUsd": rnd(_LC["alice"] * pps), "bobUsd": rnd(_LC["bob"] * pps),
                  "accruedUsd": rnd(_LC["accrued"])},
        "events": visible, "hiddenCount": hidden,
        "role": role,
    }


@app.get("/api/lifecycle")
def api_lifecycle(role: str = "observer") -> JSONResponse:
    if role not in LC_ROLES:
        return JSONResponse({"error": f"role must be one of {LC_ROLES}"}, status_code=400)
    return JSONResponse(_lc_view(role))


@app.post("/api/lifecycle/next")
def api_lifecycle_next(role: str = "observer") -> JSONResponse:
    if _LC["i"] < len(LC_STEPS):
        _lc_run(LC_STEPS[_LC["i"]])
        _LC["i"] += 1
    return JSONResponse(_lc_view(role))


@app.post("/api/lifecycle/reset")
def api_lifecycle_reset(role: str = "observer") -> JSONResponse:
    global _LC
    _LC = _fresh_lc()
    return JSONResponse(_lc_view(role))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_HERE / "index.html").read_text()
