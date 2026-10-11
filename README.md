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
  `RATE_LIMIT_CHAT_PER_MIN` (30, per identity: chat + voice). In-process only, so limits are
  per worker, not shared; use a gateway/Redis limiter when scaling out.

### First admin
There is no public admin signup. Create one with the CLI (no credentials are hard-coded):
`python -m app.cli create_admin --email you@org.example [--role reviewer]`. The password is
prompted (or `--password`, which lands in shell history). Duplicate emails exit 1.
Then `POST /v1/admin/login`.

### Behaviour notes
- Errors: `{"error": {"code", "message", "details"?}}` for every 4xx/5xx; validation details
  list only `loc` + `message` (inputs are never echoed). 500s are generic.
- `Accept-Language: en|rw` sets the reply language for chat/voice when the request body does
  not specify `language`.
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
