# Ubuzima Web Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A mobile-responsive React web app — youth end-user experience (`/`) + admin panel (`/admin`) — that a person can use in a browser against the running backend, with a warm "buddy" design, EN/RW, light/dark, and no gradients.

**Architecture:** Vite + React 18 + TypeScript SPA in `web/`. Typed fetch API client with anon + admin auth. CSS-custom-property theming (no gradients). Framer Motion micro-animations. Vitest + RTL tests; `tsc` + `vite build` gate. One additive backend change: CORS.

**Spec:** `docs/superpowers/specs/2026-10-11-ubuzima-web-frontend-design.md`

## Global Constraints
- Vite + React 18 + TypeScript, strict mode; code in `web/`. Node 24 available.
- Talks to backend at `import.meta.env.VITE_API_BASE` (default `http://127.0.0.1:8099`); never hard-code another base.
- **No gradients** anywhere; warm buddy palette; light + dark via CSS vars (`:root` + `[data-theme="dark"]` + `prefers-color-scheme`); WCAG-AA contrast; `prefers-reduced-motion` respected; touch targets ≥44px; responsive 360px→desktop, no horizontal scroll.
- EN + RW via a frontend string dict + `useT()`; user-togglable; persisted (localStorage, try/catch).
- Crisis/referral/out-of-knowledge responses get distinct **calm, supportive** styling (not alarming red).
- Secrets/tokens never logged to console; sensitive-context field explicitly optional with a privacy note; wipe available.
- Each task: `tsc --noEmit` clean + the task's Vitest tests pass + `vite build` stays green; commit (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

## Review Focus
- **Backend unreachable / network error** → friendly retry message, no white screen. (Task 2)
- **503 provider-unavailable** (fake mode off, no key) and **out-of-knowledge** answer → clear non-scary messaging, not an error. (Tasks 4, 6)
- **Crisis response** → rendered with supportive styling + referral prominent, never a red "error" look. (Task 4)
- **Admin reviewer vs admin role** → admin-only actions hidden/disabled for reviewer; 401/403 handled. (Task 6)
- **Mobile 360px width** → chat, onboarding, admin tables usable, no overflow. (Tasks 3,4,6,7)

---

### Task 1: Backend CORS + Vite/React/TS scaffold + theming + i18n shell
**Files:** Backend: modify `app/main.py` (+ `app/core/config.py` `cors_origins`). Frontend create: `web/package.json`, `vite.config.ts`, `tsconfig.json`, `vitest.config.ts`, `index.html`, `web/.env.example`, `src/main.tsx`, `src/App.tsx`, `src/router.tsx`, `src/theme/tokens.css`, `src/theme/ThemeProvider.tsx`, `src/i18n/{en,rw}.ts`, `src/i18n/useT.ts`, `src/components/{ThemeToggle,LangToggle}.tsx`, `tests` for theme/i18n.
**Interfaces:** Produces the app shell, `ThemeProvider` (light/dark, persisted), `useT()` (en/rw), router with `/` and `/admin` placeholders, and the CORS-enabled backend.
- [ ] **Step 1:** Backend test `tests/test_cors.py::test_cors_allows_configured_origin` (an OPTIONS/GET with `Origin: http://localhost:5173` returns the `access-control-allow-origin`). Frontend test: `useT` returns EN vs RW strings; ThemeProvider toggles `data-theme` and persists.
- [ ] **Step 2:** Run backend test (FAIL), `npm test` (FAIL/none).
- [ ] **Step 3:** Add CORS middleware reading `cors_origins` (default localhost/127.0.0.1:5173). Scaffold Vite app; tokens.css (no gradients, warm palette, light+dark); ThemeProvider; i18n; router shell; theme/lang toggles. Pin dep versions.
- [ ] **Step 4:** Backend test PASS; `npm test` PASS; `npm run build` + `tsc --noEmit` clean.
- [ ] **Step 5:** Commit.

### Task 2: Typed API client + auth (anon + admin) + token store
**Files:** `src/api/client.ts`, `src/api/types.ts`, `src/api/{identity,profile,chat,voice,admin}.ts`, `src/auth/tokenStore.ts`, `src/auth/useAuth.tsx`, tests `src/api/__tests__/*` (msw).
**Interfaces:** Consumes Task 1. Produces `apiFetch` (base URL, bearer header, refresh-on-401, error-envelope→typed error), `tokenStore` (get/set/clear, try/catch localStorage), `useAuth` (anon bootstrap on load, admin login/logout), typed endpoint fns.
- [ ] **Step 1:** Tests (msw): apiFetch attaches bearer + parses `{error:{code,message}}`; a 401 triggers one refresh then retry; `identity.anon()` stores tokens; `admin.login()` stores admin tokens separately; a network error surfaces a typed "offline" error. *(Review Focus: network error)*
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement client + token store + auth hook + endpoint fns (identity anon/upgrade/recover/refresh, profile get/put/delete, chat + chat/stream, voice transcribe/speak/chat, admin login/documents/users/audit).
- [ ] **Step 4:** `npm test` PASS; build clean.
- [ ] **Step 5:** Commit.

### Task 3: Onboarding flow + profile
**Files:** `src/features/onboarding/*`, wire into `/`, tests.
**Interfaces:** Consumes Task 2 (identity, profile). Produces the onboarding wizard → creates anon identity + `PUT /v1/profile`; skippable; re-entrant from settings.
- [ ] **Step 1:** Test: completing onboarding posts the expected profile payload (nickname/language/age_band/pronouns/interests/tone; sensitive context only when provided) and marks onboarding done; skipping still yields a usable session. *(Review Focus: 360px)*
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement the wizard (warm, animated, accessible; sensitive-context step clearly optional + privacy note). Persist "onboarded".
- [ ] **Step 4:** tests PASS; build clean.
- [ ] **Step 5:** Commit.

### Task 4: Chat screen (SSE streaming, citations, safety/crisis rendering)
**Files:** `src/features/chat/*` (ChatScreen, MessageList, Bubble, Composer, sseParser.ts, callouts), tests.
**Interfaces:** Consumes Task 2 chat endpoints. Produces the chat UI with streaming, citation chips, referral/out-of-knowledge callouts, crisis styling, typing indicator, conversation continuity.
- [ ] **Step 1:** Tests: `sseParser` yields incremental tokens from a chunked SSE body and ignores `[DONE]`; a message with `citations` renders source chips; a `safety_flags.crisis` response renders the calm crisis callout with the referral prominent (NOT an error/red style) *(Review Focus: crisis)*; an out-of-knowledge answer renders the "talk to a doctor" callout, not an error *(Review Focus)*.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement ChatScreen (stream via `/v1/chat/stream`, fall back to `/v1/chat`), bubbles, callouts, animations, reduced-motion, conversation_id continuity.
- [ ] **Step 4:** tests PASS; build clean.
- [ ] **Step 5:** Commit.

### Task 5: Voice (turn-based record → reply)
**Files:** `src/features/voice/*`, tests.
**Interfaces:** Consumes Task 2 voice endpoints. Produces mic record (MediaRecorder) → `POST /v1/voice/chat` → show transcript+answer, play `audio_base64` when `tts_available` else show text; a "Live mode coming soon" placeholder.
- [ ] **Step 1:** Tests (mock MediaRecorder + fetch): recording then stopping posts multipart audio and renders the returned transcript+answer; when `tts_available:false` no audio play is attempted and the text still shows; permission-denied mic → friendly message.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement voice capture/playback UI (accessible, animated record button), guard mic-permission errors.
- [ ] **Step 4:** tests PASS; build clean.
- [ ] **Step 5:** Commit.

### Task 6: Admin panel (`/admin`)
**Files:** `src/features/admin/*` (Login, Documents, UploadDialog, Review, Users, Audit, adminGuard), tests.
**Interfaces:** Consumes Task 2 admin endpoints. Produces admin login + documents (list/upload/review/reindex/delete + status badges) + users (list/disable) + audit; RBAC-aware UI.
- [ ] **Step 1:** Tests: admin login stores admin tokens and reveals the panel; uploading posts multipart (title+file); approve calls `…/review`; a reviewer token hides admin-only actions (delete/users/audit) *(Review Focus: RBAC)*; a 503 shows a clear message.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement the admin section (tables responsive at 360px, status badges, confirm dialogs for destructive actions, role-gated controls).
- [ ] **Step 4:** tests PASS; build clean.
- [ ] **Step 5:** Commit.

### Task 7: Settings, responsive/polish pass, run docs
**Files:** `src/features/settings/*`, layout/nav, `web/README.md`, final `App`/router wiring, tests.
**Interfaces:** Consumes all. Produces settings (theme, language, edit profile, wipe-with-confirm), app nav/layout, a responsive pass, and run docs.
- [ ] **Step 1:** Tests: wipe calls `DELETE /v1/profile` after confirm; language/theme toggles persist; `test_app_routes` renders `/` and `/admin` without crashing.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement settings + nav; responsive audit (no overflow at 360px); README (install, VITE_API_BASE, dev server, how to log in as admin, note on fake-provider placeholder answers).
- [ ] **Step 4:** Full `npm test` PASS; `tsc --noEmit` + `npm run build` clean.
- [ ] **Step 5:** Commit.

## Notes for executors
- Pin exact dependency versions. Keep bundle lean. No gradient CSS. Respect `prefers-reduced-motion`.
- Don't change backend behavior beyond adding CORS. The backend runs in fake-provider mode, so answers are placeholder — design the empty/out-of-knowledge states to look intentional, not broken.
