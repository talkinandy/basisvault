"""Environment-driven config. Secrets (token, party ids, endpoint) come from the
env / .env and are NEVER committed — see the repo .gitignore.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    # "mock" runs with no creds; "json" hits the real Canton JSON Ledger API.
    mode: str = "mock"
    dry_run: bool = True  # log decisions, don't submit (safe default)

    # Real-ledger settings (only needed when mode == "json").
    ledger_base_url: str = ""
    ledger_token: str = ""
    operator_party: str = ""
    manager_party: str = ""
    vault_template_id: str = ""  # e.g. "<pkg-id>:BasisVault.Vault:Vault"

    @staticmethod
    def from_env() -> "EngineConfig":
        return EngineConfig(
            mode=os.getenv("BV_MODE", "mock"),
            dry_run=os.getenv("BV_DRY_RUN", "true").lower() != "false",
            ledger_base_url=os.getenv("BV_LEDGER_URL", ""),
            ledger_token=os.getenv("BV_LEDGER_TOKEN", ""),
            operator_party=os.getenv("BV_OPERATOR_PARTY", ""),
            manager_party=os.getenv("BV_MANAGER_PARTY", ""),
            vault_template_id=os.getenv("BV_VAULT_TID", ""),
        )
