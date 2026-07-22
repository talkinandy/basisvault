"""Fetch REAL Hyperliquid perp funding history for the short leg of the carry.

The BasisYield-on-Canton mechanism shorts BTC/ETH perps on Hyperliquid while
holding cBTC/cETH long on Canton — so the honest dataset for the funding leg is
Hyperliquid's own funding prints (not a Binance proxy). Intervals are variable
(8h early history, hourly later); each row carries its own timestamp so the
backtest annualizes by actual elapsed time.

Source: POST https://api.hyperliquid.xyz/info {"type": "fundingHistory", ...}
Writes engine/data/hl_btc_funding.json + hl_eth_funding.json (committed).

Run:  python scripts/fetch_hl_funding.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

URL = "https://api.hyperliquid.xyz/info"
DATA = Path(__file__).resolve().parent.parent / "data"
COINS = {
    "BTC": "hl_btc_funding.json",
    "ETH": "hl_eth_funding.json",
    # next-phase gold pair: HIP-3 builder-dex perp (short) vs XAUT0 spot /
    # DBS gold token on Canton (long). History starts 2025-12-22.
    "xyz:GOLD": "hl_gold_funding.json",
}


def fetch(coin: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[int] = set()
    start = 0  # HL returns from listing (May 2023) when startTime predates it
    with httpx.Client(timeout=30.0) as c:
        while True:
            for attempt in range(6):
                r = c.post(URL, json={"type": "fundingHistory", "coin": coin,
                                      "startTime": start})
                if r.status_code != 429:
                    break
                time.sleep(5.0 * (attempt + 1))  # HL rate limit — back off
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for b in batch:
                t = int(b["time"])
                if t in seen:
                    continue
                seen.add(t)
                rows.append({"time": t, "fundingRate": float(b["fundingRate"])})
            last = max(int(b["time"]) for b in batch)
            if last <= start:
                break
            start = last + 1
            time.sleep(0.25)  # be polite
    rows.sort(key=lambda x: x["time"])
    return rows


def main() -> None:
    import sys
    only = set(a.upper() for a in sys.argv[1:])  # e.g. `... fetch_hl_funding.py ETH`
    DATA.mkdir(parents=True, exist_ok=True)
    for coin, fname in COINS.items():
        if only and coin not in only:
            continue
        rows = fetch(coin)
        (DATA / fname).write_text(json.dumps(rows))
        days = (rows[-1]["time"] - rows[0]["time"]) / 86_400_000 if rows else 0
        print(f"{coin}: {len(rows)} funding points ({days:.0f} days) -> data/{fname}")


if __name__ == "__main__":
    main()
