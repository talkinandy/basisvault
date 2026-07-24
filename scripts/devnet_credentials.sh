#!/usr/bin/env bash
# Store DevNet (NODERS shared node) credentials for the BasisYield dashboard.
#
# Run this YOURSELF over SSH (it prompts interactively — your password is never
# echoed, never stored; only the OIDC *offline/refresh token* is kept):
#
#   bash /root/basisvault/scripts/devnet_credentials.sh
#
# Writes /root/basisvault/.env.devnet (chmod 600, gitignored) and prints the
# systemd wiring instructions.
set -euo pipefail

TOKEN_URL="https://keycloak.naas.noders.services/realms/noders-appsfactory/protocol/openid-connect/token"
CLIENT_ID="web-app-ui-hackcanton-01-devnet"
SCOPE="openid daml_ledger_api offline_access"
JSON_API="https://ledger-api-json.participant.hackcanton-01.devnet.naas.noders.services:443"
ENV_FILE="/root/basisvault/.env.devnet"

read -r -p "AppsFactory email: " AF_USER
read -r -s -p "AppsFactory password (input hidden): " AF_PASS; echo

echo "→ requesting tokens from Keycloak..."
RESP=$(curl -sS "$TOKEN_URL" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "username=$AF_USER" \
  --data-urlencode "password=$AF_PASS" \
  --data-urlencode "scope=$SCOPE")
unset AF_PASS

ACCESS=$(echo "$RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("access_token",""))')
REFRESH=$(echo "$RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("refresh_token",""))')
if [ -z "$REFRESH" ]; then
  echo "!! no refresh token in response:"; echo "$RESP" | head -c 400; exit 1
fi

# ledger user id = the JWT's sub claim
SUB=$(echo "$ACCESS" | cut -d. -f2 | python3 -c 'import base64,json,sys;p=sys.stdin.read();p+="="*(-len(p)%4);print(json.loads(base64.urlsafe_b64decode(p)).get("sub",""))')
echo "→ token OK. ledger user id (sub): $SUB"

echo -n "→ probing JSON Ledger API with the token... "
CODE=$(curl -s -o /tmp/devnet-probe.json -w "%{http_code}" -H "Authorization: Bearer $ACCESS" "$JSON_API/v2/state/ledger-end")
echo "HTTP $CODE $(head -c 120 /tmp/devnet-probe.json)"

umask 077
cat > "$ENV_FILE" <<ENV
LEDGER_API_BASE=$JSON_API
LEDGER_OIDC_TOKEN_URL=$TOKEN_URL
LEDGER_OIDC_CLIENT_ID=$CLIENT_ID
LEDGER_OIDC_SCOPE=$SCOPE
LEDGER_OIDC_REFRESH_TOKEN=$REFRESH
LEDGER_USER_ID=$SUB
LEDGER_LABEL=Canton DevNet · NODERS hackcanton-01 · JSON Ledger API v2
ENV
echo "→ wrote $ENV_FILE (mode 600)."
echo
echo "Wire it into the dashboard with:"
echo "  systemctl edit basisvault-dashboard   # add under [Service]:"
echo "      EnvironmentFile=/root/basisvault/.env.devnet"
echo "  systemctl restart basisvault-dashboard"
echo "Revert to sandbox anytime:  systemctl revert basisvault-dashboard && systemctl restart basisvault-dashboard"
