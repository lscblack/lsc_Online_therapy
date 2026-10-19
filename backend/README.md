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
There is no public admin signup. Two options (no credentials are hard-coded in the image):
- **Startup bootstrap:** set `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` in `.env`; the API
  creates that admin once on startup if it does not already exist (idempotent, non-blocking).
- **CLI:** `python -m app.cli create_admin --email you@org.example [--role reviewer]`. The password
  is prompted (or `--password`, which lands in shell history; min 12 chars). Duplicate emails exit 1.

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

## Live voice (realtime)
**Architecture.** WebRTC, server-terminated (aiortc): the client sends mic audio over a peer
connection; the server runs VAD, streaming STT (Deepgram for English; VAD-segmented utterances
for Kinyarwanda), then the normal `ChatService` pipeline, and streams TTS back on an outbound
audio track. Safety is **guard-before-audio**: crisis/safety checks run on the transcript before
any synthesized audio is released. Barge-in cancels agent speech (crisis answers play a minimum
duration first). Layering is additive; the text/voice REST API is unchanged.

**Client flow.**
1. `POST /v1/live/offer` (Bearer JWT) `{sdp, type:"offer", language, voice?}` -> `{session_id, sdp (answer), ice_servers, ws_ticket}`. 401 unauthenticated, 429 over the per-user cap, 503 if the realtime extra is not installed.
2. Trickle ICE: `POST /v1/live/ice` `{session_id, candidate}` (or via the WS).
3. Open `WS /v1/live?session_id=...&ticket=<ws_ticket>` (ticket is single-use, ~60s). Server events: `state`, `transcript_partial/final`, `answer`, `citations`, `safety_flags`, `barge_in`, `error`. Client messages: `{"type":"barge_in"}`, `{"type":"end"}`, `{"type":"ice", candidate}`. Close codes: 4401 unauthorized, 4404 unknown session, 4409 already attached.

**Settings (env).** `REALTIME_MAX_SESSIONS_PER_USER` (2), `REALTIME_MAX_SESSION_SECONDS` (900),
`REALTIME_IDLE_SECONDS` (120), `REALTIME_WS_ATTACH_GRACE_SECONDS` (30, time allowed between
`/offer` and the WS attaching), `REALTIME_REAPER_INTERVAL_SECONDS` (5), plus `STUN_URL`,
`TURN_URL`, `TURN_SECRET`, `TURN_TTL` (see above) and `STREAMING_STT_PROVIDER`
(`auto|deepgram|vad|fake`). A background reaper (started in the app lifespan) closes sessions
that are idle, over max duration, or never attached a WS; on shutdown all sessions are closed.

**Install the realtime extra.** The heavy deps (aiortc, av, silero-vad/torch, webrtcvad) are
optional: `pip install '.[realtime]'`. Without them the app boots normally and non-realtime
routes work; `POST /v1/live/offer` returns 503 "Realtime voice unavailable".

**Not covered by the default tests.** Unit tests use fakes. Real aiortc handshakes, coturn, the
multilingual-e5 model, and Deepgram are integration/production concerns (`pytest -m integration`).
Go-live gates still deferred: a real aiortc offer/answer smoke on the target host, a public TURN
with TLS, and load testing of concurrent sessions (the registry and reaper are per-process, so
run a single worker or add sticky routing).

## Jev (TypeSafe System One) — structured decisions in the RAG pipeline

[Jev](https://docs.typesafe.ai) is a "System One" model: instead of free-form text it returns
typed, schema-valid answers with **calibrated probabilities/confidence** (and, by design, no
hallucination or type errors). We use it as an *additive* safety signal in two places, and it
**fails soft** everywhere — no key / SDK error / timeout → the pipeline keeps its existing
LLM-triage + plain-retrieval behaviour. Jev is never the only path to a safe answer.

1. **Triage refinement** (`app/safety/triage.py` → `_jev_refine`). After the deterministic
   rules, Jev returns a calibrated category + confidence. Same contract as the LLM path: it can
   **escalate to crisis** or sharpen a bare in-scope result, but a rules-detected crisis is
   final and is never downgraded. Low confidence on a non-crisis in-scope answer sets
   `low_confidence`, which makes that turn prefer a referral.
2. **Passage filtering / re-rank** (`app/rag/jev_rerank.py`, wired in `services/chat.py`). After
   pgvector retrieval, Jev scores each passage (relevant / answer-evidence / prompt-injection
   nouls) and routes in code to **drop injected or irrelevant chunks** and **re-order the rest by
   relevance** before they reach the generator. If filtering removes everything, the turn
   degrades to a safe referral (as an out-of-knowledge turn would).

**Enable it.** Set `TYPESAFE_API_KEY` (create one at console.typesafe.ai). With no key Jev is
OFF. Toggles/thresholds live in `app/core/config.py` (`JEV_*`): `JEV_MODEL` (default
`jev-latest`), `JEV_TRIAGE_ENABLED`, `JEV_RERANK_ENABLED`, `JEV_RERANK_CANDIDATES`,
`JEV_RELEVANCE_MIN`, `JEV_EVIDENCE_MIN`, `JEV_INJECTION_MAX`, `JEV_TRIAGE_CONFIDENCE_FLOOR`.
Status shows at `GET /v1/admin/system` (`jev: {configured, model, triage, rerank}`) and per-turn
in `safety_flags` (`triage_source: "jev"`, `triage_confidence`, `low_confidence`).

**Tests.** `tests/test_jev.py` covers escalation, confidence gating, passage routing and the
fail-soft path with the SDK stubbed (no network). Dependency: `typesafe-sdk` (in `pyproject`).
