"""Run the full BasisVault lifecycle on a Canton participant — single-party mode.

Plan B for restricted shared nodes (e.g. the HackCanton DevNet node): when the
token can act as ONE party only, every role (operator/manager/auditor/oracle/
investors) is played by that party. The workflow, the Daml choices and the
transaction ids are real; only the multi-party privacy demo is out of scope
(that stays on the multi-party deployment).

Usage:
  set -a && . /root/basisvault/.env.devnet && set +a       # or sandbox: no env
  engine/.venv/bin/python scripts/devnet_lifecycle.py

Prints every step's update id. Requires the basisvault DAR on the participant.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web"))
from ledger_bridge import HINTS, LedgerBridge  # noqa: E402

NOTIONAL = "400000.0"
DEPOSIT = "1000000.0"


def main() -> None:
    br = LedgerBridge()
    # single-party override: our user's primary party plays every role
    me = br._http.get(f"/v2/users/{__import__('ledger_bridge').USER}")
    me.raise_for_status()
    party = me.json()["user"].get("primaryParty") or ""
    if not party:
        # sandbox fallback: bootstrap normally and use the operator party
        assert br.ensure(), "no primary party and no bootstrap — is the ledger up?"
        party = br.party["operator"]
    br.party = {h: party for h in HINTS}
    br._ready = True
    print(f"party (all roles): {party[:40]}…")

    txs: list[tuple[str, str]] = []

    def rec(step: str, r: dict) -> dict:
        txs.append((step, r["updateId"]))
        print(f"  {step:<28} tx {r['updateId']}")
        return r

    # our vault = the one where THIS party plays every role (a coexisting
    # multi-party vault, e.g. on the sandbox, is not ours to drive)
    def my_vault_cid() -> str:
        for v in br.find("operator", "Vault"):
            if v["arg"]["operator"] == party and v["arg"]["manager"] == party:
                return v["cid"]
        return ""

    if not my_vault_cid():
        rec("create Vault", br.create_vault())
    br.vault_cid = my_vault_cid          # override lookups for the run
    br.vault = lambda: next(v for v in br.find("operator", "Vault")
                            if v["cid"] == my_vault_cid())

    # 1 deposit
    r = br.create("alice", "DepositRequest", {
        "operator": party, "investor": party,
        "amount": DEPOSIT, "vaultCid": br.vault_cid()})
    dep = next(c for c in r["created"] if c["entity"] == "DepositRequest")
    rec("deposit propose", r)
    rec("deposit accept (mint)", br.exercise(
        "operator", "DepositRequest", dep["cid"], "DepositRequest_Accept"))

    # 2 open carry: oracle feeds + propose + approve, per asset
    for u, perp, mark in (("CBTC", "BTC", "65000.0"), ("CETH", "ETH", "3200.0")):
        br.create("oracle", "PriceFeed", {
            "oracle": party, "operator": party,
            "underlying": {"tag": u, "value": {}}, "price": mark},
            module="BasisVault.Venue")
        br.create("oracle", "RateFeed", {
            "oracle": party, "operator": party, "kind": "Basis",
            "asset": f"{perp}-PERP-HL", "annualizedRate": "0.08"},
            module="BasisVault.YieldSource")
        rp = br.exercise("manager", "Vault", br.vault_cid(), "Vault_ProposeRebalance",
                         {"plan": {"underlying": {"tag": u, "value": {}},
                                   "shortVenue": "Hyperliquid", "longVenue": "Cantex",
                                   "notional": NOTIONAL,
                                   "collateralAsset": "USDCx", "collateralRate": "0.0"}})
        prop = next(c for c in rp["created"] if c["entity"] == "RebalanceProposal")
        feed = next(f for f in br.find("oracle", "PriceFeed")
                    if f["arg"]["underlying"]["tag"] == u and f["arg"]["oracle"] == party)
        rec(f"open carry {u}", br.exercise(
            "operator", "RebalanceProposal", prop["cid"],
            "RebalanceProposal_Approve", {"priceFeedCid": feed["cid"]}))

    # 3 accrue a quarter of funding on both positions
    for pos in br.find("operator", "DeltaNeutralPosition"):
        if pos["arg"]["manager"] != party:
            continue
        u = pos["arg"]["underlying"]["tag"]
        feed = next(f for f in br.find("oracle", "RateFeed")
                    if f["arg"]["kind"] == "Basis" and f["arg"]["oracle"] == party)
        rec(f"accrue funding {u}", br.exercise(
            "operator", "Vault", br.vault_cid(), "Vault_AccrueFunding",
            {"positionCid": pos["cid"], "rateFeedCid": feed["cid"],
             "yearFraction": "0.25"}))

    # 4 transfer (self-transfer in single-party mode — flow still real)
    hold = next(h for h in br.find("alice", "ShareHolding")
                if h["arg"]["investor"] == party)
    rp = br.exercise("alice", "ShareHolding", hold["cid"],
                     "ShareHolding_ProposeTransfer", {"newHolder": party})
    prop = next(c for c in rp["created"] if c["entity"] == "TransferProposal")
    ra = br.exercise("bob", "TransferProposal", prop["cid"], "TransferProposal_Accept")
    acc = next(c for c in ra["created"] if c["entity"] == "AcceptedTransfer")
    rec("transfer settle", br.exercise(
        "operator", "AcceptedTransfer", acc["cid"], "AcceptedTransfer_Settle"))

    # 5 unwind both pairs
    for pos in [p_ for p_ in br.find("operator", "DeltaNeutralPosition")
                if p_["arg"]["manager"] == party]:
        rec(f"unwind {pos['arg']['underlying']['tag']}", br.exercise(
            "operator", "Vault", br.vault_cid(), "Vault_UnwindPosition",
            {"positionCid": pos["cid"]}))

    # 6 redeem
    hold = next(h for h in br.find("bob", "ShareHolding")
                if h["arg"]["investor"] == party)
    rr = br.exercise("bob", "ShareHolding", hold["cid"], "ShareHolding_RequestRedeem")
    req = next(c for c in rr["created"] if c["entity"] == "RedeemRequest")
    rec("redeem (burn)", br.exercise(
        "operator", "RedeemRequest", req["cid"], "RedeemRequest_Accept",
        {"vaultCid": br.vault_cid()}))

    v = br.vault()
    print(f"\nfinal vault: totalAssets={v['arg']['totalAssets']} "
          f"totalShares={v['arg']['totalShares']}")
    print(f"{len(txs)} steps, all real ledger transactions.")


if __name__ == "__main__":
    main()
