# Ubuzima backend

AI SRHR health-info navigator for Rwandan youth (FastAPI, async, Postgres + pgvector).

## Run
```
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in real values (see below)
docker compose up -d db         # Postgres+pgvector on host port 5434 (DBs: ubuzima, ubuzima_test)
alembic upgrade head            # create schema
python -m app.cli create_admin --email you@org.example   # prompts for password (min 12 chars)
uvicorn app.main:app --reload   # docs at /docs
```
Or the whole stack: `docker compose up --build` (the api container needs `alembic upgrade head`
run once: `docker compose exec api alembic upgrade head`).

### Environment (.env)
- `DATABASE_URL` (asyncpg URL), `POSTGRES_USER` / `POSTGRES_PASSWORD` (compose).
- `JWT_SECRET` (>= 32 chars), `ENCRYPTION_KEY` (base64 of exactly 32 random bytes; see `.env.example`).
- `OPENROUTER_API_KEY`, `LLM_MODEL`, `STT_MODEL`, `TTS_MODEL`, `OPENROUTER_BASE_URL`.
- Provider selectors: `LLM_PROVIDER` (openrouter|fake), `EMBEDDING_PROVIDER` (e5|fake),
  `STT_PROVIDER` / `TTS_PROVIDER` (openrouter|digitalumuganda|fake).
- Rate limits (per minute, `<=0` disables, `RATE_LIMIT_ENABLED=false` turns off):
  `RATE_LIMIT_AUTH_PER_MIN` (10, per IP: `/v1/identity/recover`, `/v1/admin/login`),
  `RATE_LIMIT_CHAT_PER_MIN` (30, per identity, one shared budget for chat + voice). In-process only, so limits are
  per worker, not shared; use a gateway/Redis limiter when scaling out.

### Behind a proxy / gateway (required for correct rate limiting)
The limiter keys on the client IP. Behind a gateway every request otherwise appears to come
from the proxy, making the 10/min auth budget global (one attacker could lock out all admin
logins/recoveries). Set `TRUSTED_PROXIES` (comma-separated IPs/CIDRs of your gateway; the app
then honours `X-Forwarded-For`, taking the right-most non-trusted hop) and run uvicorn with
`--proxy-headers --forwarded-allow-ips <gateway IPs>` (the Docker image does this via
`FORWARDED_ALLOW_IPS`, default 127.0.0.1). With `TRUSTED_PROXIES` empty (default) the header is
ignored, so clients cannot spoof their IP. Not behind a proxy: change nothing.

### First admin
There is no public admin signup. Create one with the CLI (no credentials are hard-coded):
`python -m app.cli create_admin --email you@org.example [--role reviewer]`. The password is
prompted (or `--password`, which lands in shell history). Duplicate emails exit 1.
Then `POST /v1/admin/login`.

### Behaviour notes
- Errors: `{"error": {"code", "message", "details"?}}` for every 4xx/5xx; validation details
  list only `loc` + `message` (inputs are never echoed). 500s are generic.
- `Accept-Language: en|rw` sets the reply language (answer + TTS) for chat/voice when the request
  does not specify `language`. It is never used as the STT language hint; STT auto-detects unless
  the explicit `language` form field is sent.
- Startup seeds placeholder referrals (idempotent; verified rows are never overwritten); if the
  DB is not migrated it logs a warning and continues.
- `WS /v1/live` is a RESERVED stub for future realtime voice; it only sends
  `{"error":"not_available"}` and closes (code 4501).
- Docker image installs CPU torch + sentence-transformers for e5 embeddings (large image, model
  downloaded on first use). For a light smoke run set `EMBEDDING_PROVIDER=fake` (not for real RAG).

## Test
```
TEST_DATABASE_URL=postgresql+asyncpg://postgres:<pw>@127.0.0.1:5434/ubuzima_test pytest -v
```
`-m "not integration"` is the default (pyproject addopts), so slow tests needing real
models/services are skipped, including the real multilingual-e5 test. Run it explicitly with
`pytest -m integration`.
Tests run only against a database whose name ends in `_test` (`TEST_DATABASE_URL`, falling back to `DATABASE_URL`); otherwise pytest aborts.

`docker/init-test-db.sql` (creates `ubuzima_test`) only runs on a fresh volume. If the volume already exists, create it manually:
```
docker compose exec db psql -U postgres -c "CREATE DATABASE ubuzima_test;"
```
Compose reads `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env`; no passwords are hard-coded.

## Realtime voice: TURN/STUN
WebRTC peers need ICE servers to connect across NATs. `app/realtime/turn.py` (`get_ice_servers`)
always returns the STUN server (`STUN_URL`) and, when `TURN_SECRET` is set, a TURN entry
(`TURN_URL`) with short-lived credentials (coturn `use-auth-secret`: username `<expiry>:<id>`,
credential = base64 HMAC-SHA1 over it, valid `TURN_TTL` seconds).

- `docker compose --profile realtime up coturn` runs a **dev-only** coturn sharing `TURN_SECRET` (must be set in `.env`; opt-in profile so db/api are unaffected). It is not hardened.
- Production needs a publicly reachable TURN server: set `--external-ip`, open 3478 (udp+tcp) and the relay port range in the firewall, and add TLS (`turns:` on 5349).
- Without `TURN_SECRET` only STUN is offered; clients behind symmetric NATs or strict firewalls will often fail to connect.
