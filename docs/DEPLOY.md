# Deploy — canton.basisyield.com

Live at **https://canton.basisyield.com** (karbonlens, 49.13.82.0). Additive to the
existing basisyield.com setup — separate port, own systemd unit + nginx vhost.

## Pieces
- **Canton sandbox (real ledger):** `/etc/systemd/system/basisvault-sandbox.service` —
  `daml sandbox --port 6865 --json-api-port 7575 --dar .daml/dist/basisvault-0.1.0.dar
  --wall-clock-time`. In-memory: a restart wipes the ledger; the web app's
  `LedgerBridge` re-bootstraps lazily (parties, `basisyield` API user with
  actAs/readAs rights, fresh Vault) on the next reset/step. The lifecycle demo
  then runs as REAL Daml transactions; if the sandbox is down the app falls back
  to its mock driver automatically.
- **systemd:** `/etc/systemd/system/basisvault-dashboard.service` — uvicorn serving
  `web.app:app` on `127.0.0.1:8411`, `WorkingDirectory=/root/basisvault`, from the
  engine venv `/root/basisvault/engine/.venv`. `Restart=always`.
- **nginx:** `/etc/nginx/sites-available/canton-basisyield` (symlinked into
  sites-enabled) → reverse proxy to `127.0.0.1:8411`. TLS by certbot.
- **TLS:** Let's Encrypt cert for `canton.basisyield.com` (certbot --nginx), auto-renew.
- **DNS:** `canton.basisyield.com A 49.13.82.0`.

## Operate
```bash
journalctl -u basisvault-dashboard -f          # logs
systemctl restart basisvault-dashboard          # after a code change
systemctl disable --now basisvault-dashboard    # stop + don't start on boot
```

## Redeploy after pushing changes
```bash
cd /root/basisvault && git pull
# if engine deps changed: engine/.venv/bin/pip install -e 'engine[dashboard]'
# refresh funding data + backtests: (cd engine && .venv/bin/python scripts/fetch_hl_funding.py && .venv/bin/python -m basisvault_engine.backtest)
# if the Daml model changed: daml build && systemctl restart basisvault-sandbox
systemctl restart basisvault-dashboard
```

## First-time setup (reproduce on a fresh host)
```bash
cd /root/basisvault/engine && python -m venv .venv
.venv/bin/pip install -e '.[dashboard,ledger]'
.venv/bin/python scripts/fetch_rates.py 3 && .venv/bin/python -m basisvault_engine.backtest
# install the systemd unit + nginx vhost (see files above), then:
systemctl daemon-reload && systemctl enable --now basisvault-dashboard
ln -s /etc/nginx/sites-available/canton-basisyield /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d canton.basisyield.com
```
