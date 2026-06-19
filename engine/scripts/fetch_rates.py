"""Fetch real RWA yield-source rates from FRED (no API key needed) as proxies:
  - SOFR    -> tokenized-Treasury REPO carry
  - DGS3MO  -> 3-month T-bill, proxy for tokenized MMF base yield

These are the honest, public stand-ins for Canton's tokenized-RWA yields until
those assets carry their own on-chain rate feeds. Writes data/rwa_rates.json
(date_ms, repo_rate, mmf_rate as annualized fractions), merged on common dates.

Run:  python scripts/fetch_rates.py [years]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv"
OUT = Path(__file__).resolve().parent.parent / "data" / "rwa_rates.json"


def _series(series_id: str) -> dict[int, float]:
    r = httpx.get(FRED, params={"id": series_id}, timeout=30.0)
    r.raise_for_status()
    out: dict[int, float] = {}
    for line in r.text.splitlines()[1:]:
        date_s, _, val_s = line.partition(",")
        if not val_s or val_s == ".":
            continue
        dt = datetime.strptime(date_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        out[int(dt.timestamp() * 1000)] = float(val_s) / 100.0  # percent -> fraction
    return out


def main() -> None:
    years = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    cutoff = int((time.time() - years * 365 * 86400) * 1000)
    repo = _series("SOFR")
    mmf = _series("DGS3MO")
    common = sorted(t for t in (set(repo) & set(mmf)) if t >= cutoff)
    rows = [{"time": t, "repo_rate": repo[t], "mmf_rate": mmf[t]} for t in common]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows))
    span = (rows[-1]["time"] - rows[0]["time"]) / 86_400_000 if rows else 0
    print(f"wrote {len(rows)} daily rate points ({span:.0f} days) -> "
          f"{OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
