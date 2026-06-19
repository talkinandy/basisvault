"""Ledger access for the engine.

`LedgerClient` is the seam (mirrors the on-chain mock-adapter seam):
  - `MockLedgerClient` — in-memory sample state; runs with ZERO creds for
    demo / dry-run / CI.
  - `JsonLedgerClient` — real Canton JSON Ledger API (HTTP/JSON). Needs an
    endpoint, a bearer token (JWT), and the allocated party ids. Wired but
    unverified until testnet access lands — see DEV_NOTES.md open blockers.

The engine only ever calls this interface, so swapping mock -> real is a
one-line change in config.
"""
from __future__ import annotations

import json
from typing import Protocol

from .models import (
    Action,
    Decision,
    PositionState,
    RebalancePlan,
    Underlying,
    VaultState,
)


class LedgerClient(Protocol):
    def get_vault(self) -> VaultState: ...
    def get_position(self) -> PositionState | None: ...
    def propose_rebalance(self, plan: RebalancePlan) -> str: ...
    def unwind(self, position_cid: str) -> None: ...


# --------------------------------------------------------------------------- #
# Mock — runs with no creds. Lets the whole engine + dashboard demo end-to-end.
# --------------------------------------------------------------------------- #
class MockLedgerClient:
    def __init__(
        self,
        vault: VaultState | None = None,
        position: PositionState | None = None,
    ) -> None:
        self._vault = vault or VaultState(
            contract_id="mock-vault-1",
            underlying=Underlying.CBTC,
            total_assets=1_000_000.0,
            total_shares=1_000_000.0,
        )
        self._position = position
        self.actions: list[tuple[Action, object]] = []  # audit trail for the demo

    def get_vault(self) -> VaultState:
        return self._vault

    def get_position(self) -> PositionState | None:
        return self._position

    def propose_rebalance(self, plan: RebalancePlan) -> str:
        self.actions.append((Action.PROPOSE, plan))
        # Simulate the operator approving + both legs filling equal-notional.
        self._position = PositionState(
            contract_id="mock-pos-1",
            underlying=plan.underlying,
            short_notional=plan.notional,
            long_notional=plan.notional,
            mark_price=0.0,
        )
        return self._position.contract_id

    def unwind(self, position_cid: str) -> None:
        self.actions.append((Action.UNWIND, position_cid))
        self._position = None


# --------------------------------------------------------------------------- #
# Real — Canton JSON Ledger API. Unverified until testnet access.
# --------------------------------------------------------------------------- #
PKG = "basisvault"  # package name; the real package-id is filled in from the .dar


class JsonLedgerClient:
    """Thin client over the Canton JSON Ledger API.

    Endpoints follow the v2 JSON Ledger API shape (POST /v2/commands/submit-and-wait,
    POST /v2/state/active-contracts). Confirm exact paths/payloads against the
    target node's docs at integration:
    https://docs.canton.network/appdev/modules/m4-json-api-tutorial.md
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        operator_party: str,
        manager_party: str,
        vault_template_id: str,
    ) -> None:
        try:
            import httpx  # imported lazily so the mock path needs no deps
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "JsonLedgerClient needs httpx: pip install 'basisvault-engine[ledger]'"
            ) from e
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        self._operator = operator_party
        self._manager = manager_party
        self._vault_tid = vault_template_id

    def get_vault(self) -> VaultState:  # pragma: no cover - needs live ledger
        contracts = self._active_contracts(self._vault_tid, self._manager)
        if not contracts:
            raise LookupError("no Vault contract visible to the manager party")
        c = contracts[0]
        payload = c["createArgument"]
        return VaultState(
            contract_id=c["contractId"],
            underlying=Underlying(payload["underlying"]),
            total_assets=float(payload["totalAssets"]),
            total_shares=float(payload["totalShares"]),
        )

    def get_position(self) -> PositionState | None:  # pragma: no cover
        tid = self._vault_tid.rsplit(":", 1)[0] + ":DeltaNeutralPosition"
        contracts = self._active_contracts(tid, self._manager)
        if not contracts:
            return None
        c = contracts[0]
        p = c["createArgument"]
        return PositionState(
            contract_id=c["contractId"],
            underlying=Underlying(p["underlying"]),
            short_notional=float(p["shortNotional"]),
            long_notional=float(p["longNotional"]),
            mark_price=float(p["markPrice"]),
        )

    def propose_rebalance(self, plan: RebalancePlan) -> str:  # pragma: no cover
        vault = self.get_vault()
        body = {
            "actAs": [self._manager],
            "commands": [{
                "ExerciseCommand": {
                    "templateId": self._vault_tid,
                    "contractId": vault.contract_id,
                    "choice": "Vault_ProposeRebalance",
                    "choiceArgument": {"plan": {
                        "underlying": plan.underlying.value,
                        "shortVenue": plan.short_venue.value,
                        "longVenue": plan.long_venue.value,
                        "notional": str(plan.notional),
                    }},
                }
            }],
        }
        res = self._submit(body)
        return json.dumps(res)  # caller logs; operator approves on-chain

    def unwind(self, position_cid: str) -> None:  # pragma: no cover
        tid = self._vault_tid.rsplit(":", 1)[0] + ":DeltaNeutralPosition"
        body = {
            "actAs": [self._operator],
            "commands": [{
                "ExerciseCommand": {
                    "templateId": tid,
                    "contractId": position_cid,
                    "choice": "DeltaNeutralPosition_Unwind",
                    "choiceArgument": {},
                }
            }],
        }
        self._submit(body)

    # --- low-level ---
    def _active_contracts(self, template_id: str, party: str) -> list[dict]:  # pragma: no cover
        body = {
            "filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"TemplateFilter": {
                    "templateId": template_id}}}]}}},
            "verbose": False,
            "activeAtOffset": 0,
        }
        res = self._http.post("/v2/state/active-contracts", json=body)
        res.raise_for_status()
        return [r["contractEntry"]["JsActiveContract"] for r in res.json()]

    def _submit(self, body: dict) -> dict:  # pragma: no cover
        res = self._http.post("/v2/commands/submit-and-wait", json=body)
        res.raise_for_status()
        return res.json()
