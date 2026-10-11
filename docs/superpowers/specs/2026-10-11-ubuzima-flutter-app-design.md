# Ubuzima — Native Flutter App (Sub-project 3-native) — Design Spec

- **Date:** 2026-10-11
- **Project:** Ubuzima SRHR Digital Navigator — the native (Android/iOS, Flutter) end-user app.
- **Builds on:** the existing backend (sub-projects 1 & 2). Reuses the exact HTTP API already consumed by the web frontend. Backend base URL via `--dart-define=API_BASE=...` (default `http://127.0.0.1:8099`). No backend change.
- **Goal:** a real Flutter app (one codebase, Android/iOS-ready) giving the youth end-user experience: onboarding, chat (text + streaming), turn-based voice, EN/RW, light/dark, settings/wipe — mirroring the web app's end-user surface with the same safety-first rendering. Verified with `flutter test` + `flutter analyze` + `flutter build web` (the web build is also browser-openable for quick testing; native Android/iOS builds use the same codebase).

## 1. Intent & confirmed decisions
- **Scope:** end-user app ONLY (admin stays the web panel). Features: onboarding, chat (text + SSE streaming), turn-based voice (record → /v1/voice/chat → play reply), settings (theme, language, edit profile, wipe), EN/RW, light/dark.
- **Out of scope (later phases):** live full-duplex WebRTC voice (needs flutter_webrtc + the backend realtime extra), offline sync + nearby facilities (sub-project 4), push/SMS/USSD. Leave seams.
- **Stack:** Flutter 3.41 (stable), Dart; **Riverpod** for state; `dio` for HTTP (+ streamed responses for SSE); `record` for mic capture, `just_audio` (or `audioplayers`) for playback; `flutter_secure_storage` for tokens (+ `shared_preferences` for non-secret prefs). Material 3.
- **Design:** warm "buddy" — rounded cards, warm coral + teal accent, friendly type, playful-but-calm motion (respect platform reduce-motion), **no gradients**, light + dark (follows system, user-togglable). Crisis/referral rendered calm & supportive, never an error/alarming treatment — mirroring the web app.
- **Safety parity:** the app NEVER renders anything but the backend's guarded answer; crisis/referral/out-of-knowledge get calm supportive treatment; sensitive-context onboarding is optional, skip doesn't save typed text, wipe truly clears local identity (clear tokens + anon id, re-bootstrap).

## 2. Architecture
```
app_flutter/            # Flutter project
  lib/
    main.dart
    core/
      config.dart       # API_BASE from dart-define
      theme.dart        # warm buddy ThemeData light+dark, no gradients
      i18n/             # en/rw ARB or a simple map + a T() lookup; language provider
      result.dart       # typed error (ApiError{code,message,status}; 'offline')
    data/
      api_client.dart   # dio wrapper: base url, bearer, single-flight refresh on 401, error-envelope -> ApiError, offline mapping
      token_store.dart  # secure storage for user token pair + anon_id (+ clear)
      sse.dart          # parse event: delta/done/error from a streamed response
      endpoints/        # identity, profile, chat, voice (typed models + calls)
      models/           # Profile, ChatResponse, SafetyFlags, VoiceResponse, Citation
    state/              # Riverpod providers: authProvider (ensureAnon/role n/a), profileProvider, chatController, voiceController, settings (theme/lang)
    features/
      onboarding/       # wizard: nickname+lang, age/pronouns, interests/tone, optional sensitive (skippable, privacy note)
      chat/             # message list, bubbles, citation chips, crisis/referral callouts, composer, streaming + typing indicator
      voice/            # record button, transcript+answer (reuse chat bubble rendering), play reply when tts_available, "live coming soon"
      settings/         # theme, language, edit profile, re-run onboarding, wipe (confirm)
      shell/            # nav scaffold (Chat / Settings), header toggles
  test/                 # widget + unit tests (mocked api)
  pubspec.yaml          # pinned deps
```

## 3. End-user flows (same endpoints as web)
- **Onboarding:** `POST /v1/identity/anon` (store tokens + anon_id securely) → collect optional profile → `PUT /v1/profile` (only provided fields; sensitive_context only when entered; skip drops it). "Onboarded" flag in prefs; re-entrant from settings.
- **Chat:** `POST /v1/chat/stream` (SSE `event: delta`/`done`/`error`) with a non-stream `POST /v1/chat` fallback; render user/assistant bubbles, citation chips, calm referral/out-of-knowledge callouts, calm crisis panel; typing indicator; conversation_id continuity.
- **Voice (turn-based):** record (mic permission handled gracefully) → `POST /v1/voice/chat` (multipart) → show transcript + answer via the SAME bubble/callout rendering; play `audio_base64` when `tts_available`, else text; "Live mode coming soon" placeholder.
- **Settings:** theme toggle, language toggle, edit profile (`PUT`), re-run onboarding, wipe (`DELETE /v1/profile` + clear local tokens/anon_id + re-bootstrap) behind a confirm.

## 4. Cross-cutting
- **Auth:** anonymous-first; secure token storage; single-flight refresh on 401; a transient refresh failure keeps tokens (only a definitive 401/403 clears); offline surfaced calmly.
- **i18n:** EN + RW, user-togglable, persisted; follow device locale by default.
- **Theming:** light/dark follow system + override; warm palette; no gradients; honor platform text-scale/reduce-motion; AA contrast.
- **Accessibility:** semantic labels, large tap targets, screen-reader-friendly chat log, focus order.
- **Privacy/security:** tokens in secure storage; never log tokens/transcripts/message content; sensitive-context optional + wipe.
- **Errors:** backend error envelope → friendly in-app messages; 503 (provider/realtime) → calm "service unavailable, try later"; crisis NEVER shown as an error.

## 5. Testing & verification
- `flutter test`: unit (api_client refresh/error/offline, sse parser, token_store, profile payload only-changed, i18n) + widget (onboarding submits expected payload; chat bubble renders crisis/referral calm + citations; voice renders transcript+answer and gates audio on tts_available; settings wipe clears local identity).
- `flutter analyze` clean (no errors; warnings addressed).
- `flutter build web` succeeds (CI/demo + browser-openable); codebase stays Android/iOS-buildable (`flutter build apk` when SDK licenses are accepted — documented, not required in CI here).
- No real device/emulator needed for the above; real-device runs are a manual follow-up.

## 6. Out of scope / later
Live full-duplex WebRTC (flutter_webrtc) — phase 2, on the existing backend `/v1/live`; offline + nearby facilities — sub-project 4; push/SMS/USSD; the admin panel (stays web). Interfaces/placeholders left so these slot in.

## 7. Run / deliverable
`cd app_flutter && flutter pub get && flutter run -d chrome --dart-define=API_BASE=http://127.0.0.1:8099` (or `flutter build web`). The controller will build web and serve it so the Flutter app is testable in a browser against the running backend; native builds use the same codebase.
