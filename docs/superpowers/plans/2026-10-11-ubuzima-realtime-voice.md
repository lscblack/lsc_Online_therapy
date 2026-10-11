# Ubuzima Realtime Full-Duplex Voice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A WebRTC, server-terminated, interruptible ("barge-in") live voice conversation whose every spoken reply is the guarded `ChatService.respond()` answer — same safety guarantees as the existing text/turn-based voice.

**Architecture:** New `app/realtime/` package (signaling, LiveSession state machine, aiortc media tracks, server-side VAD) + a `StreamingSTTProvider` abstraction (word-level streaming for English, VAD-segmented near-real-time for Kinyarwanda). The answer path is unchanged: utterance → final transcript → `ChatService.respond(mode="voice")` → guard → stream TTS. aiortc terminates media in Python.

**Tech Stack:** Python 3.13, FastAPI, aiortc, silero-vad (webrtcvad fallback), the existing providers/safety/chat, coturn (TURN/STUN), pytest + fakes.

**Spec:** `docs/superpowers/specs/2026-10-11-ubuzima-realtime-voice-design.md`

## Global Constraints

- `ChatService.respond(mode="voice")` is the SOLE path that produces a spoken answer; no realtime code generates or voices text another way. Guard the full answer BEFORE any TTS audio is produced. Crisis bypass and all sub-project 1 safety guarantees must hold unchanged.
- WebRTC via **aiortc**, server-terminated, one `RTCPeerConnection` per session; audio Opus.
- Streaming STT via `StreamingSTTProvider`, selected by session language: streaming impl for English; **VAD-segmented** path (wrapping the existing batch `STTProvider`/`DigitalUmugandaSTT`) for Kinyarwanda and any language without a streaming vendor. English vendor stays behind the interface (Deepgram default).
- Signaling is JWT-authed (reuse `current_user`); per-identity concurrent-session cap; idle/no-audio + max-duration session timeouts.
- Async end-to-end; layering `app/realtime → (services|providers|safety) → core`; realtime imports nothing from `api` except its own router. Fakes for all unit/integration tests; real aiortc/coturn media behind `@pytest.mark.integration`.
- Additive only: do not change sub-project 1 behavior; the reserved `/v1/live` WS becomes the control channel.
- TDD: test first, RED, implement, GREEN, full suite once, commit (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

## Review Focus

- **Barge-in during a crisis/referral answer** → the mandatory referral line is not silently lost (configurable: let the short safety line finish). (Task 4)
- **ICE/connection drop or client disconnect mid-session** → the peer connection, media tracks, VAD, STT stream, and any in-flight generation task are all torn down; no leaked tasks/sessions. (Tasks 4, 5)
- **Kinyarwanda session** → routes to the VAD-segmented STT path, never the English-only streaming vendor. (Task 1)
- **Unauthed/expired JWT on `/v1/live/offer`** → rejected (401) with NO `RTCPeerConnection` created. (Task 5)
- **Concurrent-session cap / session timeout exceeded** → new session refused (429/explicit close) and stale sessions reaped; no unbounded resource growth. (Tasks 5, 6)

---

### Task 1: Streaming STT abstraction + VAD

**Files:**
- Create: `app/providers/streaming_stt.py`, `app/realtime/__init__.py`, `app/realtime/vad.py`, `tests/realtime/test_streaming_stt.py`, `tests/realtime/test_vad.py`
- Modify: `app/providers/factory.py` (add `get_streaming_stt(language)`), `app/core/config.py` (streaming/VAD settings)

**Interfaces:**
- Consumes: existing `STTProvider` / `factory.get_stt`, `core.i18n.recognised_language`.
- Produces: `StreamingSTTProvider` protocol `async stream(frames: AsyncIterator[bytes], language) -> AsyncIterator[STTEvent]` (`STTEvent(text, is_final, language)`); `VadSegmentedSTT` (wraps batch STT, emits one Final per utterance via VAD); a streaming vendor impl `StreamingVendorSTT` (behind the interface; Deepgram-style, not called in unit tests); `FakeStreamingSTT`; `factory.get_streaming_stt(language)`; `vad.detect(frames) -> AsyncIterator[VadEvent]` (`speech_start`/`speech_end`) + `vad.is_speech(frame)`.

- [ ] **Step 1:** Write `test_streaming_stt.py`: `test_factory_selects_vad_segmented_for_kinyarwanda` and `test_factory_selects_streaming_for_english` *(Review Focus: KR routing)*; `test_vad_segmented_emits_final_per_utterance` (fake batch STT + scripted VAD). `test_vad.py`: endpointing (speech_start/end on silence threshold) and `is_speech` on scripted frames.
- [ ] **Step 2:** Run `pytest tests/realtime/test_streaming_stt.py tests/realtime/test_vad.py -v` → FAIL.
- [ ] **Step 3:** Implement protocol, `VadSegmentedSTT`, the vendor impl (real calls guarded/integration), fakes, factory selector (by `recognised_language`), and `vad.py` (silero-vad; webrtcvad fallback; lazy model load behind a lock like e5).
- [ ] **Step 4:** Run the two test files → PASS (`-m "not integration"`).
- [ ] **Step 5:** Commit.

---

### Task 2: ICE/TURN config + coturn

**Files:**
- Create: `app/realtime/turn.py`, `tests/realtime/test_turn.py`
- Modify: `docker-compose.yml` (add `coturn`), `app/core/config.py` (ICE/TURN settings), `README.md` (realtime infra note)

**Interfaces:**
- Produces: `turn.get_ice_servers() -> list[dict]` (STUN always; TURN with short-lived HMAC `username`/`credential` when `TURN_SECRET` set, per coturn's REST ephemeral-credential scheme).

- [ ] **Step 1:** Write `test_turn.py`: `test_ice_servers_stun_only_when_no_turn_secret`; `test_turn_credentials_are_time_limited_hmac` (username is `<expiry>:<id>`, credential = base64 HMAC-SHA1 over username with the secret; expiry honors `TURN_TTL`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `turn.py`; add coturn service to compose (ports, realm, `use-auth-secret`), settings (`STUN_URL`, `TURN_URL`, `TURN_SECRET`, `TURN_TTL`), README note on securing coturn.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 3: Media tracks (inbound sink, cancellable outbound TTS)

**Files:**
- Create: `app/realtime/media.py`, `tests/realtime/test_media.py`

**Interfaces:**
- Consumes: aiortc `MediaStreamTrack`; `factory.get_tts`.
- Produces: `InboundAudio` (consumes an aiortc track → yields resampled PCM frames to the session); `TtsTrack(MediaStreamTrack)` — an outbound source fed by a TTS byte/chunk stream, with `play(chunks)` and `cancel()` that immediately stops output (for barge-in) and drains cleanly; a `frames_to_pcm`/resample helper.

- [ ] **Step 1:** Write `test_media.py` (no real network): `test_tts_track_emits_fed_chunks`; `test_tts_track_cancel_stops_output_promptly` *(Review Focus: barge-in teardown)*; `test_inbound_yields_pcm_frames` (fake track). Use fakes for aiortc frame objects.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement the tracks + resampling; `cancel()` sets a flag + unblocks `recv()` so aiortc stops pulling.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 4: LiveSession state machine + orchestration + barge-in

**Files:**
- Create: `app/realtime/session.py`, `tests/realtime/test_session.py`

**Interfaces:**
- Consumes: Task 1 (`get_streaming_stt`, `vad`), Task 3 (`InboundAudio`, `TtsTrack`), `ChatService.respond(mode="voice")`, `safety` copy, profile.
- Produces: `LiveSession(user, language, session, llm=None, ...)` with `state` (`IDLE/LISTENING/THINKING/SPEAKING`), `feed(frames)`, an event stream (state changes, partial transcripts, citations, safety_flags, barge-in), `on_utterance_final(text)` → calls `ChatService.respond()` → streams the guarded answer to the `TtsTrack`, and `barge_in()` cancelling in-flight generation + TTS. Exposes `close()` for teardown.

- [ ] **Step 1:** Write `test_session.py` (fakes for STT/VAD/TTS/LLM; real `ChatService`):
  - `test_utterance_goes_through_chatservice_and_speaks_guarded_answer` (the TTS track receives exactly the guarded answer; respond() is the only answer source).
  - `test_crisis_utterance_bypasses_rag_and_speaks_referral` (no retrieval; referral present).
  - `test_barge_in_cancels_inflight_tts_and_generation` → returns to LISTENING *(Review Focus)*.
  - `test_barge_in_during_crisis_keeps_referral_line` (configurable mandatory safety line not dropped) *(Review Focus)*.
  - `test_close_tears_down_stt_tts_and_tasks` (no leaked tasks) *(Review Focus: teardown)*.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement the state machine + orchestration; cancellation via `asyncio.Task.cancel()` on barge-in; guard-before-audio (await respond() fully before feeding the TtsTrack); emit control events.
- [ ] **Step 4:** Run `pytest tests/realtime/test_session.py -v` → PASS.
- [ ] **Step 5:** Commit.

---

### Task 5: Signaling endpoints + control WS

**Files:**
- Create: `app/realtime/signaling.py`, `tests/realtime/test_signaling.py`
- Modify: `app/api/v1/live.py` (replace the stub: control WS + mount signaling), `app/main.py` if needed

**Interfaces:**
- Consumes: Task 4 `LiveSession`, Task 2 `get_ice_servers`, Task 3 tracks, `current_user`, aiortc `RTCPeerConnection`.
- Produces: `POST /v1/live/offer` (JWT; body: SDP offer + `language`; creates `RTCPeerConnection`, wires inbound→LiveSession and LiveSession→TtsTrack, returns SDP answer + ICE servers); `POST /v1/live/ice` (trickle); `WS /v1/live` control channel (JSON events from the session; client can send `barge_in`/`end`); a session registry with a per-identity concurrent cap.

- [ ] **Step 1:** Write `test_signaling.py`: `test_offer_requires_auth` (no/expired JWT → 401, NO peer connection created) *(Review Focus)*; `test_offer_over_cap_refused` (per-identity cap → 429) *(Review Focus)*; `test_control_ws_streams_session_events` (a driven session emits state/partials over the WS); `test_disconnect_closes_session` (client drop → `LiveSession.close()` called, registry entry removed) *(Review Focus: teardown)*. Mock aiortc's `RTCPeerConnection` so no real media runs.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement signaling + control WS + session registry/cap; ensure auth check precedes peer-connection creation; wire teardown on disconnect/ICE-failure.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

---

### Task 6: Wiring, limits, deps, docs, smoke

**Files:**
- Create: `tests/realtime/test_realtime_wiring.py`
- Modify: `app/core/config.py` (session caps/timeouts), `pyproject.toml` (aiortc, silero-vad), `app/main.py` (session reaper in lifespan), `README.md`, `docker-compose.yml`

**Interfaces:**
- Consumes: all realtime modules.
- Produces: a background reaper that closes idle/over-max-duration sessions; settings `REALTIME_MAX_SESSION_SECONDS`, `REALTIME_IDLE_SECONDS`, `REALTIME_MAX_SESSIONS_PER_USER`; README "Live voice" section (TURN, client flow, limits).

- [ ] **Step 1:** Write `test_realtime_wiring.py`: `test_routes_registered` (offer/ice/live WS in OpenAPI/app); `test_idle_session_reaped` (a session past its idle deadline is closed by the reaper) *(Review Focus)*; `test_session_timeout_enforced`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement reaper + settings; declare deps; README; ensure aiortc import is optional-safe so the rest of the app still boots if aiortc is missing (log + disable realtime) — realtime deps are heavy.
- [ ] **Step 4:** Run full suite `pytest -m "not integration" -v` → PASS; document an optional `@pytest.mark.integration` offer→answer handshake smoke.
- [ ] **Step 5:** Commit.

---

## Notes for executors
- Keep aiortc/coturn out of the default (fakes-only) test path; real handshake is integration-marked.
- Reuse `ChatService`, `safety`, `providers`, identity unchanged — this sub-project is additive.
- The Flutter WebRTC client is sub-project 3; this plan delivers only the server side + a documented client contract (SDP/ICE/control-WS event shapes).
