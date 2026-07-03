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
import uuid
from typing import Any

import httpx

log = logging.getLogger("basisvault.ledger")

PKG = "#basisvault"
HINTS = ("operator", "manager", "auditor", "oracle", "alice", "bob", "mallory")
USER = "basisyield"

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
    def __init__(self, base: str = "http://127.0.0.1:7575") -> None:
        self._http = httpx.Client(base_url=base, timeout=25.0)
        self.party: dict[str, str] = {}
        self._ready = False

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
        existing = {p["party"].split("::")[0]: p["party"] for p in self._parties()}
        for h in HINTS:
            if h not in existing:
                r = self._http.post("/v2/parties", json={
                    "partyIdHint": h, "identityProviderId": ""})
                r.raise_for_status()
                existing[h] = r.json()["partyDetails"]["party"]
        self.party = {h: existing[h] for h in HINTS}

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

    def vault_cid(self) -> str | None:
        vs = self.find("operator", "Vault")
        return vs[0]["cid"] if vs else None

    def vault(self) -> dict | None:
        vs = self.find("operator", "Vault")
        return vs[0] if vs else None

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
        r = self._http.post("/v2/commands/submit-and-wait-for-transaction", json=body)
        if r.status_code != 200:
            raise RuntimeError(f"submit failed [{r.status_code}]: {r.text[:300]}")
        tx = r.json()["transaction"]
        created = []
        for ev in tx.get("events", []):
            ce = ev.get("CreatedEvent")
            if ce:
                created.append({"entity": ce["templateId"].rsplit(":", 1)[1],
                                "cid": ce["contractId"],
                                "arg": ce.get("createArgument", {})})
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

    # ---------- lifecycle helpers ----------
    def create_vault(self) -> dict:
        return self.create("operator", "Vault", {
            "operator": self.party["operator"], "manager": self.party["manager"],
            "auditor": self.party["auditor"],
            "underlying": {"tag": "CBTC", "value": {}},
            "totalAssets": "0.0", "totalShares": "0.0"})

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
