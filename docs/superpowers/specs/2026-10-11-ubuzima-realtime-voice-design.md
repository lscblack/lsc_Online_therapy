# Ubuzima — Realtime Full-Duplex Voice (Sub-project 2) — Design Spec

- **Date:** 2026-10-11
- **Project:** Ubuzima SRHR Digital Navigator — realtime "live" voice mode.
- **Builds on:** Sub-project 1 (Backend + RAG Core) — reuses `ChatService.respond()` (triage → retrieve → guard → referral), the provider abstraction, safety module, identity/JWT, and models. Nothing in sub-project 1 changes except additive extension points noted below.

## 1. Purpose & Intent (agreed)

A real-time, interruptible voice conversation — talking to the agent as if to a person — over **WebRTC**, with **true streaming STT** where the language supports it, **full barge-in** (the user can interrupt the agent mid-sentence), and the **same safety guarantees** as text/turn-based voice: every spoken reply is the guarded `ChatService` answer, crises always bypass to a referral, nothing ungrounded is voiced.

### Confirmed decisions
- **Transport:** WebRTC (server-terminated).
- **STT:** true streaming provider where available; see the Kinyarwanda reconciliation (§6).
- **Scope:** full barge-in from the start.
- **Safety:** guard the full answer **before any audio is synthesized/streamed** (never sentence-stream raw model output).

### Key risks flagged for review
- **R1 — Kinyarwanda streaming gap:** no production streaming STT supports Kinyarwanda today. Reconciliation: a `StreamingSTTProvider` abstraction with two strategies — word-level streaming for supported languages (English via e.g. Deepgram), and a **VAD-segmented near-real-time** path for Kinyarwanda (existing batch STT / Digital Umuganda per utterance). Same WebRTC session; strategy chosen by session language. This preserves KR at slightly higher per-utterance latency. **Please confirm this reconciliation.**
- **R2 — TURN infrastructure:** reliable WebRTC on Rwandan mobile networks needs a TURN relay (coturn) plus STUN; this is an ops/deploy dependency and a per-session cost. The spec includes config + a self-hosted coturn in compose, but running/securing it is an operational commitment.
- **R3 — guard-before-audio vs latency:** guarding the whole answer before speaking adds one full generate+guard round per turn before TTS starts. Acceptable and required for this content; barge-in keeps it feeling responsive.

## 2. Architecture

A new `app/realtime/` package plus a signaling endpoint; the media path is terminated in Python with **aiortc**.

```
app/realtime/
  signaling.py      # SDP offer/answer + ICE exchange (over the existing API, JWT-authed)
  session.py        # LiveSession: per-connection state machine + orchestration
  media.py          # aiortc tracks: inbound audio sink, outbound TTS source
  vad.py            # server-side voice-activity detection (barge-in + endpointing)
  turn.py           # ICE server config (STUN/TURN) from settings
app/providers/
  streaming_stt.py  # StreamingSTTProvider protocol + impls (streaming + VAD-segmented)
```

Reused unchanged: `ChatService.respond()` (the single guarded entry point), `safety/*`, `providers/factory` (LLM/TTS/STT), `rag/*`, identity/RBAC, models.

### Session state machine (per LiveSession)
`IDLE → LISTENING → (endpoint detected) → THINKING → SPEAKING → LISTENING …`
- **LISTENING:** inbound audio → VAD → streaming partial transcripts (or buffered for the KR segmented path).
- **THINKING:** on utterance end, final transcript → `ChatService.respond(mode="voice")` (full triage+retrieve+guard). No audio yet.
- **SPEAKING:** stream TTS of the guarded answer onto the outbound track.
- **Barge-in:** VAD detects user speech while SPEAKING → **cancel** the outbound TTS + any in-flight generation task, flush the output track, return to LISTENING, begin the new utterance. Crisis answers are allowed to finish a short mandatory referral line even on barge-in (configurable) so a safety message isn't lost.

## 3. Signaling & Transport
- `POST /v1/live/offer` (JWT-authed): client sends SDP offer + chosen `language`; server creates an aiortc `RTCPeerConnection`, attaches the inbound sink + outbound TTS track, returns the SDP answer. Trickle ICE via `POST /v1/live/ice` or within the WS. (The reserved `/v1/live` WS from sub-project 1 becomes the control/events channel: state changes, partial transcripts, citations, safety flags, barge-in events — JSON.)
- ICE servers (STUN + TURN) delivered to the client from settings (`turn.py`), credentials short-lived.
- One `RTCPeerConnection` per session; audio is Opus; server decodes to PCM for VAD/STT and encodes TTS PCM→Opus outbound.

## 4. Media & VAD
- Inbound: aiortc audio track → resample → **VAD** (silero-vad preferred; webrtcvad fallback) for speech start/stop (endpointing) and for barge-in detection during SPEAKING.
- Outbound: a pull-based audio track fed by the TTS byte stream (chunked), cancellable mid-stream.
- Latency budget (target, 5G): endpoint→first-audio ≈ STT-final + generate + guard + TTS-first-chunk; instrument each stage and emit timings on the control channel for tuning.

## 5. Pipeline per utterance (safety-first)
1. LISTENING: stream audio → partials (control channel shows live text).
2. Endpoint (VAD silence > threshold) → final transcript.
3. THINKING: `ChatService.respond(user, transcript, conversation_id, language, mode="voice")` — this runs triage (crisis bypass), retrieval, grounding guard, referral enforcement. **No audio is produced until respond() returns a guarded answer.**
4. SPEAKING: strip citation markers, stream TTS of the guarded answer. Crisis → the crisis+referral copy is spoken (as in sub-project 1).
5. Barge-in at any point in 4 cancels and loops to LISTENING.

Because step 3 is the existing guarded entry point, **all sub-project 1 safety guarantees hold unchanged** in realtime.

## 6. Streaming STT abstraction (R1 reconciliation)
`app/providers/streaming_stt.py`:
- `StreamingSTTProvider` protocol: `async stream(audio_frames) -> AsyncIterator[Partial|Final]` with `.is_final`, `.text`, `.language`.
- **`StreamingWhisperDeepgram`-style impl** (or chosen vendor) for languages with streaming support (English) → word-level partials.
- **`VadSegmentedSTT`** adapter: wraps the existing batch `STTProvider` (Whisper / `DigitalUmugandaSTT`); uses `vad.py` to cut utterances and transcribes each segment → emits a single Final per utterance (no word partials). Used for Kinyarwanda and any language without a streaming vendor.
- `factory.get_streaming_stt(language)` selects the strategy by language + settings. Fakes for tests.

## 7. Config & Infra (additive)
- Settings: `ICE_SERVERS`/STUN URL, `TURN_URL`/`TURN_SECRET` (short-lived HMAC credentials), `STREAMING_STT_PROVIDER`, `VAD_*` thresholds, barge-in + endpoint timeouts, `REALTIME_MAX_SESSION_SECONDS`, max concurrent sessions.
- `docker-compose`: add **coturn** (TURN/STUN) service; document securing it. aiortc + silero-vad added to deps (note: aiortc needs ffmpeg/libopus — already have ffmpeg).
- Auth/limits: signaling is JWT-authed (reuse identity); per-identity concurrent-session cap; reuse/extend rate limiting; session idle/no-audio timeout; profile personalization reused.

## 8. Testing
- Unit: VAD endpointing + barge-in trigger logic; session state-machine transitions (listening→thinking→speaking→barge-in) with fakes; streaming-STT strategy selection by language; TTS track cancellation on barge-in; citation stripping.
- Integration (fakes, no real media): a driven LiveSession where a fake inbound stream yields a transcript → asserts `ChatService.respond()` is the sole answer path, the guarded answer is what reaches the (fake) TTS track, a crisis utterance bypasses retrieval and still speaks a referral, and a barge-in event cancels in-flight TTS.
- Safety red-team through the realtime path: crisis/sensitive utterances → guarded/referral spoken; never an unguarded partial.
- aiortc/coturn wiring validated by a thin smoke (offer→answer handshake) marked integration.

## 9. Out of scope
- The Flutter client side of WebRTC (sub-project 3). Production TURN hardening/scaling. Real Kinyarwanda streaming STT model training. Multi-party. Telephony/PSTN.

## 10. Open items for your review
- Confirm **R1** hybrid STT (streaming EN + VAD-segmented KR) is acceptable, or whether KR-only-VAD / English-first is preferred.
- Confirm committing to **TURN/coturn** ops (R2), or defer realtime to networks where STUN-only suffices (then flag reliability).
- Pick the streaming STT vendor for English (Deepgram is the common choice) — or keep it behind the interface and decide at build time.
