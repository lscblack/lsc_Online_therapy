# Ubuzima backend

AI SRHR health-info navigator for Rwandan youth (FastAPI, async, Postgres + pgvector).

## Run
```
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # fill in real values
docker-compose up -d db     # Postgres on host port 5434 (DBs: ubuzima, ubuzima_test)
uvicorn app.main:app --reload
```
Endpoints: `GET /v1/health`, `GET /v1/ready`.

## Test
```
pytest -v
```
Tests use `.env`; point `DATABASE_URL` at `ubuzima_test`.
