# Ubuzima backend

AI SRHR health-info navigator for Rwandan youth (FastAPI, async, Postgres + pgvector).

## Run
```
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # fill in real values
docker compose up -d db   # or `docker-compose` (v1)     # Postgres on host port 5434 (DBs: ubuzima, ubuzima_test)
uvicorn app.main:app --reload
```
Endpoints: `GET /v1/health`, `GET /v1/ready`.

## Test
```
pytest -v
```
Tests run only against a database whose name ends in `_test` (`TEST_DATABASE_URL`, falling back to `DATABASE_URL`); otherwise pytest aborts.

`docker/init-test-db.sql` (creates `ubuzima_test`) only runs on a fresh volume. If the volume already exists, create it manually:
```
docker compose exec db psql -U postgres -c "CREATE DATABASE ubuzima_test;"
```
Compose reads `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env`; no passwords are hard-coded.
