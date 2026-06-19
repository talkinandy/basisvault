"""Fetch BTC perpetual funding history (8h intervals) as a transparent PROXY for
CBTC funding — CBTC tracks BTC, and clean CBTC perp history isn't public yet.
Honest by labelling: the backtest validates the *strategy*, on real BTC funding.

Source: Binance USDT-M fundingRate (rate + mark price per interval).
Writes engine/data/btc_funding.json (committed for reproducibility).

Run:  python scripts/fetch_funding.py [years]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

SYMBOL = "BTCUSDT"
URL = "https://fapi.binance.com/fapi/v1/fundingRate"
OUT = Path(__file__).resolve().parent.parent / "data" / "btc_funding.json"


def fetch(years: float = 2.0) -> list[dict]:
    now_ms = int(time.time() * 1000)
    start = now_ms - int(years * 365 * 24 * 3600 * 1000)
    rows: list[dict] = []
    seen: set[int] = set()
    with httpx.Client(timeout=30.0) as c:
        while start < now_ms:
            r = c.get(URL, params={"symbol": SYMBOL, "startTime": start,
                                   "endTime": now_ms, "limit": 1000})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for b in batch:
                t = int(b["fundingTime"])
                if t in seen:
                    continue
                seen.add(t)
                rows.append({
                    "time": t,
                    "fundingRate": float(b["fundingRate"]),
                    "markPrice": float(b.get("markPrice") or 0.0),
                })
            last = max(int(b["fundingTime"]) for b in batch)
            if last <= start:
                break
            start = last + 1
            time.sleep(0.2)  # be polite
    rows.sort(key=lambda x: x["time"])
    return rows


def main() -> None:
    years = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    rows = fetch(years)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows))
    span_days = (rows[-1]["time"] - rows[0]["time"]) / 86_400_000 if rows else 0
    print(f"wrote {len(rows)} funding points "
          f"({span_days:.0f} days) -> {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
