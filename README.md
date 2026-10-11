# Ubuzima

AI-powered SRHR (sexual & reproductive health and rights) digital navigator for
young people in Rwanda. A private, youth-friendly health companion that answers
from a curated, clinically-reviewed knowledge base (RAG) over chat and voice, in
**English and Kinyarwanda**, and refers to a health worker whenever a question is
outside its knowledge or needs professional care.

Partner: Health Development Initiative (HDI).

## Repository layout

```
backend/   FastAPI service — RAG, safety/referral engine, auth, realtime voice (Python 3.13, Postgres + pgvector)
web/        React + Vite admin & web client (TypeScript)
mobile/     Flutter app — chat, voice, onboarding, settings (Android/iOS, verified via web build)
docs/       Design specs and implementation plans
```

Each sub-project has its own README with setup and run instructions:
- [backend/README.md](backend/README.md)
- [web/README.md](web/README.md)
- [mobile/README.md](mobile/README.md)

## Quick start (dev)

```sh
# 1. Backend (http://127.0.0.1:8099)
cd backend
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in DATABASE_URL, OPENROUTER_API_KEY, keys, DEFAULT_ADMIN_* …
docker compose up -d db         # Postgres + pgvector on host port 5434
alembic upgrade head
uvicorn app.main:app --reload --port 8099

# 2. Web admin/client (http://127.0.0.1:5173)
cd web && npm install
VITE_API_BASE=http://127.0.0.1:8099 npm run dev

# 3. Mobile app (web preview)
cd mobile && flutter pub get
flutter run -d chrome --dart-define=API_BASE=http://127.0.0.1:8099
```

## Design principles

- **Safety first.** Crisis/GBV detection and the referral ("see a health worker")
  rules run independently of the LLM and can only escalate, never downgrade.
- **Grounded answers only.** The bot answers from approved, indexed documents; out-of-knowledge
  questions get a calm referral, never a fabricated answer.
- **Private by default.** Anonymous-first identity with optional account recovery; sensitive
  profile context is encrypted at rest.
- **Accessible.** Blue/green palette, light + dark modes, no gradients, large tap targets,
  reduce-motion honored, EN/RW throughout.
