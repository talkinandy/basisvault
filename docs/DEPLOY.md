# Deploy — canton.basisyield.com

Live at **https://canton.basisyield.com** (karbonlens, 49.13.82.0). Additive to the
existing basisyield.com setup — separate port, own systemd unit + nginx vhost.

## Pieces
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
# if backtest data changed: (cd engine && .venv/bin/python -m basisvault_engine.backtest)
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
