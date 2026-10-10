# Ubuzima — Backend + RAG Core (Sub-project 1) — Design Spec

- **Date:** 2026-10-11
- **Project:** Ubuzima ("health/life" in Kinyarwanda — working name) — AI-Powered, Low-Connectivity SRHR Digital Navigator for Adolescents and Young People in Rwanda
- **Initiators:** Princia Bella Arakaza & Loue Souver Christian · Potential partner: Health Development Initiative (HDI), Rwanda
- **This spec covers:** Sub-project 1 only (the backend foundation). Sub-projects 2–5 are summarized in the Roadmap for context.

---

## 1. Purpose & Intent (agreed understanding)

A youth-friendly, privacy-conscious, bilingual (Kinyarwanda + English, multilingual-extensible) conversational health companion that answers **only** from a curated, medically-reviewed knowledge base, and refers users to professional care / verified services whenever a question is out of scope, clinically sensitive, or an emergency.

Success for sub-project 1: a running, tested FastAPI backend that can ingest reviewed PDFs, answer grounded questions (text + turn-based voice) in EN/RW with robust safety/referral guardrails, under an anonymous-first identity model, with all external AI behind swappable provider interfaces — ready for the mobile app, realtime voice, offline, and admin sub-projects to build on.

### Confirmed decisions
- **Knowledge:** RAG (embeddings + retrieval), **not** fine-tuning. "Retraining on a PDF" = re-indexing.
- **Offline:** facilities + downloaded content + saved answers work offline (later sub-project); live AI chat requires connectivity. (Rwanda has broad 4G/5G; still design lightweight.)
- **Voice:** core to the product. Turn-based voice ships in sub-project 1; full-duplex barge-in "live" mode is sub-project 2, offered as an **optional** mode.
- **Identity:** anonymous-first, optional account upgrade (recovery PIN/passphrase) for cross-device sync.
- **Personalization (opt-in):** nickname + language; age band + gender/pronouns (optional); interests/tone; **sensitive health context** (opt-in, never required, encrypted at rest, on-device-first, transient to model, easy wipe).
- **Mobile:** Flutter. **LLM:** Claude via OpenRouter. **Embeddings:** local `multilingual-e5` (self-hosted; no user text leaves the server). **KR voice:** Whisper/OpenRouter now behind an interface; Digital Umuganda / Mbaza NLP self-hosted later.

### Non-negotiable safety principles (SRHR, minors, abortion care)
- Provide **general, medically-reviewed information**; never diagnose, never determine legal eligibility, never replace a clinician.
- Abortion care content reflects Rwanda's legal framework and emphasizes professional assessment; no unsupported eligibility/availability claims.
- Always offer referral pathways; escalate crisis (self-harm, GBV/sexual violence, medical emergency) immediately.
- Answers grounded in **approved** documents only; low retrieval confidence → disclaim + refer, never fabricate.
- Data minimization, transparency, easy data wipe; safe on shared devices.

---

## 2. Architecture

**Modular FastAPI monolith** (single deployable service), async end-to-end, strictly layered so each unit has one purpose and a clear interface:

```
app/
  api/v1/          # routers: identity, profile, chat, voice, admin, health, (facilities stub)
  services/        # ChatService, IngestionService, SafetyService, IdentityService, VoiceService, AdminService
  providers/       # LLMProvider, EmbeddingProvider, STTProvider, TTSProvider (Protocols + impls + factory)
  rag/             # chunking, retrieval, prompt assembly, (optional rerank)
  safety/          # input triage, grounding guard, referral catalog, tone/age policy
  repositories/    # async SQLAlchemy data access
  models/          # ORM models
  schemas/         # Pydantic request/response
  core/            # settings, db, security, i18n, logging, exceptions
  main.py
alembic/           # migrations
tests/             # unit, integration, safety red-team
docker-compose.yml # db (custom pgvector/pg17) + api
Dockerfile.db      # FROM postgres:17 + pgvector (matches glibc)
Dockerfile
```

**Dependency rule:** `api → services → (providers | rag | safety | repositories) → core`. No upward imports. Providers and repositories are the only modules that touch the outside world (HTTP/DB/models), so everything above them is unit-testable with fakes.

---

## 3. Data Model (PostgreSQL 17 + pgvector)

- **users**: `id` uuid pk, `anon_id` (device-scoped, unique), `role` enum(user, reviewer, admin), `is_upgraded` bool, `recovery_hash` (argon2, nullable), `locale`, `disabled` bool, `created_at`, `last_seen_at`.
- **profiles**: `user_id` fk pk, `nickname`, `age_band` enum(under15, 15_17, 18_19, 20_24, 25_plus, undisclosed), `gender` (nullable), `pronouns` (nullable), `tone_pref`, `interests` jsonb, `sensitive_context_enc` bytea (nullable, AES-GCM), `consent` jsonb (flags + timestamps), `updated_at`.
- **documents**: `id`, `title`, `source_filename`, `language`, `topic_tags` jsonb, `status` enum(uploaded, processing, indexed, failed), `review_status` enum(pending, approved, rejected), `uploaded_by`, `reviewed_by`, `review_notes`, `version` int, `checksum`, `created_at`, `indexed_at`.
- **document_chunks**: `id`, `document_id` fk, `chunk_index`, `content`, `token_count`, `language`, `metadata` jsonb (page, section, topic), `embedding` `vector(768)` (e5-base; configurable). **HNSW** index on `embedding`; GIN on `metadata`/`topic_tags`. Only chunks of `review_status=approved` docs are retrievable.
- **conversations**: `id`, `user_id` fk, `mode` enum(text, voice), `language`, `created_at`, `last_message_at`.
- **messages**: `id`, `conversation_id` fk, `role` enum(user, assistant, system), `content`, `citations` jsonb (doc/chunk refs), `safety_flags` jsonb, `created_at`. Server-side history is **opt-in & minimal**; default retention short/configurable; ephemeral mode supported.
- **referrals**: curated catalog — `id`, `category` (GBV, crisis, clinic, pharmacy, helpline…), `name`, `contact`, `district`, `languages`, `verified_at`. Seed used by safety escalations; shared with facilities sub-project.
- **facilities** (schema defined now, populated in offline sub-project): `id`, `name`, `type`, `location` (lat/lng), `district`, `services` jsonb, `hours`, `verified_at`.
- **audit_log**: admin/reviewer actions (actor, action, target, metadata, at).

Migrations via **Alembic**. `vector` extension created in migration `0001`.

---

## 4. RAG Pipeline

**Ingest (admin-triggered):** PDF → text extraction (`pypdf`, fallback `unstructured` for scanned → OCR optional later) → clean/normalize → language detect → **recursive semantic chunking** (~400–600 tokens, ~15% overlap) → batch-embed with local e5 → upsert chunks + vectors. Document moves `uploaded → processing → indexed`/`failed`. Re-upload or "reindex" re-runs this (versioned). **Only `approved` docs are retrievable** — ingestion and review are separate steps.

**Retrieve:** embed query (same e5 model, with e5 `query:`/`passage:` prefixes) → pgvector cosine top-k (k≈6, configurable) → optional metadata filter (language/topic) → confidence threshold. Low max-similarity ⇒ "out-of-knowledge" path.

**Generate:** assemble system prompt (persona + scope + safety rules + user profile + language) + retrieved context (with source ids) + recent history → OpenRouter (Claude) **streaming (SSE)**. Enforce inline citations; if out-of-knowledge or sensitive ⇒ safety path overrides.

---

## 5. Safety & Guardrails (first-class module, not an afterthought)

Pipeline order per user turn: **Input triage → (crisis? → escalate) → retrieve → grounding check → generate → output guard → persist flags.**

- **Input triage classifier** (rules + LLM classifier): detects crisis (self-harm/suicide, GBV/sexual violence, acute medical emergency), out-of-scope, and topic routing. Crisis bypasses normal RAG → empathetic message + **referral/helpline** from `referrals` catalog.
- **Grounding guard:** generation must be supported by retrieved approved content; max-similarity below threshold ⇒ disclaimer + doctor/service referral, no fabrication.
- **Policy:** non-judgmental, age-appropriate tone by `age_band`; abortion content framed with Rwandan legal context + professional-assessment emphasis; never diagnoses or rules on eligibility.
- **Output guard:** strips/blocks unsafe content, ensures a referral is present for sensitive categories, ensures citations exist.
- **Red-team test suite:** curated sensitive prompts (crisis, GBV, abortion eligibility, dosage/self-treatment, out-of-scope) with asserted referral/refusal behavior. Part of CI.

---

## 6. Identity & Privacy

- **Anonymous bootstrap:** first contact issues `anon_id` + JWT (access + refresh). No email/phone required. Works on shared devices (no lingering PII by default).
- **Optional upgrade:** user sets a recovery passphrase/PIN → `recovery_hash` (argon2) enabling cross-device recovery/sync. Fully optional.
- **Admin/reviewer accounts:** email + password (argon2), role-based access control; separate from end-user anon identities.
- **Sensitive data:** profile sensitive fields optional & **encrypted at rest (AES-GCM)**, key from env/secret manager; transient to model only; **wipe endpoint** clears profile/history. Consent flags recorded. Configurable, short default chat retention; ephemeral mode.

---

## 7. Provider Abstraction (swappable AI)

`Protocol` interfaces + concrete impls + settings-driven factory:
- `LLMProvider.stream_chat(messages, **opts) -> AsyncIterator[str]` — **OpenRouterLLM** (Claude).
- `EmbeddingProvider.embed(texts, kind) -> list[vector]` — **LocalE5Embeddings** (sentence-transformers, CPU-ok).
- `STTProvider.transcribe(audio, language) -> Transcript` — **OpenRouterWhisperSTT** now; `DigitalUmugandaSTT` interface stubbed.
- `TTSProvider.synthesize(text, language, voice) -> audio` — **OpenRouterTTS** now; `DigitalUmugandaTTS`/`MbazaTTS` stubbed.

All providers have **fake/mock impls** for tests. Real network calls only behind an integration marker. OpenRouter accessed via `httpx` against OpenAI-compatible endpoints (`/chat/completions`, `/audio/speech`, `/audio/transcriptions`).

---

## 8. API Surface (v1)

- `POST /v1/identity/anon` → tokens · `POST /v1/identity/upgrade` · `POST /v1/identity/recover` · `POST /v1/identity/refresh`
- `GET /v1/profile` · `PUT /v1/profile` · `DELETE /v1/profile` (wipe)
- `POST /v1/chat` (JSON) · `POST /v1/chat/stream` (SSE) — `{message, conversation_id?, language}`
- `POST /v1/voice/transcribe` (audio→text) · `POST /v1/voice/speak` (text→audio) · `POST /v1/voice/chat` (audio→audio turn: STT→chat→TTS)
- **Admin/reviewer:** `POST /v1/admin/documents` (upload) · `GET /v1/admin/documents` · `GET /v1/admin/documents/{id}` · `POST /v1/admin/documents/{id}/review` · `POST /v1/admin/documents/{id}/reindex` · `DELETE /v1/admin/documents/{id}` · `GET /v1/admin/users` · `POST /v1/admin/users/{id}/disable` · `GET /v1/admin/audit`
- `GET /v1/health` · `GET /v1/ready`
- `WS /v1/live` — **reserved** interface stub for sub-project 2 (full-duplex barge-in).

Responses bilingual via `Accept-Language`/`language` param; error envelope standardized; all sensitive endpoints rate-limited.

---

## 9. Config & Infrastructure

- **Settings** via `pydantic-settings` from `.env`: `DATABASE_URL` (project Postgres, port 5434, db `ubuzima`), `OPENROUTER_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`, `ENCRYPTION_KEY`, `JWT_SECRET`, retention/threshold knobs.
- **docker-compose:** `db` (built from `Dockerfile.db`: `FROM postgres:17` + pgvector, **matching glibc** — avoids the collation-mismatch corruption seen with the prebuilt pgvector image), `api`. Own named volume, port 5434. The user's existing `ijwi-pg` (port 5433) is left untouched.
- **Migrations:** Alembic; `0001` enables `vector`, creates schema.

---

## 10. Testing Strategy (TDD)

- **Unit:** chunking, e5 prefixing + embedding dims, safety triage rules, grounding threshold, prompt assembly, provider factory, AES-GCM encryption, JWT/argon2, i18n.
- **Integration (test DB `ubuzima_test` / testcontainer):** ingest→retrieve roundtrip (real pgvector), chat with **mocked** LLM, voice pipeline with mocked STT/TTS, admin upload→review→reindex→retrievable, RBAC enforcement, profile wipe.
- **Safety red-team suite:** asserted escalation/referral/refusal behavior for crisis/GBV/abortion-eligibility/self-treatment/out-of-scope prompts (CI gate).
- **Tooling:** `pytest`, `pytest-asyncio`, `respx` (mock OpenRouter), coverage gate. Mocked providers by default; real-provider tests behind marker.

---

## 11. Roadmap (sub-projects 2–5; each gets its own spec → plan → build)

2. **Realtime full-duplex voice** — `WS /v1/live`: VAD, barge-in, continuous STT→LLM→TTS streaming; offered as an **optional** mode alongside turn-based voice. Built on sub-project 1's provider abstraction.
3. **Mobile app (Flutter)** — onboarding (buddy personalization), text/voice/live UI, EN/RW, light+dark, **no-gradient** modern youth design, animations, local DB for offline.
4. **Offline** — knowledge/content sync for offline reading + saved answers; offline nearby-facility finder (bundled verified facility dataset + on-device geo/search).
5. **Web admin panel** — user/system management, PDF upload, review workflow, re-index ("retrain") dashboard, facility & referral directory management, analytics/M&E per concept note.

---

## 12. Out of Scope (sub-project 1)
Mobile UI, full-duplex realtime WebSocket implementation, offline sync, admin web UI, SMS/USSD, self-hosted Kinyarwanda speech models, facility data population. Interfaces/stubs are provided so these slot in without refactoring.
