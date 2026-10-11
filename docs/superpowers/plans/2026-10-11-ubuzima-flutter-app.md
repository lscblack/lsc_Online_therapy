# Ubuzima Native Flutter App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A Flutter end-user app (Android/iOS-ready, verified via web build) — onboarding, chat (streaming), turn-based voice, EN/RW, light/dark, settings/wipe — on the existing backend API, with the same safety-first rendering as the web app.

**Architecture:** Flutter 3.41 + Dart, Riverpod state, dio HTTP (streamed SSE), `record` + `just_audio` for voice, `flutter_secure_storage` for tokens. Material 3 warm "buddy" theme, no gradients. Project in `app_flutter/`.

**Spec:** `docs/superpowers/specs/2026-10-11-ubuzima-flutter-app-design.md`

## Global Constraints
- Flutter 3.41 stable; project in `app_flutter/`. API base from `--dart-define=API_BASE=...` (default `http://127.0.0.1:8099`); never hard-code another base.
- **No gradients**; warm buddy palette; light+dark (follow system + override); honor platform reduce-motion + text scale; AA contrast; large tap targets.
- EN + RW, user-togglable + persisted. Crisis/referral/out-of-knowledge = calm supportive, NEVER an error/alarming treatment. The app renders ONLY the backend's guarded answer.
- Tokens in `flutter_secure_storage`; never log tokens/transcripts/message content. Sensitive-context onboarding optional; skip doesn't save typed text; wipe clears local tokens+anon_id and re-bootstraps.
- Each task: `flutter analyze` clean + that task's `flutter test` green; `flutter build web` stays green by the end; pin dep versions in pubspec; commit (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

## Review Focus
- **Backend offline / network error** → calm retry message, no crash. (Task 2)
- **Crisis response** → calm supportive panel + referral, never an error/red/alarming style, in both chat and voice. (Tasks 4, 5)
- **Out-of-knowledge / 503** → calm "see a doctor"/"try later", not an error. (Tasks 4, 6)
- **Mic permission denied** → friendly message, text chat still usable. (Task 5)
- **Wipe** → clears local tokens + anon_id + re-bootstraps (shared-device). (Task 6)

---

### Task 1: Flutter scaffold + theme + i18n + shell
**Files:** `app_flutter/pubspec.yaml`, `lib/main.dart`, `lib/core/config.dart`, `lib/core/theme.dart`, `lib/core/i18n/*`, `lib/features/shell/*`, `test/theme_i18n_test.dart`.
**Interfaces:** Produces the app shell (Material 3 warm theme light+dark, no gradients), a language provider + `t(key)` (en/rw, persisted), config `apiBase`, and a nav scaffold (Chat/Settings tabs) with theme+language toggles.
- [ ] **Step 1:** Test: `t()` returns EN vs RW strings and toggling persists (fake prefs); theme exposes light+dark ColorSchemes with no gradient decorations.
- [ ] **Step 2:** `flutter test` → FAIL (no project/files).
- [ ] **Step 3:** `flutter create` the project under `app_flutter/` (or hand-author), pin deps (flutter_riverpod, dio, record, just_audio, flutter_secure_storage, shared_preferences), build theme/i18n/config/shell.
- [ ] **Step 4:** `flutter test` PASS; `flutter analyze` clean; `flutter build web` green.
- [ ] **Step 5:** Commit.

### Task 2: Data layer (api client, token store, sse, models, auth provider)
**Files:** `lib/data/api_client.dart`, `token_store.dart`, `sse.dart`, `models/*`, `endpoints/{identity,profile,chat,voice}.dart`, `lib/state/auth.dart`, tests.
**Interfaces:** Consumes Task 1 config. Produces `ApiClient` (dio: bearer, single-flight refresh on 401, error-envelope→`ApiError`, network→`ApiError('offline')`), `TokenStore` (secure: user pair + anon_id + clear), `parseSse` (delta/done/error), typed models + endpoint calls, `authProvider` (ensureAnon, adminLogin not needed here).
- [ ] **Step 1:** Tests (mock dio/http): bearer attached; error-envelope→ApiError(code/status); 401→one refresh+retry; transient refresh failure keeps tokens, definitive 401/403 clears; network→'offline' *(Review Focus)*; parseSse yields delta tokens, final on done, throws on error; ensureAnon stores tokens+anon_id (deduped).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `flutter test`+analyze+build web green. **Step 5:** Commit.

### Task 3: Onboarding + profile
**Files:** `lib/features/onboarding/*`, `lib/state/profile.dart`, tests.
**Interfaces:** Consumes Task 2. Produces the wizard → ensureAnon → `PUT /v1/profile` (only provided fields; sensitive only when entered; skip drops it); onboarded flag; re-entrant.
- [ ] **Step 1:** Tests: completing posts expected payload; skip after nickname still usable + minimal payload; sensitive skip sends no sensitive_context; language rw switches app language.
- [ ] **Step 2:** FAIL. **Step 3:** implement (warm, animated, accessible, optional sensitive w/ privacy note). **Step 4:** green. **Step 5:** Commit.

### Task 4: Chat (streaming, bubbles, citations, crisis/referral)
**Files:** `lib/features/chat/*`, `lib/state/chat.dart`, tests.
**Interfaces:** Consumes Task 2 chat. Produces the chat screen (stream via `/v1/chat/stream`, fallback `/v1/chat`), bubbles, citation chips, calm referral + calm crisis rendering, typing indicator, conversation_id continuity, friendly error-retry.
- [ ] **Step 1:** Tests: streaming appends tokens + typing indicator; citations render chips; `safety_flags.crisis` → calm crisis widget (assert NOT an error/alarming style) *(Review Focus)*; out-of-knowledge → calm referral, not error *(Review Focus)*; conversation_id resent; stream error → retry, no crash.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** green. **Step 5:** Commit.

### Task 5: Voice (turn-based)
**Files:** `lib/features/voice/*`, `lib/state/voice.dart`, tests.
**Interfaces:** Consumes Task 2 voice + reuse Task 4 bubble/callout rendering. Produces record→`/v1/voice/chat`→transcript+answer (same safety rendering), play `audio_base64` when tts_available else text, mic-permission handling, "live coming soon" placeholder, mic released on stop/dispose.
- [ ] **Step 1:** Tests (mock record + api): record→stop posts audio and renders transcript+answer; tts_available:false → no playback, text shows; crisis in voice answer → calm crisis widget; mic denied → friendly message, text chat usable *(Review Focus)*; recorder/stream released on dispose.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** green. **Step 5:** Commit.

### Task 6: Settings + shell wiring + build/run docs
**Files:** `lib/features/settings/*`, shell/nav finalize, `app_flutter/README.md`, tests.
**Interfaces:** Consumes all. Produces settings (theme, language, edit profile only-changed, re-run onboarding, wipe=DELETE+clear local tokens/anon_id+re-bootstrap, behind confirm), final nav, run docs.
- [ ] **Step 1:** Tests: wipe calls DELETE then clears local tokens+anon_id + re-bootstraps *(Review Focus)*; edit sends only changed fields; re-run onboarding resets flag; app builds routes without crashing.
- [ ] **Step 2:** FAIL. **Step 3:** implement + README (pub get, dart-define API_BASE, flutter run -d chrome / build web, note native apk needs SDK licenses, fake-provider backend note). **Step 4:** full `flutter test` + `flutter analyze` clean + `flutter build web` green. **Step 5:** Commit.

## Notes for executors
- Pin all pubspec versions. No gradients. Reuse Task 4's chat rendering in Task 5 (don't duplicate safety UI). Keep the backend untouched. Verify with web build; native device runs are a manual follow-up.
