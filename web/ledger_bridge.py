"""Bridge to a REAL Canton ledger (daml sandbox) via the JSON Ledger API v2.

Drives the lifecycle demo as actual on-ledger Daml transactions: every step
submits commands to the participant on 127.0.0.1:7575, and every role view is a
real per-party ACS query — so the need-to-know filtering the UI shows is
enforced by Canton itself, not simulated.

Bootstrap is lazy + idempotent (the sandbox is in-memory; a restart wipes it):
allocate parties, create the API user with actAs/readAs rights, create the Vault.
If the sandbox is unreachable the web app falls back to its mock driver.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx

log = logging.getLogger("basisvault.ledger")

PKG = "#basisvault"
HINTS = ("operator", "manager", "auditor", "oracle", "alice", "bob", "mallory")

# Point the bridge at any participant's JSON Ledger API v2 — the local sandbox
# by default, a Canton DevNet/TestNet validator participant via env:
#   LEDGER_API_BASE   e.g. http://127.0.0.1:7575 (sandbox) or the validator's
#                     json-api endpoint
#   LEDGER_API_TOKEN  bearer JWT if the participant requires auth (testnet does;
#                     the sandbox doesn't)
#   LEDGER_API_HOST   Host header override — the Splice compose validator routes
#                     everything through one nginx on :80 by virtual host, so a
#                     validator deployment needs "json-ledger-api.localhost"
#   LEDGER_USER_ID    ledger user the app acts through (default "basisyield")
#   LEDGER_LABEL      participant label shown in the UI proof block
BASE = os.environ.get("LEDGER_API_BASE", "http://127.0.0.1:7575")
TOKEN = os.environ.get("LEDGER_API_TOKEN", "")
HOST = os.environ.get("LEDGER_API_HOST", "")
USER = os.environ.get("LEDGER_USER_ID", "basisyield")
LABEL = os.environ.get("LEDGER_LABEL", "canton sandbox · JSON Ledger API v2")
# shared nodes allocate namespaced hints, e.g. "basisvault-operator" — set
# LEDGER_PARTY_PREFIX=basisvault- to map them onto our role hints
PREFIX = os.environ.get("LEDGER_PARTY_PREFIX", "")

# OIDC auto-refresh (shared DevNet nodes front the ledger API with Keycloak;
# access tokens live minutes, so a static LEDGER_API_TOKEN dies mid-demo).
# Set these and the bridge keeps itself authenticated:
#   LEDGER_OIDC_TOKEN_URL      Keycloak token endpoint
#   LEDGER_OIDC_CLIENT_ID      e.g. web-app-ui-hackcanton-01-devnet
#   LEDGER_OIDC_SCOPE          e.g. "openid daml_ledger_api offline_access"
#   LEDGER_OIDC_REFRESH_TOKEN  offline/refresh token (preferred), or
#   LEDGER_OIDC_USERNAME / LEDGER_OIDC_PASSWORD   password grant
OIDC_URL = os.environ.get("LEDGER_OIDC_TOKEN_URL", "")
OIDC_CLIENT = os.environ.get("LEDGER_OIDC_CLIENT_ID", "")
OIDC_SCOPE = os.environ.get("LEDGER_OIDC_SCOPE", "openid daml_ledger_api offline_access")
OIDC_REFRESH = os.environ.get("LEDGER_OIDC_REFRESH_TOKEN", "")
OIDC_USER = os.environ.get("LEDGER_OIDC_USERNAME", "")
OIDC_PASS = os.environ.get("LEDGER_OIDC_PASSWORD", "")


class _OidcAuth(httpx.Auth):
    """Bearer auth that refreshes itself against Keycloak before expiry."""

    def __init__(self) -> None:
        self._access = ""
        self._exp = 0.0
        self._refresh = OIDC_REFRESH

    def _fetch(self) -> None:
        import time
        if self._refresh:
            form = {"grant_type": "refresh_token", "client_id": OIDC_CLIENT,
                    "refresh_token": self._refresh}
        else:
            form = {"grant_type": "password", "client_id": OIDC_CLIENT,
                    "username": OIDC_USER, "password": OIDC_PASS,
                    "scope": OIDC_SCOPE}
        r = httpx.post(OIDC_URL, data=form, timeout=20.0)
        r.raise_for_status()
        tok = r.json()
        self._access = tok["access_token"]
        self._exp = time.time() + float(tok.get("expires_in", 300)) - 60
        if tok.get("refresh_token"):        # Keycloak may rotate it
            self._refresh = tok["refresh_token"]

    def auth_flow(self, request):
        import time
        if not self._access or time.time() >= self._exp:
            self._fetch()
        request.headers["Authorization"] = f"Bearer {self._access}"
        yield request

# template short-name -> archiving authority (signatory), for reset()
_ARCHIVE_AS = {
    "Vault": "operator", "ShareHolding": "operator", "Allocation": "operator",
    "VenueLeg": "operator", "DeltaNeutralPosition": "operator",
    "AllocationProposal": "manager", "RebalanceProposal": "manager",
    "RateFeed": "oracle", "PriceFeed": "oracle",
}


def _tpl(entity: str, module: str = "BasisVault.Vault") -> str:
    return f"{PKG}:{module}:{entity}"


class LedgerBridge:
    def __init__(self, base: str | None = None) -> None:
        headers = {}
        auth = None
        if OIDC_URL and OIDC_CLIENT and (OIDC_REFRESH or (OIDC_USER and OIDC_PASS)):
            auth = _OidcAuth()          # self-refreshing bearer (shared DevNet node)
        elif TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        if HOST:
            headers["Host"] = HOST
        self._http = httpx.Client(base_url=base or BASE, timeout=25.0,
                                  headers=headers, auth=auth)
        self.label = LABEL
        self.party: dict[str, str] = {}
        self._ready = False
        # "on the wire": the last raw JSON Ledger API exchanges (proof the demo
        # is real traffic, not a facade) — rendered by the UI's terminal panel
        self.wire: list[dict] = []

    def _record(self, method: str, path: str, request: Any, status: int,
                response: Any, ms: int) -> None:
        import time as _t

        def _trunc(x: Any, n: int) -> str:
            s = x if isinstance(x, str) else __import__("json").dumps(x, separators=(",", ":"))
            return s if len(s) <= n else s[:n] + f"… (+{len(s)-n} chars)"

        self.wire.append({
            "time": _t.strftime("%H:%M:%S UTC", _t.gmtime()),
            "method": method, "path": path, "status": status, "ms": ms,
            "request": _trunc(request, 900), "response": _trunc(response, 600),
        })
        del self.wire[:-10]

    # ---------- bootstrap ----------
    def ensure(self) -> bool:
        """True when the sandbox is reachable and bootstrapped."""
        try:
            if self._ready and self.party:
                # cheap liveness probe
                self._http.get("/v2/state/ledger-end").raise_for_status()
                return True
            self._bootstrap()
            self._ready = True
            return True
        except Exception as e:  # sandbox down -> mock fallback
            log.warning("ledger unavailable: %s", e)
            self._ready = False
            return False

    def _bootstrap(self) -> None:
        try:
            existing = {p["party"].split("::")[0]: p["party"] for p in self._parties()}
        except Exception as e:
            # shared node: the party directory is admin-gated — discover our
            # parties from the rights the operator granted our user instead
            log.warning("party listing unavailable (%s); using granted rights", e)
            r = self._http.get(f"/v2/users/{USER}/rights")
            r.raise_for_status()
            existing = {}
            for right in r.json().get("rights", []):
                for kind in ("CanActAs", "CanReadAs"):
                    p = right.get("kind", {}).get(kind, {}).get("value", {}).get("party")
                    if p:
                        existing[p.split("::")[0]] = p
        for h in HINTS:
            if PREFIX + h not in existing:
                r = self._http.post("/v2/parties", json={
                    "partyIdHint": PREFIX + h, "identityProviderId": ""})
                if r.status_code in (401, 403):
                    # shared node: allocation is admin-gated — parties must be
                    # pre-allocated by the operator (see docs/TESTNET.md)
                    log.warning("party allocation forbidden; missing hint %r", PREFIX + h)
                    continue
                r.raise_for_status()
                existing[PREFIX + h] = r.json()["partyDetails"]["party"]
        missing = [h for h in HINTS if PREFIX + h not in existing]
        if missing:
            raise RuntimeError(
                f"parties missing and not allocatable on this participant: {missing}")
        self.party = {h: existing[PREFIX + h] for h in HINTS}

        rights = ([{"kind": {"CanActAs": {"value": {"party": p}}}} for p in self.party.values()]
                  + [{"kind": {"CanReadAs": {"value": {"party": p}}}} for p in self.party.values()])
        r = self._http.post("/v2/users", json={
            "user": {"id": USER, "primaryParty": "", "isDeactivated": False,
                     "identityProviderId": "",
                     "metadata": {"resourceVersion": "", "annotations": {}}},
            "rights": rights})
        if r.status_code == 409:  # user exists — top up rights (e.g. new party)
            self._http.post(f"/v2/users/{USER}/rights", json={
                "userId": USER, "rights": rights, "identityProviderId": ""})
        elif r.status_code in (401, 403):
            # shared node: user admin is gated — trust the operator-granted
            # rights and verify we can actually read as our parties
            log.warning("user management forbidden; relying on pre-granted rights")
            self._http.get(f"/v2/users/{USER}").raise_for_status()
        else:
            r.raise_for_status()

        if not self.vault_cid():
            self.create_vault()

    def _parties(self) -> list[dict]:
        r = self._http.get("/v2/parties")
        r.raise_for_status()
        return r.json()["partyDetails"]

    # ---------- reads ----------
    def _ledger_end(self) -> int:
        return self._http.get("/v2/state/ledger-end").json()["offset"]

    def acs(self, hint: str) -> list[dict]:
        """Active contracts visible to `hint`'s party — Canton-enforced."""
        party = self.party[hint]
        r = self._http.post("/v2/state/active-contracts", json={
            "filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"WildcardFilter": {
                    "value": {"includeCreatedEventBlob": False}}}}]}}},
            "verbose": False, "activeAtOffset": self._ledger_end()})
        r.raise_for_status()
        out = []
        for row in r.json():
            ev = row.get("contractEntry", {}).get("JsActiveContract", {}).get("createdEvent")
            if ev:
                out.append({"template": ev["templateId"].split(":", 1)[1],
                            "entity": ev["templateId"].rsplit(":", 1)[1],
                            "cid": ev["contractId"],
                            "arg": ev.get("createArgument", {})})
        return out

    def find(self, hint: str, entity: str) -> list[dict]:
        return [c for c in self.acs(hint) if c["entity"] == entity]

    def _pick_vault(self) -> dict | None:
        """Deterministic vault choice: the funded one wins (a stray empty vault
        can survive a reset race on a shared node); ties break on contract id
        so every query in a step agrees on the same vault."""
        vs = self.find("operator", "Vault")
        if not vs:
            return None
        return max(vs, key=lambda v: (float(v["arg"].get("totalShares", 0) or 0),
                                      float(v["arg"].get("totalAssets", 0) or 0),
                                      v["cid"]))

    def vault_cid(self) -> str | None:
        v = self._pick_vault()
        return v["cid"] if v else None

    def vault(self) -> dict | None:
        return self._pick_vault()

    # ---------- writes ----------
    def submit(self, act_as: list[str], commands: list[dict]) -> dict:
        """submit-and-wait-for-transaction; returns {updateId, created:[...]}."""
        parties = [self.party[h] for h in act_as]
        body = {
            "commands": {"commands": commands,
                         "commandId": f"lc-{uuid.uuid4().hex[:16]}",
                         "actAs": parties, "userId": USER},
            "transactionFormat": {
                "eventFormat": {
                    "filtersByParty": {p: {"cumulative": [
                        {"identifierFilter": {"WildcardFilter": {
                            "value": {"includeCreatedEventBlob": False}}}}]}
                        for p in parties},
                    "verbose": False},
                "transactionShape": "TRANSACTION_SHAPE_ACS_DELTA"},
        }
        import time as _t
        t0 = _t.monotonic()
        r = self._http.post("/v2/commands/submit-and-wait-for-transaction", json=body)
        ms = int((_t.monotonic() - t0) * 1000)
        if r.status_code != 200:
            self._record("POST", "/v2/commands/submit-and-wait-for-transaction",
                         body, r.status_code, r.text, ms)
            raise RuntimeError(f"submit failed [{r.status_code}]: {r.text[:300]}")
        tx = r.json()["transaction"]
        created = []
        for ev in tx.get("events", []):
            ce = ev.get("CreatedEvent")
            if ce:
                created.append({"entity": ce["templateId"].rsplit(":", 1)[1],
                                "cid": ce["contractId"],
                                "arg": ce.get("createArgument", {})})
        self._record("POST", "/v2/commands/submit-and-wait-for-transaction",
                     body, 200,
                     {"updateId": tx["updateId"], "offset": tx.get("offset"),
                      "recordTime": tx.get("recordTime"),
                      "created": [c["entity"] for c in created]}, ms)
        return {"updateId": tx["updateId"], "created": created}

    def create(self, act_as: str, entity: str, args: dict, module: str = "BasisVault.Vault") -> dict:
        return self.submit([act_as], [{"CreateCommand": {
            "templateId": _tpl(entity, module), "createArguments": args}}])

    def exercise(self, act_as: str | list[str], entity: str, cid: str, choice: str,
                 arg: dict | None = None, module: str = "BasisVault.Vault") -> dict:
        acts = [act_as] if isinstance(act_as, str) else act_as
        return self.submit(acts, [{"ExerciseCommand": {
            "templateId": _tpl(entity, module), "contractId": cid,
            "choice": choice, "choiceArgument": arg or {}}}])

    def upload_dar(self, path: str) -> None:
        """Upload the app DAR to the participant (idempotent — re-uploading the
        same package is a no-op). Needed once per fresh participant/testnet."""
        with open(path, "rb") as f:
            r = self._http.post("/v2/packages", content=f.read(),
                                headers={"Content-Type": "application/octet-stream"})
        r.raise_for_status()

    # ---------- lifecycle helpers ----------
    def create_vault(self) -> dict:
        args = {
            "operator": self.party["operator"], "manager": self.party["manager"],
            "auditor": self.party["auditor"],
            "underlying": {"tag": "CBTC", "value": {}},
            "totalAssets": "0.0", "totalShares": "0.0"}
        # v0.2.0 templates bind everything to a stable vault id (judge-feedback
        # fix). The shared DevNet node still runs the judged v0.1.0 package
        # (no such field), so the id is only sent when the target participant
        # has v0.2.0+:  LEDGER_VAULT_ID=basisyield-main
        vid = os.environ.get("LEDGER_VAULT_ID", "")
        if vid:
            args["vaultId"] = vid
        return self.create("operator", "Vault", args)

    def reset(self) -> None:
        """Archive every basisvault contract, then re-create a fresh Vault."""
        if not self.ensure():
            return
        for sweep in range(3):  # proposals may reference now-gone holdings; sweep
            leftovers = 0
            for hint in ("operator", "manager", "oracle", "alice", "bob"):
                for c in self.acs(hint):
                    who = _ARCHIVE_AS.get(c["entity"])
                    try:
                        if c["entity"] in ("DepositRequest", "RedeemRequest"):
                            inv = c["arg"].get("investor", "")
                            who = next((h for h, p in self.party.items() if p == inv), None)
                        elif c["entity"] == "TransferProposal":
                            frm = c["arg"].get("from", "")
                            who = next((h for h, p in self.party.items() if p == frm), None)
                        elif c["entity"] == "AcceptedTransfer":
                            frm = c["arg"].get("from", ""); to = c["arg"].get("to", "")
                            pair = [h for h, p in self.party.items() if p in (frm, to)]
                            if len(pair) == 2:
                                self.exercise(pair, c["entity"], c["cid"], "Archive",
                                              module=c["template"].rsplit(":", 1)[0])
                            continue
                        if who and who == hint:
                            module = c["template"].rsplit(":", 1)[0]
                            self.exercise(who, c["entity"], c["cid"], "Archive", module=module)
                        elif who is None:
                            leftovers += 1
                    except Exception as e:
                        log.warning("reset archive %s failed: %s", c["entity"], e)
                        leftovers += 1
            if leftovers == 0:
                break
        self.create_vault()
        # collapse any duplicate vaults (e.g. from a concurrent reset race)
        keep = self.vault_cid()
        for v in self.find("operator", "Vault"):
            if v["cid"] != keep:
                try:
                    self.exercise("operator", "Vault", v["cid"], "Archive")
                except Exception as e:
                    log.warning("duplicate vault archive failed: %s", e)
