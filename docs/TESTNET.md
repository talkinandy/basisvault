# Demo on a real Canton network — step-by-step

Goal: the lifecycle demo at canton.basisyield.com runs against a **real Canton
network participant** instead of the local sandbox. The app is already wired for
this — the ledger bridge targets any JSON Ledger API v2 via env vars; no code
changes are needed, only infrastructure + config.

**Reality check (researched 2026-07-21, deadline 2026-07-25):**

| Network | Onboarding | Feasible by Jul 25? |
|---|---|---|
| **TestNet** | GSF Tokenomics-Committee approval + sponsor SV + IP allowlist | ❌ committee process, no SLA |
| **DevNet** | self-service onboarding secret, **but egress-IP allowlist takes 2–7 days** | ⚠️ only with an organizer fast-path — ask TODAY |
| **Splice LocalNet** | none — the real Splice network stack (super-validator + scan + wallet) run locally | ✅ same software as DevNet, zero wait |

So: **run Track A (ask organizers) and Track C (LocalNet fallback) in parallel
today.** If the allowlist clears in time, Track B (DevNet validator) upgrades
the demo; if not, LocalNet is honestly presentable as "the real Splice network
stack, locally — DevNet onboarding in flight (requested <date>)".

Note the naming: what the hackathon calls "testnet" for demo purposes is, in
practice, **DevNet** (open to any node). Capital-T TestNet is a later milestone.

---

## Track A — today: ask the organizers (10 minutes)

The 2–7-day IP allowlist is the only hard blocker, and NODERS (host) runs an SV
("SV NodeOps"). Post in the hackathon Discord/Telegram:

> We'd like to demo on DevNet. Our MVP already executes its full lifecycle as
> real Daml transactions via the JSON Ledger API v2 against a local ledger —
> we only need a network participant. Can you either
> (a) fast-track the SV egress-IP allowlist for one IP so we can onboard a
> compose validator (party hint `basisyield-validator-1`), or
> (b) provide access to a hosted/sponsored participant with JSON Ledger API v2
> access (we need: base URL, auth audience/token flow, and rights to upload a
> DAR + allocate a handful of parties)?
> Our egress IP: `<IP of the VM below>`. SDK 3.4.11 DAR (LF 2.1); happy to
> rebuild with 3.5.x if required.

If they offer a hosted participant → skip to **step 5** (app wiring).

## Track B — DevNet validator (once the IP is allowlisted)

### 1. Get a VM

The validator is a docker-compose stack (participant + validator app +
postgres). Don't co-host it on karbonlens (7.6 GB RAM, mostly used). Rent a
fresh VPS: **4 vCPU / 16 GB / 100 GB** (e.g. Hetzner CPX41/CX42, ~€30/mo,
cancel after the final), Ubuntu 24.04, docker + compose ≥ 2.26. Its public IP
is the egress IP for the allowlist request in Track A.

### 2. Verify the allowlist cleared

From the VM (403 = not yet; JSON = you're in):

```bash
curl -fsS https://scan.sv-1.dev.global.canton.network.sync.global/api/scan/version
```

### 3. Onboard the validator

```bash
# self-service DevNet secret (valid 1 h, one-time) — from the sponsor SV app:
SV=https://sv.sv-1.dev.global.canton.network.sync.global
SECRET=$(curl -sfX POST "$SV/api/sv/v0/devnet/onboard/validator/prepare")

# release bundle (version = DevNet's Splice version, 0.6.13 at research time —
# check https://docs.canton.network/shared/version-compatibility-dashboard)
tar xzf 0.6.13_splice-node.tar.gz && cd splice-node/docker-compose/validator
export IMAGE_TAG=0.6.13
./start.sh -s "$SV" -o "$SECRET" -p basisyield-validator-1 -w
```

Notes:
- `-p` (party hint) is **immutable**, format `org-function-enum`.
- Default deployment binds one nginx to `127.0.0.1:80` with **auth disabled**
  (fine for a demo; do NOT add `-E` to expose it publicly — we reach it over an
  SSH tunnel). Restarts: `./stop.sh`, then `./start.sh` again with `-o ""`.
- Traffic/fees: on DevNet the validator **auto-taps CC** to buy synchronizer
  traffic — no funding needed. Wallet UI: `http://wallet.localhost` (user
  `administrator`) via the tunnel if you want to show CC balances.

### 4. Upload the DAR + smoke-test

Everything routes through nginx by virtual host, so requests need
`Host: json-ledger-api.localhost`:

```bash
# on the VM (or through the tunnel):
curl -sf -X POST http://127.0.0.1:80/v2/packages \
  -H "Host: json-ledger-api.localhost" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @basisvault-0.1.0.dar
curl -sf http://127.0.0.1:80/v2/parties -H "Host: json-ledger-api.localhost"
```

(Or from Python: `LedgerBridge().upload_dar(".daml/dist/basisvault-0.1.0.dar")`
once the env vars from step 5 are set.)

DAR compatibility: DevNet runs Canton 3.5.x; our SDK 3.4.11 DAR targets stable
LF 2.1 and should upload as-is. If `/v2/packages` rejects it, rebuild with the
SDK matching the dashboard (`daml.yaml: sdk-version: 3.5.9`) — no source
changes expected.

### 5. Point the dashboard at the participant

On **karbonlens**, tunnel to the VM and set the bridge env. The bridge
bootstraps everything else itself (parties, `basisyield` user + actAs/readAs
rights, Vault) exactly as it does on the sandbox — `LedgerBridge.ensure()` is
lazy and idempotent.

```bash
# persistent SSH tunnel: karbonlens:7580 -> VM's nginx :80
ssh -fN -L 7580:127.0.0.1:80 root@<VM_IP>     # or a systemd unit / autossh

# systemd override for the dashboard:
systemctl edit basisvault-dashboard
  [Service]
  Environment=LEDGER_API_BASE=http://127.0.0.1:7580
  Environment=LEDGER_API_HOST=json-ledger-api.localhost
  Environment=LEDGER_LABEL=Canton DevNet · basisyield-validator-1 · JSON Ledger API v2
systemctl restart basisvault-dashboard
```

The lifecycle panel's proof badge now reads **"⛓ live Canton ledger · Canton
DevNet"**, and every per-role contract count is the DevNet participant's own
ACS answer. To fall back to the sandbox: `systemctl revert basisvault-dashboard
&& systemctl restart basisvault-dashboard`.

Caveats vs the sandbox:
- **No reset-by-restart**: DevNet state persists; the panel's ↺ Reset uses the
  bridge's archive-sweep (`reset()`), which works but leaves history (fine —
  history is the point of a real network). DevNet itself resets every ~3 months.
- Party IDs carry the validator's namespace fingerprint — the UI already
  displays hints, not raw IDs.
- Each step consumes synchronizer traffic (auto-topped-up on DevNet).

### 6. Auth variant (only if the organizers hand us a secured participant)

If the provided participant requires JWTs: set `LEDGER_API_TOKEN=<jwt>` too.
For Splice-style HS256 dev auth the token is
`jwt.encode({"sub": "<user>", "aud": "<ledger-api-audience>"}, <secret>,
algorithm="HS256")`; for OIDC (`-a` mode) mint via the provided IdP
(client-credentials) with the `LEDGER_API_AUTH_AUDIENCE` they give us.

## Track C — fallback: Splice LocalNet on karbonlens (no wait)

The same release bundle ships `docker-compose/localnet`: a complete local
Canton network — super-validator, scan, wallet, participant — i.e. **the
identical software stack a DevNet validator runs**, minus the global
synchronizer. It is materially stronger than the bare sandbox (Splice stack,
wallet UI, CC, traffic accounting) and needs no approval.

```bash
tar xzf 0.6.13_splice-node.tar.gz && cd splice-node/docker-compose/localnet
export IMAGE_TAG=0.6.13
docker compose up -d          # see the bundle's README for the exact invocation
# then upload the DAR + wire the app exactly as steps 4–5 (same nginx virtual
# hosts; LEDGER_LABEL="Splice LocalNet · full network stack, local")
```

RAM on karbonlens is tight (7.6 GB total) — if LocalNet doesn't fit alongside
the existing services, run it on the Track-B VM instead (it's useful for
rehearsal even while waiting for the allowlist).

Demo framing if we end up here: *"This is the full Splice network stack — the
same software a DevNet validator runs. Our DevNet onboarding is in flight
(egress-IP allowlist requested <date>, 2–7 day SLA)."* Honest, and it shows the
integration is real.

## Demo-day checklist

- [ ] `curl -s https://canton.basisyield.com/api/lifecycle?role=observer` →
      `"live": true` with the DevNet/LocalNet label
- [ ] ↺ Reset, then click through all 6 steps once (warm run; catches traffic
      or auth hiccups before the recording)
- [ ] Role tabs: observer N contracts / holder own-only / outsider 0 —
      screenshot the badge with the participant label visible
- [ ] Keep the sandbox systemd unit running as instant fallback (revert = one
      `systemctl revert` away)
- [ ] Mention in the video: *"every transaction id you see is a real update on
      a Canton network participant"*

## Who to chase, in order

1. **NODERS NaaS** — the hackathon host runs Node-as-a-Service (see their
   "Canton Node + NaaS Workshop" video); a hosted validator skips the VM, the
   compose deployment AND the IP-allowlist wait. Ask what a team gets: JSON
   Ledger API access + DAR upload + party allocation is all we need
   (the official deploy guidance is explicitly "self-host **or NaaS**").
2. HackCanton Discord/Telegram — sponsor-SV fast-path or hosted participant
   (Track A message above).
3. **`#gsf-global-synchronizer-appdev`** on the Canton/GSF Slack — the
   canonical channel for DevNet app-dev asks; also the GSF lists at
   https://lists.sync.global/.
4. BitSafe — separately ask for **cBTC testnet access** (their docs ship a
   testnet guide + `cbtc-lib`); real testnet cBTC holdings are pilot step 1 and
   would be a strong flex if it lands early.

Current validator-compose docs (non-deprecated):
https://docs.canton.network/sdks-tools/development-tools/validator-operator/docker-compose-validator.html
