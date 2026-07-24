#!/usr/bin/env bash
# Store DevNet (NODERS shared node) credentials for the BasisYield dashboard.
#
# Run this YOURSELF over SSH (it prompts interactively — your password is never
# echoed, never stored; only the OIDC *offline/refresh token* is kept):
#
#   DEVNET_TOKEN_URL=... DEVNET_CLIENT_ID=... DEVNET_JSON_API=... \
#     bash /root/basisvault/scripts/devnet_credentials.sh
#
# Endpoint values come from the hackathon Materials page ("DevNet node
# materials") — intentionally NOT hardcoded in this public repo.
# Writes /root/basisvault/.env.devnet (chmod 600, gitignored).
set -euo pipefail

TOKEN_URL="${DEVNET_TOKEN_URL:?set DEVNET_TOKEN_URL (Materials page: OIDC URL)}"
CLIENT_ID="${DEVNET_CLIENT_ID:?set DEVNET_CLIENT_ID (Materials page: client_id)}"
SCOPE="${DEVNET_SCOPE:-openid daml_ledger_api offline_access}"
JSON_API="${DEVNET_JSON_API:?set DEVNET_JSON_API (Materials page: JSON Ledger API)}"

read -r -p "AppsFactory email: " AF_USER
read -r -s -p "AppsFactory password (input hidden): " AF_PASS; echo

export TOKEN_URL CLIENT_ID SCOPE JSON_API AF_USER AF_PASS
python3 - <<'EOF'
import base64, json, os, sys, urllib.parse, urllib.request

token_url = os.environ["TOKEN_URL"]
form = urllib.parse.urlencode({
    "grant_type": "password",
    "client_id": os.environ["CLIENT_ID"],
    "username": os.environ["AF_USER"],
    "password": os.environ["AF_PASS"],
    "scope": os.environ["SCOPE"],
}).encode()

req = urllib.request.Request(token_url, data=form, headers={
    "Content-Type": "application/x-www-form-urlencoded"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.load(r)
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")
    sys.exit(f"!! Keycloak refused the request (HTTP {e.code}):\n   {body[:400]}\n"
             "   (invalid_grant usually means wrong email/password; "
             "invalid_scope means drop DEVNET_SCOPE and retry)")

access = tok.get("access_token", "")
refresh = tok.get("refresh_token", "")
if not access or not refresh:
    sys.exit(f"!! unexpected token response: {json.dumps(tok)[:400]}")

def jwt_claims(t):
    try:
        p = t.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception:
        return {}

claims = jwt_claims(access)
sub = claims.get("sub", "")
print(f"→ token OK. expires_in={tok.get('expires_in')}s  "
      f"refresh_expires_in={tok.get('refresh_expires_in')}s  sub={sub or '<undecoded>'}")

# probe the JSON Ledger API with the fresh token
probe = urllib.request.Request(
    os.environ["JSON_API"].rstrip("/") + "/v2/state/ledger-end",
    headers={"Authorization": f"Bearer {access}"})
try:
    with urllib.request.urlopen(probe, timeout=30) as r:
        print(f"→ JSON Ledger API probe: HTTP {r.status} {r.read(200).decode(errors='replace')}")
except urllib.error.HTTPError as e:
    print(f"→ JSON Ledger API probe: HTTP {e.code} {e.read(200).decode(errors='replace')}")

env_file = "/root/basisvault/.env.devnet"
os.umask(0o077)
with open(env_file, "w") as f:
    f.write(f"""LEDGER_API_BASE={os.environ['JSON_API']}
LEDGER_OIDC_TOKEN_URL={token_url}
LEDGER_OIDC_CLIENT_ID={os.environ['CLIENT_ID']}
LEDGER_OIDC_SCOPE="{os.environ['SCOPE']}"
LEDGER_OIDC_REFRESH_TOKEN={refresh}
LEDGER_USER_ID={sub}
LEDGER_LABEL="Canton DevNet · NODERS hackcanton-01 · JSON Ledger API v2"
""")
print(f"→ wrote {env_file} (mode 600).")
print("""
Wire it into the dashboard with:
  systemctl edit basisvault-dashboard   # add under [Service]:
      EnvironmentFile=/root/basisvault/.env.devnet
  systemctl restart basisvault-dashboard
Revert to sandbox anytime:
  systemctl revert basisvault-dashboard && systemctl restart basisvault-dashboard
""")
EOF
unset AF_PASS
