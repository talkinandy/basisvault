"""BasisYield on Canton — MVP dashboard.

A designed, user-facing product page (BasisYield "Sunrise" brand) over the
BasisVault on-chain vault + off-chain carry engine. Serves:
  - GET /                 the landing/dashboard page (web/index.html)
  - GET /api/state?role=  public product overview + role-gated live book

THE MECHANISM (this phase, on Canton's live asset menu):
  short the BTC/ETH perp on Hyperliquid (receive funding) + long cBTC/cETH
  spot custodied on Canton (cancel price) — the production BasisYield
  cash-and-carry with the spot leg moved into Canton custody. Next phase:
  tokenized-RWA margin (DBS gold, T-bills) stacking base yield on the carry.

Privacy demo = the role switch. The marketing page is public; the *live book*
(positions, holdings) is need-to-know:
  - auditor (observer) -> full book   · investor (holder) -> own holding only
  - outsider           -> nothing
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE.parent / "engine"
sys.path.insert(0, str(_ENGINE))

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from basisvault_engine.backtest import (  # noqa: E402
    capital_efficiency,
    optimal_leverage,
)

sys.path.insert(0, str(_HERE))
from ledger_bridge import LedgerBridge  # noqa: E402

app = FastAPI(title="BasisYield on Canton")
BRIDGE = LedgerBridge()
app.mount("/assets", StaticFiles(directory=str(_HERE / "assets")), name="assets")
_DATA = _ENGINE / "data"
AUM = 1_500_000.0
ROLES = ("auditor", "investor", "outsider")

LEVERAGE = optimal_leverage(0.02, 0.15, 10)          # 5x — liquidation-buffer bound
CAP_EFF = capital_efficiency(LEVERAGE)               # 83% of capital earns funding

CARRY_ASSETS = {          # perp shorted on HL -> spot custodied on Canton
    "CBTC": {"perp": "BTC", "spot": "cBTC (BitSafe, CIP-56)"},
    "CETH": {"perp": "ETH", "spot": "cETH (OnRails, CIP-56)"},
}


def _pct(x: float) -> float:
    return round(x * 100, 2)


# ---------- real market inputs (honest, but never load-bearing) ----------
def _trailing_funding(days: int = 30) -> dict[str, float]:
    """Trailing annualized HL funding per asset from the committed real data."""
    out = {}
    for u in CARRY_ASSETS:
        try:
            rows = json.loads((_DATA / f"hl_{'btc' if u == 'CBTC' else 'eth'}_funding.json").read_text())
            cutoff = rows[-1]["time"] - days * 86_400_000
            win = [r for r in rows if r["time"] >= cutoff]
            yrs = (win[-1]["time"] - win[0]["time"]) / (365 * 24 * 3600 * 1000)
            out[u] = sum(r["fundingRate"] for r in win) / yrs if yrs > 0 else 0.0
        except Exception:
            out[u] = 0.05
    return out


_marks_cache: tuple[float, dict[str, float]] = (0.0, {})


def _hl_marks() -> dict[str, float]:
    """Live BTC/ETH mid marks from Hyperliquid (the venue the short trades on);
    cached 60s; falls back to static marks offline."""
    global _marks_cache
    ts, cached = _marks_cache
    if cached and time.time() - ts < 60:
        return cached
    try:
        r = httpx.post("https://api.hyperliquid.xyz/info",
                       json={"type": "allMids"}, timeout=5.0)
        r.raise_for_status()
        mids = r.json()
        marks = {"CBTC": float(mids["BTC"]), "CETH": float(mids["ETH"])}
        _marks_cache = (time.time(), marks)
        return marks
    except Exception:
        return cached or {"CBTC": 118_000.0, "CETH": 4_200.0}


# ---------- backtest payloads ----------
def _carry() -> dict:
    """THE HERO: cash-and-carry on real Hyperliquid funding (3.2y), short HL
    perp + long cBTC/cETH on Canton. Leads with the honest rolling-1y range."""
    try:
        c = json.loads((_DATA / "hl_carry_backtest_result.json").read_text())
        lo, med, hi = c["annual_range"]
        return {
            "apyPct": _pct(c["apy"]),
            "lowPct": _pct(lo), "medianPct": _pct(med), "highPct": _pct(hi),
            "todayPct": _pct(c["today_apy"]),
            "maxDrawdownPct": _pct(c["max_drawdown"]),
            "years": c["years"],
            "leverage": c["leverage"],
            "capitalEfficiencyPct": _pct(c["capital_efficiency"]),
            "sleeves": [
                {"asset": s["asset"], "apyPct": _pct(s["apy"]),
                 "deployedPct": _pct(s["pct_time_deployed"]),
                 "avgFundingPct": _pct(s["avg_funding_annual"]),
                 "roundTrips": s["unwinds"]}
                for s in c["sleeves"]
            ],
            "navCurve": c["nav_curve"], "navStart": c["nav_start"],
            "source": "Real Hyperliquid BTC+ETH funding prints (hourly, 3.2y) — the venue the short leg trades on",
        }
    except Exception:
        return {}


def _stacked() -> dict:
    """NEXT PHASE: RWA-collateralized carry (tokenized T-bill/gold margin
    stacking base yield on the funding) — the Canton edge once RWAs ship."""
    try:
        s = json.loads((_DATA / "stacked_backtest_result.json").read_text())
        lo, med, hi = s["annual_range"]
        return {
            "blendedApyPct": _pct(s["apy"]),
            "lowPct": _pct(lo), "highPct": _pct(hi),
            "todayPct": _pct(s["today_apy"]),
            "floorPct": _pct(s["carry_collateral_apy"]),
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
            "source": "Real BTC funding + SOFR/T-bill (FRED), 5y — projection for tokenized-RWA margin on Canton",
        }
    except Exception:
        return {}


def state_for(role: str) -> dict:
    funding = _trailing_funding()
    blended_now = sum(funding.values()) / len(funding) * CAP_EFF
    overview = {
        "aumUsd": AUM,
        "currentYieldPct": _pct(blended_now),
        "carry": _carry(),
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
                "valueUsd": round(shares * 1.0, 2),
                "yourYieldPct": _pct(blended_now),
            },
            "note": "A holder sees their own holding + NAV + headline yield — not the strategy book.",
        }
    else:  # auditor
        marks = _hl_marks()
        deploy = AUM * 0.8 / len(CARRY_ASSETS)
        book = {
            "visible": True,
            "scope": "auditor",
            "positions": [
                {"underlying": u,
                 "shortLeg": f"short {m['perp']} perp · Hyperliquid",
                 "longLeg": f"long {m['spot']} · Canton custody",
                 "notional": round(deploy * CAP_EFF, 2),
                 "markPrice": marks.get(u, 0.0),
                 "fundingAprPct": _pct(funding.get(u, 0.0)),
                 "netDelta": 0.0,
                 "margin": "USDCx"}
                for u, m in CARRY_ASSETS.items()
            ],
            "leverage": LEVERAGE,
            "capitalEfficiencyPct": _pct(CAP_EFF),
            "blendedYieldPct": _pct(blended_now),
            "holders": 1,
            "note": "The auditor sees the full book — every position, leg and holding.",
        }
    return {"role": role, "overview": overview, "book": book}


@app.get("/api/state")
def api_state(role: str = "auditor") -> JSONResponse:
    if role not in ROLES:
        return JSONResponse({"error": f"role must be one of {ROLES}"}, status_code=400)
    return JSONResponse(state_for(role))


# --------------------------------------------------------------------------- #
# Interactive lifecycle — the track's end-to-end workflow, clickable:
#   create (deposit + open the carry pair) -> update status (accrue REAL
#   funding) -> transfer -> fulfill (unwind + redeem) -> audit (the observer
#   feed sees everything, need-to-know filters the rest). Each step names the
#   REAL Daml choices it exercises; on the sandbox they run as REAL txs.
# --------------------------------------------------------------------------- #
LC_ROLES = ("issuer", "holder", "observer", "outsider")
LC_STEPS = ["deposit", "open", "accrue", "transfer", "unwind", "redeem"]


LC_ROLE_PARTY = {"issuer": "operator", "holder": "alice",
                 "observer": "auditor", "outsider": "mallory"}

_DEMO_AUM = 1_000_000.0
_DEMO_NOTIONAL = 400_000.0        # per asset: 2 pairs × $400k = 80% deployed


def _fresh_lc(mode: str = "mock") -> dict:
    return {"i": 0, "aum": 0.0, "shares": 0.0, "alice": 0.0, "bob": 0.0,
            "positions": [], "accrued": 0.0, "events": [], "mode": mode,
            "accrual": None}


def _accrual_detail(assets: list[dict], total: float) -> dict:
    """Per-pair anatomy for the step-3 visual: both legs, margin, and the
    realized funding flow — real numbers from the run."""
    return {
        "assets": assets,
        "totalEarnedUsd": round(total, 2),
        "leverage": LEVERAGE,
        "capitalEfficiencyPct": _pct(CAP_EFF),
        "perPairCapitalUsd": round(_DEMO_NOTIONAL * (1 + 1 / LEVERAGE), 2),
    }


_LC = _fresh_lc("ledger" if BRIDGE.ensure() else "mock")


def _lc_pps() -> float:
    return _LC["aum"] / _LC["shares"] if _LC["shares"] > 0 else 1.0


def _lc_event(step: str, title: str, detail: str, daml: str, visible: list[str],
              update_id: str | None = None) -> None:
    _LC["events"].append({"step": step, "title": title, "detail": detail,
                          "daml": daml, "visibleTo": visible,
                          "updateId": update_id})


def _open_title(u: str, funding: dict[str, float]) -> tuple[str, str]:
    m = CARRY_ASSETS[u]
    title = f"Open carry: short {m['perp']} perp (HL) + long {m['spot'].split(' (')[0]} on Canton"
    detail = (f"${_DEMO_NOTIONAL/1e6:.1f}M each leg at the oracle mark — net delta 0; "
              f"USDCx margin, {LEVERAGE}x perp; trailing HL funding "
              f"{funding.get(u, 0.0)*100:+.1f}% APR")
    return title, detail


def _lc_run(step: str) -> None:
    funding = _trailing_funding()
    if step == "deposit":
        _LC["aum"] = _DEMO_AUM
        _LC["shares"] = _DEMO_AUM
        _LC["alice"] = _DEMO_AUM
        _lc_event(step, "Alice deposits $1.00M (USDCx)", "1,000,000 shares minted at NAV/share 1.0000",
                  "DepositRequest_Accept → Vault_MintShares", ["issuer", "holder", "observer"])
    elif step == "open":
        marks = _hl_marks()
        for u in CARRY_ASSETS:
            _LC["positions"].append({"underlying": u, "notional": _DEMO_NOTIONAL,
                                     "rate": funding.get(u, 0.05), "mark": marks.get(u, 0.0)})
            title, detail = _open_title(u, funding)
            _lc_event(step, title, detail,
                      "Vault_ProposeRebalance → RebalanceProposal_Approve",
                      ["issuer", "observer"])
    elif step == "accrue":
        earned = sum(p["notional"] * p["rate"] * 0.25 for p in _LC["positions"])
        _LC["aum"] += earned
        _LC["accrued"] += earned
        _LC["accrual"] = _accrual_detail([
            {"underlying": p["underlying"],
             "perp": CARRY_ASSETS[p["underlying"]]["perp"],
             "spot": CARRY_ASSETS[p["underlying"]]["spot"],
             "notionalUsd": p["notional"], "aprPct": _pct(p["rate"]),
             "marginUsd": round(p["notional"] / LEVERAGE, 2),
             "earnedUsd": round(p["notional"] * p["rate"] * 0.25, 2)}
            for p in _LC["positions"]], earned)
        _lc_event(step, f"One quarter of funding accrues: +${earned:,.0f}",
                  f"realized only — notional × trailing HL funding × 0.25y; NAV/share → {_lc_pps():.4f}",
                  "Vault_AccrueFunding", ["issuer", "observer"])
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
    elif step == "unwind":
        _lc_event(step, "Sign guard unwinds both carry pairs",
                  f"funding decays below the exit floor → both legs close; realized funding "
                  f"(${_LC['accrued']:,.0f}) already in NAV; the short never pays through a negative regime",
                  "Vault_UnwindPosition → DeltaNeutralPosition_Unwind", ["issuer", "observer"])
        _LC["positions"] = []
    elif step == "redeem":
        value = _LC["bob"] * _lc_pps()
        _lc_event(step, f"Bob redeems at the higher NAV: ${value:,.0f}",
                  f"entered via transfer at NAV/share {_lc_pps():.4f} — yield travelled with the shares",
                  "RedeemRequest_Accept → Vault_BurnShares", ["issuer", "observer"])
        _LC["aum"] -= value
        _LC["shares"] = 0.0
        _LC["bob"] = 0.0
        _LC["accrual"] = None


def _lc_sync_from_ledger() -> None:
    """Refresh the state strip numbers from the REAL ledger's ACS."""
    v = BRIDGE.vault()
    _LC["aum"] = float(v["arg"]["totalAssets"]) if v else 0.0
    _LC["shares"] = float(v["arg"]["totalShares"]) if v else 0.0
    _LC["alice"] = sum(float(h["arg"]["shares"]) for h in BRIDGE.find("alice", "ShareHolding"))
    _LC["bob"] = sum(float(h["arg"]["shares"]) for h in BRIDGE.find("bob", "ShareHolding"))


def _lc_run_ledger(step: str) -> None:
    """Run one lifecycle step as REAL Daml transactions on the sandbox."""
    br = BRIDGE
    funding = _trailing_funding()
    if step == "deposit":
        r1 = br.create("alice", "DepositRequest", {
            "operator": br.party["operator"], "investor": br.party["alice"],
            "amount": f"{_DEMO_AUM:.1f}", "vaultCid": br.vault_cid()})
        dep = next(c for c in r1["created"] if c["entity"] == "DepositRequest")
        r2 = br.exercise("operator", "DepositRequest", dep["cid"], "DepositRequest_Accept")
        _lc_event(step, "Alice deposits $1.00M (USDCx)", "1,000,000 shares minted at NAV/share 1.0000",
                  "DepositRequest_Accept → Vault_MintShares",
                  ["issuer", "holder", "observer"], r2["updateId"])
    elif step == "open":
        marks = _hl_marks()
        for u in CARRY_ASSETS:
            # oracle publishes the mark (live HL mid) + the funding feed
            br.create("oracle", "PriceFeed", {
                "oracle": br.party["oracle"], "operator": br.party["operator"],
                "underlying": {"tag": u, "value": {}},
                "price": f"{marks.get(u, 0.0):.2f}"},
                module="BasisVault.Venue")
            br.create("oracle", "RateFeed", {
                "oracle": br.party["oracle"], "operator": br.party["operator"],
                "kind": "Basis", "asset": f"{CARRY_ASSETS[u]['perp']}-PERP-HL",
                "annualizedRate": f"{max(funding.get(u, 0.05), 0.0):.10f}"},
                module="BasisVault.YieldSource")
            rp = br.exercise("manager", "Vault", br.vault_cid(), "Vault_ProposeRebalance",
                             {"plan": {"underlying": {"tag": u, "value": {}},
                                       "shortVenue": "Hyperliquid", "longVenue": "Cantex",
                                       "notional": f"{_DEMO_NOTIONAL:.1f}",
                                       "collateralAsset": "USDCx", "collateralRate": "0.0"}})
            prop = next(c for c in rp["created"] if c["entity"] == "RebalanceProposal")
            feed = next(f for f in br.find("oracle", "PriceFeed")
                        if f["arg"]["underlying"]["tag"] == u)
            ra = br.exercise("operator", "RebalanceProposal", prop["cid"],
                             "RebalanceProposal_Approve", {"priceFeedCid": feed["cid"]})
            title, detail = _open_title(u, funding)
            _lc_event(step, title, detail,
                      "Vault_ProposeRebalance → RebalanceProposal_Approve",
                      ["issuer", "observer"], ra["updateId"])
    elif step == "accrue":
        total = 0.0
        last_up = None
        detail: list[dict] = []
        for pos in br.find("operator", "DeltaNeutralPosition"):
            u = pos["arg"]["underlying"]["tag"]
            feed = next(f for f in br.find("oracle", "RateFeed")
                        if f["arg"]["asset"].startswith(CARRY_ASSETS[u]["perp"]))
            r = br.exercise("operator", "Vault", br.vault_cid(), "Vault_AccrueFunding",
                            {"positionCid": pos["cid"], "rateFeedCid": feed["cid"],
                             "yearFraction": "0.25"},
                            )
            notional = float(pos["arg"]["shortNotional"])
            rate = float(feed["arg"]["annualizedRate"])
            earned = notional * rate * 0.25
            total += earned
            last_up = r["updateId"]
            detail.append({
                "underlying": u, "perp": CARRY_ASSETS[u]["perp"],
                "spot": CARRY_ASSETS[u]["spot"],
                "notionalUsd": notional, "aprPct": _pct(rate),
                "marginUsd": round(notional / LEVERAGE, 2),
                "earnedUsd": round(earned, 2)})
        _LC["accrued"] += total
        _LC["accrual"] = _accrual_detail(detail, total)
        _lc_sync_from_ledger()
        _lc_event(step, f"One quarter of funding accrues: +${total:,.0f}",
                  f"realized only — notional × trailing HL funding × 0.25y; NAV/share → {_lc_pps():.4f}",
                  "Vault_AccrueFunding", ["issuer", "observer"], last_up)
        _lc_event(step, "Your holding grew",
                  f"your {_LC['alice']:,.0f} shares are now worth ${_LC['alice']*_lc_pps():,.0f}",
                  "(your view of the same accrual)", ["holder"], last_up)
    elif step == "transfer":
        hold = br.find("alice", "ShareHolding")[0]
        rp = br.exercise("alice", "ShareHolding", hold["cid"], "ShareHolding_ProposeTransfer",
                         {"newHolder": br.party["bob"]})
        prop = next(c for c in rp["created"] if c["entity"] == "TransferProposal")
        ra = br.exercise("bob", "TransferProposal", prop["cid"], "TransferProposal_Accept")
        acc = next(c for c in ra["created"] if c["entity"] == "AcceptedTransfer")
        rs = br.exercise("operator", "AcceptedTransfer", acc["cid"], "AcceptedTransfer_Settle")
        _lc_event(step, "Alice transfers her holding to Bob",
                  "propose → Bob accepts → issuer settles; share count unchanged. "
                  "Only Alice, Bob, issuer and the observer ever see this.",
                  "ShareHolding_ProposeTransfer → TransferProposal_Accept → AcceptedTransfer_Settle",
                  ["issuer", "holder", "observer"], rs["updateId"])
    elif step == "unwind":
        last_up = None
        for pos in br.find("operator", "DeltaNeutralPosition"):
            r = br.exercise("operator", "Vault", br.vault_cid(), "Vault_UnwindPosition",
                            {"positionCid": pos["cid"]})
            last_up = r["updateId"]
        _lc_event(step, "Sign guard unwinds both carry pairs",
                  f"funding decays below the exit floor → both legs close; realized funding "
                  f"(${_LC['accrued']:,.0f}) already in NAV; the short never pays through a negative regime",
                  "Vault_UnwindPosition → DeltaNeutralPosition_Unwind",
                  ["issuer", "observer"], last_up)
    elif step == "redeem":
        hold = br.find("bob", "ShareHolding")[0]
        value = float(hold["arg"]["shares"]) * _lc_pps()
        rr = br.exercise("bob", "ShareHolding", hold["cid"], "ShareHolding_RequestRedeem")
        req = next(c for c in rr["created"] if c["entity"] == "RedeemRequest")
        r = br.exercise("operator", "RedeemRequest", req["cid"], "RedeemRequest_Accept",
                        {"vaultCid": br.vault_cid()})
        _lc_event(step, f"Bob redeems at the higher NAV: ${value:,.0f}",
                  f"entered via transfer at NAV/share {_lc_pps():.4f} — yield travelled with the shares",
                  "RedeemRequest_Accept → Vault_BurnShares", ["issuer", "observer"], r["updateId"])
        _LC["accrual"] = None
    _lc_sync_from_ledger()


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
        "ledger": _lc_ledger_info(role),
        "accrual": _LC.get("accrual") if role in ("issuer", "observer") else None,
        # the raw JSON Ledger API exchanges behind the buttons — same for every
        # role (it's OUR app's traffic; role privacy applies to ledger reads,
        # not to showing what the demo itself submitted)
        "wire": BRIDGE.wire if _LC["mode"] == "ledger" else [],
    }


def _lc_ledger_info(role: str) -> dict:
    """Proof block: is this running on a real Canton ledger, and how many
    contracts can THIS role's party actually see on it (Canton-enforced)."""
    if _LC["mode"] != "ledger":
        return {"live": False}
    try:
        n = len(BRIDGE.acs(LC_ROLE_PARTY[role]))
        return {"live": True, "visibleContracts": n,
                "participant": BRIDGE.label}
    except Exception:
        return {"live": False}


@app.get("/api/lifecycle")
def api_lifecycle(role: str = "observer") -> JSONResponse:
    if role not in LC_ROLES:
        return JSONResponse({"error": f"role must be one of {LC_ROLES}"}, status_code=400)
    return JSONResponse(_lc_view(role))


_LC_LOCK = threading.Lock()


@app.post("/api/lifecycle/next")
def api_lifecycle_next(role: str = "observer") -> JSONResponse:
    if not _LC_LOCK.acquire(blocking=False):
        return JSONResponse({**_lc_view(role), "busy": True}, status_code=409)
    try:
        if _LC["i"] < len(LC_STEPS):
            step = LC_STEPS[_LC["i"]]
            if _LC["i"] == 0 and _LC["mode"] != "ledger" and BRIDGE.ensure():
                _LC["mode"] = "ledger"  # sandbox came up after the app — upgrade
            if _LC["mode"] == "ledger" and BRIDGE.ensure():
                try:
                    _lc_run_ledger(step)
                except Exception as e:
                    return JSONResponse({**_lc_view(role), "ledgerError": str(e)[:300]},
                                        status_code=502)
            else:
                _LC["mode"] = "mock"
                _lc_run(step)
            _LC["i"] += 1
        return JSONResponse(_lc_view(role))
    finally:
        _LC_LOCK.release()


@app.post("/api/lifecycle/reset")
def api_lifecycle_reset(role: str = "observer") -> JSONResponse:
    global _LC
    if not _LC_LOCK.acquire(blocking=False):
        return JSONResponse({**_lc_view(role), "busy": True}, status_code=409)
    try:
        if BRIDGE.ensure():
            BRIDGE.reset()
            _LC = _fresh_lc("ledger")
        else:
            _LC = _fresh_lc("mock")
        return JSONResponse(_lc_view(role))
    finally:
        _LC_LOCK.release()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_HERE / "index.html").read_text()
