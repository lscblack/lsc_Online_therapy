# Ubuzima Backend + RAG Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested, runnable FastAPI backend that ingests medically-reviewed PDFs, answers grounded SRHR questions (text + turn-based voice) in Kinyarwanda/English with safety/referral guardrails, under an anonymous-first identity model, with all external AI behind swappable providers.

**Architecture:** Modular async FastAPI monolith, strictly layered `api → services → (providers | rag | safety | repositories) → core`. Providers and repositories are the only outward-facing modules, so everything above them is unit-testable with fakes. PostgreSQL 17 + pgvector for app data and vectors.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, SQLAlchemy 2 (async) + asyncpg, Alembic, pydantic-settings, pgvector, sentence-transformers (multilingual-e5-base), pypdf, httpx, PyJWT, argon2-cffi, cryptography, langdetect, pytest + pytest-asyncio + respx.

**Spec:** `docs/superpowers/specs/2026-10-11-ubuzima-backend-rag-core-design.md`

## Global Constraints

- Python **3.13**; FastAPI monolith, async end-to-end (no sync DB calls in request path).
- Layering rule: no module imports a layer above it; only `providers/` and `repositories/` touch HTTP/DB.
- Project owns its Postgres: `docker-compose` service `db` built from `Dockerfile.db` (`FROM postgres:17` + pgvector, matching glibc), port **5434**, DB **`ubuzima`**, test DB **`ubuzima_test`**. Never touch the user's `ijwi-pg` on 5433.
- Embedding model `intfloat/multilingual-e5-base`, dimension **768**, with `query:`/`passage:` prefixes. Vector column `vector(768)`.
- LLM via OpenRouter (`LLM_MODEL` default an Anthropic Claude id), OpenAI-compatible base `https://openrouter.ai/api/v1`.
- Only documents with `review_status='approved'` are retrievable in RAG.
- Sensitive profile fields encrypted at rest (AES-GCM). No sensitive end-user PII required anywhere.
- All config from `.env` via pydantic-settings; secrets never hard-coded or logged.
- Every external AI provider has a fake impl; unit/integration tests use fakes; real-network tests behind `@pytest.mark.integration`.
- TDD: test first, watch it fail, implement minimally, watch it pass, commit.

## Review Focus

- **Malformed / scanned / empty PDF on ingest** → document marked `failed` with reason, no crash, no partial chunks. (Task 6)
- **Out-of-knowledge question** (max similarity below threshold) → disclaimer + professional referral, never a fabricated answer. (Tasks 7, 8, 9)
- **Crisis / GBV / self-harm input** → bypass RAG, empathetic response + referral/helpline, regardless of language. (Tasks 8, 9)
- **Expired / forged / wrong-role JWT** on admin endpoints → 401/403, never silent allow. (Tasks 4, 11)
- **Mixed / unsupported language input** → language detection falls back safely; response language honored or defaulted, never 500. (Tasks 7, 9)

---

### Task 1: Project scaffold, config, DB infra, health

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `Dockerfile`, `Dockerfile.db`, `docker-compose.yml`, `app/__init__.py`, `app/main.py`, `app/core/config.py`, `app/core/db.py`, `app/api/v1/health.py`, `tests/conftest.py`, `tests/test_health.py`, `README.md`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `app.core.config.Settings` (pydantic-settings; fields incl. `database_url`, `openrouter_api_key`, `llm_model`, `embedding_model`, `encryption_key`, `jwt_secret`, retention/threshold knobs) and `get_settings()`; `app.core.db.engine`, `async_session`, `get_session()` dependency; `app.main.app` (FastAPI).

- [ ] **Step 1:** Write `tests/test_health.py::test_health_ok` — GET `/v1/health` → 200 `{"status":"ok"}`; and `test_ready_checks_db` — GET `/v1/ready` → 200 when DB reachable.
- [ ] **Step 2:** Run `pytest tests/test_health.py -v` → FAIL (app missing).
- [ ] **Step 3:** Implement `Settings`/`get_settings()`, async engine/session from `database_url`, `health.py` router (`/v1/health`, `/v1/ready` pinging DB), assemble `app.main.app`. Write `Dockerfile.db` (`FROM postgres:17`, install pgvector so glibc matches), `docker-compose.yml` (`db` on 5434 + `api`), `.env.example`, `pyproject.toml` deps, `README.md` run steps.
- [ ] **Step 4:** Run `pytest tests/test_health.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 2: Database models + Alembic migration 0001

**Files:**
- Create: `app/models/__init__.py`, `app/models/base.py`, `app/models/user.py`, `app/models/profile.py`, `app/models/document.py`, `app/models/conversation.py`, `app/models/referral.py`, `app/models/facility.py`, `app/models/audit.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_init.py`, `tests/test_migration.py`
- Test: `tests/test_migration.py`

**Interfaces:**
- Consumes: Task 1 `engine`, `Settings`.
- Produces: ORM classes `User, Profile, Document, DocumentChunk, Conversation, Message, Referral, Facility, AuditLog` with the columns/enums from spec §3; `DocumentChunk.embedding` = `Vector(768)`. Enums `UserRole`, `AgeBand`, `DocStatus`, `ReviewStatus`, `MessageRole`, `ConversationMode`.

- [ ] **Step 1:** Write `tests/test_migration.py::test_upgrade_creates_tables_and_vector` — run Alembic upgrade head against `ubuzima_test`; assert `vector` extension present, all tables exist, and an HNSW index exists on `document_chunks.embedding`.
- [ ] **Step 2:** Run `pytest tests/test_migration.py -v` → FAIL.
- [ ] **Step 3:** Implement models + `Base`; wire `alembic/env.py` to metadata + `database_url`; write `0001_init.py` (`CREATE EXTENSION vector`, all tables, enum types, HNSW index on embedding, GIN on jsonb tag columns).
- [ ] **Step 4:** Run `pytest tests/test_migration.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 3: Provider abstraction layer

**Files:**
- Create: `app/providers/__init__.py`, `app/providers/base.py`, `app/providers/llm_openrouter.py`, `app/providers/embeddings_e5.py`, `app/providers/stt_openrouter.py`, `app/providers/tts_openrouter.py`, `app/providers/stubs_digitalumuganda.py`, `app/providers/fakes.py`, `app/providers/factory.py`, `tests/providers/test_factory.py`, `tests/providers/test_embeddings_e5.py`, `tests/providers/test_openrouter.py`
- Test: as above

**Interfaces:**
- Consumes: Task 1 `Settings`.
- Produces: Protocols `LLMProvider.stream_chat(messages: list[dict], **opts) -> AsyncIterator[str]`, `EmbeddingProvider.embed(texts: list[str], kind: Literal["query","passage"]) -> list[list[float]]`, `STTProvider.transcribe(audio: bytes, language: str|None) -> Transcript`, `TTSProvider.synthesize(text: str, language: str, voice: str|None) -> bytes`; concrete impls; `fakes.FakeLLM/FakeEmbeddings/FakeSTT/FakeTTS`; `factory.get_llm()/get_embeddings()/get_stt()/get_tts()` selecting impl by settings.

- [ ] **Step 1:** Write `test_factory.py` (factory returns fakes when configured `fake`, concrete when configured provider); `test_embeddings_e5.py::test_embed_dim_768` (real e5, `@pytest.mark.integration`, applies `passage:` prefix, returns 768-length vectors); `test_openrouter.py` (respx-mock `/chat/completions` streaming yields chunks; `/audio/transcriptions` returns text; `/audio/speech` returns bytes).
- [ ] **Step 2:** Run the provider tests → FAIL.
- [ ] **Step 3:** Implement Protocols in `base.py`, concrete OpenRouter impls over `httpx` (streaming SSE parse), `LocalE5Embeddings` via sentence-transformers, Digital Umuganda stubs raising `NotImplementedError`, fakes, and settings-driven `factory`.
- [ ] **Step 4:** Run `pytest tests/providers -v -m "not integration"` → PASS (mark e5 test integration).
- [ ] **Step 5:** Commit.

---

### Task 4: Identity, JWT auth, RBAC

**Files:**
- Create: `app/repositories/users.py`, `app/services/identity.py`, `app/core/security.py`, `app/schemas/identity.py`, `app/api/v1/identity.py`, `app/api/deps.py`, `tests/test_identity.py`
- Test: `tests/test_identity.py`

**Interfaces:**
- Consumes: Task 2 `User`, Task 1 session/settings.
- Produces: `security.create_access_token/create_refresh_token/decode_token`, `security.hash_secret/verify_secret` (argon2); `IdentityService.bootstrap_anon()`, `.upgrade(user, passphrase)`, `.recover(passphrase)`, `.login_admin(email, password)`; FastAPI deps `current_user`, `require_role(role)`.

- [ ] **Step 1:** Write `tests/test_identity.py`: `test_anon_bootstrap_returns_tokens`, `test_upgrade_sets_recovery_and_recover_works`, `test_admin_login_and_rbac` (user token rejected 403 on admin dep; admin token allowed), `test_expired_and_forged_token_rejected` (401). *(covers Review Focus: JWT)*
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement security (PyJWT + argon2), users repo, `IdentityService`, identity router, `deps.current_user`/`require_role`.
- [ ] **Step 4:** Run `pytest tests/test_identity.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 5: Profile + field encryption

**Files:**
- Create: `app/core/crypto.py`, `app/repositories/profiles.py`, `app/services/profile.py`, `app/schemas/profile.py`, `app/api/v1/profile.py`, `tests/test_profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: Task 2 `Profile`, Task 4 `current_user`.
- Produces: `crypto.encrypt(plaintext: str) -> bytes` / `crypto.decrypt(blob: bytes) -> str` (AES-GCM, key from settings); `ProfileService.get/upsert/wipe`.

- [ ] **Step 1:** Write `tests/test_profile.py`: `test_crypto_roundtrip`, `test_sensitive_context_stored_encrypted` (raw DB column != plaintext), `test_get_put_profile`, `test_wipe_clears_profile_and_history`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement AES-GCM crypto, profiles repo, `ProfileService`, profile router (`GET/PUT/DELETE /v1/profile`).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 6: RAG ingestion + document lifecycle/review

**Files:**
- Create: `app/rag/chunking.py`, `app/rag/extract.py`, `app/repositories/documents.py`, `app/services/ingestion.py`, `app/schemas/document.py`, `tests/rag/test_chunking.py`, `tests/rag/test_ingestion.py`, `tests/fixtures/sample.pdf`, `tests/fixtures/empty.pdf`
- Test: as above

**Interfaces:**
- Consumes: Task 2 `Document/DocumentChunk`, Task 3 `get_embeddings()`.
- Produces: `extract.extract_text(data: bytes) -> list[Page]`; `chunking.chunk(pages, max_tokens=500, overlap=0.15) -> list[Chunk]`; `IngestionService.ingest(document_id)`, `.create_document(...)`, `.set_review(document_id, status, reviewer)`, `.reindex(document_id)`.

- [ ] **Step 1:** Write `test_chunking.py` (token sizing + overlap, no chunk exceeds max); `test_ingestion.py`: `test_ingest_pdf_creates_chunks_with_embeddings`, `test_empty_or_bad_pdf_marks_failed` *(Review Focus: bad PDF)*, `test_only_approved_docs_retrievable` (chunks of pending doc excluded from a retrieval query), `test_reindex_replaces_chunks`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement extract (pypdf), chunking (recursive, token-based), documents repo, `IngestionService` with lifecycle `uploaded→processing→indexed/failed` + review workflow; use FakeEmbeddings in tests.
- [ ] **Step 4:** Run `pytest tests/rag -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 7: RAG retrieval + prompt assembly

**Files:**
- Create: `app/rag/retrieval.py`, `app/rag/prompt.py`, `tests/rag/test_retrieval.py`, `tests/rag/test_prompt.py`
- Test: as above

**Interfaces:**
- Consumes: Task 2 models, Task 3 embeddings, Task 6 ingested chunks.
- Produces: `retrieval.retrieve(query, language, k=6) -> RetrievalResult` (`.chunks`, `.max_score`, `.in_knowledge: bool` by threshold); `prompt.build_system_prompt(profile, language)`, `prompt.assemble(query, retrieval, history, profile, language) -> list[dict]` (persona, scope, citations instruction).

- [ ] **Step 1:** Write `test_retrieval.py`: `test_retrieve_ranks_by_similarity`, `test_language_filter`, `test_below_threshold_marks_out_of_knowledge` *(Review Focus: out-of-knowledge)*, `test_mixed_language_query_defaults_safely` *(Review Focus: language)*; `test_prompt.py`: `test_prompt_includes_persona_scope_and_citations`, `test_prompt_respects_age_band_and_language`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement pgvector cosine top-k with threshold + language filter; prompt builder with buddy persona, SRHR scope boundaries, Rwanda legal framing note, citation instruction.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 8: Safety module (triage, grounding, referrals, output guard)

**Files:**
- Create: `app/safety/triage.py`, `app/safety/referrals.py`, `app/safety/guard.py`, `app/safety/policy.py`, `app/repositories/referrals.py`, `tests/safety/test_triage.py`, `tests/safety/test_guard.py`, `tests/safety/test_redteam.py`, `app/safety/data/referrals_seed.json`
- Test: as above

**Interfaces:**
- Consumes: Task 3 LLM (classifier), Task 7 retrieval result, Task 2 `Referral`.
- Produces: `triage.classify(text, language) -> Triage` (`.category`, `.is_crisis`, `.in_scope`); `referrals.lookup(category, district=None) -> list[Referral]`; `guard.ground(answer, retrieval) -> GuardResult`; `guard.ensure_referral(response, category)`; `policy.tone_for(age_band)`.

- [ ] **Step 1:** Write `test_triage.py` (crisis/GBV/self-harm detected in EN **and** RW; out-of-scope flagged) *(Review Focus: crisis, language)*; `test_guard.py` (ungrounded answer → disclaimer+referral) *(Review Focus: out-of-knowledge)*; `test_redteam.py` — table of sensitive prompts (abortion eligibility, self-treatment dosage, suicide, GBV, off-topic) each asserting expected escalate/refer/refuse behavior.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement rule-based + LLM-classifier triage (FakeLLM in tests returns scripted labels), referral catalog + seed loader, grounding/output guards, age-band policy.
- [ ] **Step 4:** Run `pytest tests/safety -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 9: Chat service + endpoints (text, streaming)

**Files:**
- Create: `app/services/chat.py`, `app/repositories/conversations.py`, `app/schemas/chat.py`, `app/api/v1/chat.py`, `tests/test_chat.py`
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: Tasks 3,5,7,8 (LLM, profile, retrieval+prompt, safety).
- Produces: `ChatService.respond(user, message, conversation_id, language) -> ChatResult` (orchestrates triage→retrieve→ground→generate→guard→persist); `.stream(...)` async generator. Routes `POST /v1/chat`, `POST /v1/chat/stream` (SSE).

- [ ] **Step 1:** Write `tests/test_chat.py`: `test_grounded_answer_has_citations` (FakeLLM + ingested fixture), `test_out_of_knowledge_refers_to_doctor` *(Review Focus)*, `test_crisis_input_bypasses_rag_and_refers` *(Review Focus)*, `test_stream_yields_sse_chunks`, `test_response_language_honored` *(Review Focus: language)*.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `ChatService` orchestration + conversations repo (minimal/opt-in persistence) + routers (JSON + SSE).
- [ ] **Step 4:** Run `pytest tests/test_chat.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 10: Voice endpoints (turn-based)

**Files:**
- Create: `app/services/voice.py`, `app/schemas/voice.py`, `app/api/v1/voice.py`, `tests/test_voice.py`
- Test: `tests/test_voice.py`

**Interfaces:**
- Consumes: Task 3 STT/TTS, Task 9 ChatService.
- Produces: `VoiceService.transcribe(audio, language)`, `.speak(text, language, voice)`, `.voice_chat(audio, language)` (STT→ChatService→TTS). Routes `POST /v1/voice/transcribe|speak|chat`.

- [ ] **Step 1:** Write `tests/test_voice.py`: `test_transcribe_returns_text` (FakeSTT), `test_speak_returns_audio` (FakeTTS), `test_voice_chat_roundtrip` (audio in → audio out, safety applied).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `VoiceService` + routes (multipart audio in, audio/stream out).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 11: Admin endpoints (documents, users, audit)

**Files:**
- Create: `app/services/admin.py`, `app/repositories/audit.py`, `app/schemas/admin.py`, `app/api/v1/admin.py`, `tests/test_admin.py`
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: Task 4 `require_role('admin'/'reviewer')`, Task 6 ingestion, Task 2 models.
- Produces: routes `POST /v1/admin/documents` (upload), `GET /v1/admin/documents`, `GET /{id}`, `POST /{id}/review`, `POST /{id}/reindex`, `DELETE /{id}`, `GET /v1/admin/users`, `POST /v1/admin/users/{id}/disable`, `GET /v1/admin/audit`; `AdminService` writing `AuditLog`.

- [ ] **Step 1:** Write `tests/test_admin.py`: `test_upload_then_review_then_retrievable` (full lifecycle), `test_reindex`, `test_non_admin_forbidden` (403) *(Review Focus: RBAC)*, `test_actions_are_audited`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `AdminService` + audit repo + router, RBAC-guarded; upload stores file + triggers ingestion.
- [ ] **Step 4:** Run `pytest tests/test_admin.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 12: Live WS stub, final wiring, compose smoke, docs

**Files:**
- Create: `app/api/v1/live.py`, `tests/test_app_wiring.py`
- Modify: `app/main.py` (mount all routers, OpenAPI metadata, i18n/error envelope middleware), `README.md`
- Test: `tests/test_app_wiring.py`

**Interfaces:**
- Consumes: all routers.
- Produces: `WS /v1/live` reserved endpoint returning a clear "not yet available (sub-project 2)" close; fully assembled `app` with standardized error envelope + `Accept-Language` handling.

- [ ] **Step 1:** Write `tests/test_app_wiring.py`: `test_all_routes_registered` (OpenAPI lists identity/profile/chat/voice/admin/health), `test_live_ws_returns_not_available`, `test_error_envelope_shape`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Mount routers, add error-envelope + language middleware, implement `live.py` stub, finalize README (compose up, migrate, seed admin, env vars).
- [ ] **Step 4:** Run full suite `pytest -m "not integration" -v` → PASS; then `docker compose up -d db && alembic upgrade head` smoke (document in README).
- [ ] **Step 5:** Commit.

---

## Notes for executors
- Seed a first admin via a small CLI/management step (documented in README); do not hard-code credentials.
- Keep Kinyarwanda/English copy strings centralized (`app/core/i18n.py`) so the mobile/admin sub-projects reuse them.
- Real OpenRouter/e5 calls are `@pytest.mark.integration`; the default CI run excludes them and uses fakes.
