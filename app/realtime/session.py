"""LiveSession: the realtime-voice state machine.

    IDLE -> LISTENING -> (final transcript) -> THINKING -> SPEAKING -> LISTENING ...

Safety contract (inherited, never re-implemented here):
  * The ONLY source of spoken text is `ChatService.respond(..., mode="voice")`. Triage, crisis
    bypass, grounding guard and referrals all happen inside it.
  * Guard-before-audio: respond() is awaited to completion before anything is synthesized or
    handed to the TTS track.
  * Barge-in (user speech while SPEAKING) cancels TTS + generation and returns to LISTENING,
    except that a CRISIS answer is protected for `crisis_min_play_ms` so the mandatory
    referral line is never silently dropped by an immediate interruption.

Control events (JSON-able dicts, via `events()`; the stream ends after close()):
  {"type": "state", "state": "idle|listening|thinking|speaking"}
  {"type": "transcript_partial", "text": str}
  {"type": "transcript_final", "text": str}
  {"type": "answer", "text": str, "language": str, "conversation_id": str}   # guarded text
  {"type": "citations", "citations": [...]}
  {"type": "safety_flags", "safety_flags": {...}}
  {"type": "barge_in"}
  {"type": "error", "code": str}
"""
import asyncio
import contextlib
import enum
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.core.config import get_settings
from app.core.i18n import normalize_language
from app.models import User
from app.services.chat import ChatService
from app.services.voice import strip_citations  # same stripping as turn-based voice

logger = logging.getLogger(__name__)


class State(str, enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


_FRAME_MS = 20


class LiveSession:
    def __init__(
        self,
        user: User,
        language: str | None,
        session: Any,
        *,
        llm: Any = None,
        stt: Any = None,
        tts: Any = None,
        tts_track: Any = None,
        chat: ChatService | None = None,
        voice: str | None = None,  # TTS voice name
        vad: Any = None,
        inbound: Any = None,  # InboundAudio (stop() on close)
        conversation_id: uuid.UUID | None = None,
        barge_in_grace_ms: int | None = None,
        barge_in_min_speech_ms: int | None = None,
        crisis_min_play_ms: int | None = None,
        playback_poll_s: float = 0.02,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        s = get_settings()
        self.user = user
        self.language = normalize_language(language)
        self.conversation_id: uuid.UUID | None = conversation_id
        self.state = State.IDLE
        self._session = session
        self._chat = chat or ChatService(session, llm=llm)
        self._stt = stt
        self._tts = tts
        self._track = tts_track
        self._voice = voice
        self._vad = vad
        self._inbound = inbound
        self._grace_ms = s.realtime_barge_in_grace_ms if barge_in_grace_ms is None else barge_in_grace_ms
        self._min_speech_ms = (s.realtime_barge_in_min_speech_ms if barge_in_min_speech_ms is None
                               else barge_in_min_speech_ms)
        self._crisis_ms = s.realtime_crisis_min_play_ms if crisis_min_play_ms is None else crisis_min_play_ms
        self._poll = playback_poll_s
        self._clock = clock

        self._events: asyncio.Queue = asyncio.Queue()
        self._in_q: asyncio.Queue = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._stt_task: asyncio.Task | None = None
        self._turn: asyncio.Task | None = None
        self._turn_gen = 0
        self._speak_start = 0.0
        self._speech_ms = 0
        self._respond_done = False  # current turn: guarded result is in hand
        self._turn_crisis = False  # current turn: result is a crisis answer (protected)
        self._interrupting = False
        self._pending: list[str] = []  # finals waiting to supersede the active turn
        self._sup: asyncio.Task | None = None
        self._closing: asyncio.Task | None = None
        self._started = False
        self._closed = asyncio.Event()

    # ------------------------------------------------------------- public
    async def events(self) -> AsyncIterator[dict]:
        while True:
            e = await self._events.get()
            if e is None:
                return
            yield e

    async def feed(self, frames: AsyncIterator[bytes]) -> None:
        """Drive the session from PCM16/16k/20ms frames until they end or close() is called.
        On a natural end of input, in-flight STT finals and the current turn are completed."""
        if self._closed.is_set():
            return
        self._start()
        it = frames.__aiter__()
        closed_wait = self._spawn(self._closed.wait())
        nxt: asyncio.Future | None = None
        try:
            while not self._closed.is_set():
                nxt = asyncio.ensure_future(it.__anext__())
                await asyncio.wait({nxt, closed_wait}, return_when=asyncio.FIRST_COMPLETED)
                if not nxt.done():
                    break
                try:
                    frame = nxt.result()
                except StopAsyncIteration:
                    break
                nxt = None
                await self._on_frame(frame)
        finally:
            if nxt is not None and not nxt.done():
                nxt.cancel()
            closed_wait.cancel()
            await asyncio.gather(*(f for f in (nxt, closed_wait) if f is not None),
                                 return_exceptions=True)
            aclose = getattr(it, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()
        if self._closed.is_set():
            return
        self._in_q.put_nowait(None)  # end of audio: let STT flush its final(s)
        if self._stt_task is not None:
            await asyncio.wait({self._stt_task})
        while not self._closed.is_set():
            live = {t for t in (self._sup, self._turn) if t is not None and not t.done()}
            if not live:
                break
            await asyncio.wait(live, timeout=0.1)

    async def close(self) -> None:
        """Idempotent teardown (STT stream, TTS track, inbound, VAD, all tasks). Concurrent
        callers all wait for the same teardown to finish."""
        if self._closing is None:
            self._closing = asyncio.ensure_future(self._do_close())
        await asyncio.shield(self._closing)

    async def _do_close(self) -> None:
        self._closed.set()
        if self._track is not None:
            with contextlib.suppress(Exception):
                self._track.cancel()
        tasks = [t for t in self._tasks if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._in_q.put_nowait(None)
        if self._inbound is not None and hasattr(self._inbound, "stop"):
            with contextlib.suppress(Exception):
                self._inbound.stop()
        if self._track is not None and hasattr(self._track, "stop"):
            with contextlib.suppress(Exception):
                self._track.stop()
        close_vad = getattr(self._vad, "close", None)
        if close_vad is not None:
            with contextlib.suppress(Exception):
                close_vad()
        self._set_state(State.IDLE)
        self._events.put_nowait(None)

    # ------------------------------------------------------------ plumbing
    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _emit(self, **event: Any) -> None:
        if not self._closed.is_set() or event.get("type") == "state":
            self._events.put_nowait(event)

    def _set_state(self, state: State) -> None:
        if state != self.state:
            self.state = state
            self._emit(type="state", state=state.value)

    def _lazy(self) -> None:
        if self._stt is None:
            from app.providers.factory import get_streaming_stt
            self._stt = get_streaming_stt(self.language)
        if self._tts is None:
            from app.providers.factory import get_tts
            self._tts = get_tts()
        if self._track is None:
            from app.realtime.media import TtsTrack
            self._track = TtsTrack()
        if self._vad is None:
            from app.realtime.vad import make_backend
            self._vad = make_backend()

    def _start(self) -> None:
        if self._started:
            return
        self._started = True
        self._lazy()
        self._set_state(State.LISTENING)
        self._stt_task = self._spawn(self._stt_loop())

    async def _frame_iter(self) -> AsyncIterator[bytes]:
        while True:
            f = await self._in_q.get()
            if f is None:
                return
            yield f

    async def _stt_loop(self) -> None:
        agen = self._stt.stream(self._frame_iter(), self.language)
        try:
            async for ev in agen:
                text = (ev.text or "").strip()
                if not text:
                    continue
                if not ev.is_final:
                    self._emit(type="transcript_partial", text=text)
                else:
                    self._emit(type="transcript_final", text=text)
                    await self._on_final(text)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("streaming STT failed (%s)", type(e).__name__)
            self._emit(type="error", code="stt_failed")
        finally:
            aclose = getattr(agen, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

    # --------------------------------------------------------- barge-in
    def _barge_allowed(self) -> bool:
        elapsed_ms = (self._clock() - self._speak_start) * 1000
        if elapsed_ms < self._grace_ms:
            return False
        return not (self._turn_crisis and elapsed_ms < self._crisis_ms)

    async def _on_frame(self, frame: bytes) -> None:
        self._in_q.put_nowait(frame)
        if self.state != State.SPEAKING:
            self._speech_ms = 0
            return
        vad = self._vad
        if getattr(vad, "blocking", False):
            speech = await asyncio.to_thread(vad.is_speech, frame)
        else:
            speech = vad.is_speech(frame)
        self._speech_ms = self._speech_ms + _FRAME_MS if speech else 0
        if self._speech_ms >= self._min_speech_ms and self._barge_allowed():
            await self._interrupt()

    async def barge_in(self) -> None:
        """Client-requested interrupt (control channel). Honors the crisis-line protection."""
        if self._closed.is_set() or self.state not in (State.SPEAKING, State.THINKING):
            return
        # Same rule as _interruptible(): a crisis turn is protected from respond() until it has
        # been SPEAKING for crisis_min_play_ms (_speak_start is stale before SPEAKING).
        if self._turn_crisis and not (self.state == State.SPEAKING and self._barge_allowed()):
            return
        await self._interrupt()

    async def _interrupt(self, to_listening: bool = True) -> None:
        """Cancel TTS + in-flight generation. One barge-in = one event."""
        if self._interrupting:
            return
        self._interrupting = True
        try:
            was_speaking = self.state == State.SPEAKING
            mid_respond = not self._respond_done
            if self._track is not None:
                self._track.cancel()
            turn, self._turn = self._turn, None
            self._turn_gen += 1
            if turn is not None and not turn.done():
                turn.cancel()
                await asyncio.wait({turn})
                if mid_respond:
                    await self._rollback()  # respond() may have died mid-query
            self._speech_ms = 0
            self._respond_done = self._turn_crisis = False
            if to_listening:
                self._set_state(State.LISTENING)
            if was_speaking:
                self._emit(type="barge_in")
        finally:
            self._interrupting = False

    async def _rollback(self) -> None:
        try:
            await self._session.rollback()
        except Exception as e:  # noqa: BLE001
            logger.error("session rollback failed (%s)", type(e).__name__)

    @staticmethod
    def _substantive(text: str) -> bool:
        return len(text.split()) >= 2 or len(text) >= 6

    def _interruptible(self) -> bool:
        """May the active turn be superseded now? A turn is never cancelled before its guarded
        result exists (a crisis result can't be recognised earlier), and a crisis answer is
        protected from respond() until it has played crisis_min_play_ms."""
        turn = self._turn
        if turn is None or turn.done():
            return True
        if not self._respond_done:
            return False
        if self._turn_crisis:
            return self.state == State.SPEAKING and self._barge_allowed()
        return True

    async def _on_final(self, text: str) -> None:
        turn = self._turn
        if self._sup is not None and not self._sup.done():
            # A supersede is in flight (possibly mid-cancel, when self._turn is None):
            # it alone starts the next turn, so there is never more than one.
            self._pending.append(text)
            return
        if turn is None or turn.done():
            self._start_turn(text)
            return
        if self.state == State.SPEAKING and not self._turn_crisis:
            # Same gating as the VAD path: echo/noise transcripts must not self-interrupt.
            if not self._substantive(text) or not self._barge_allowed():
                return
        self._pending.append(text)
        if self._sup is None or self._sup.done():
            self._sup = self._spawn(self._supersede())

    async def _supersede(self) -> None:
        while not self._interruptible():
            await asyncio.sleep(self._poll)
        if self._turn is not None and not self._turn.done():
            await self._interrupt(to_listening=False)  # next turn sets THINKING: no flicker
        if self._pending and not self._closed.is_set():
            text, self._pending = " ".join(self._pending), []
            self._start_turn(text)
        elif self.state != State.LISTENING:
            self._set_state(State.LISTENING)

    def _start_turn(self, text: str) -> None:
        old = self._turn
        if old is not None and not old.done():  # safety net: exactly one live turn
            self._track.cancel()
            old.cancel()
        self._turn_gen += 1
        self._respond_done = self._turn_crisis = False
        self._turn = self._spawn(self._run_turn(text, self._turn_gen))

    # ------------------------------------------------------------- a turn
    async def _run_turn(self, text: str, gen: int) -> None:
        self._set_state(State.THINKING)
        try:
            # Guard-before-audio: the full guarded result exists before any synth/playback.
            result = await self._chat.respond(self.user, text, self.conversation_id,
                                              self.language, mode="voice")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("respond failed (%s)", type(e).__name__)
            self._emit(type="error", code="respond_failed")
            self._finish(gen)
            return
        if gen != self._turn_gen:  # superseded: nothing from this turn may leak out
            return
        self.conversation_id = result.conversation_id
        # Mark protection BEFORE synth so a new final can't cancel a crisis referral.
        self._turn_crisis = bool(result.safety_flags.get("crisis"))
        self._respond_done = True
        self._emit(type="answer", text=result.answer, language=result.language,
                   conversation_id=str(result.conversation_id))
        self._emit(type="citations", citations=result.citations)
        self._emit(type="safety_flags", safety_flags=result.safety_flags)
        spoken = strip_citations(result.answer)
        if not spoken:
            self._finish(gen)
            return
        try:
            audio = await self._tts.synthesize(spoken, result.language, self._voice)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - text already delivered via the answer event
            logger.error("TTS failed (%s)", type(e).__name__)
            self._emit(type="error", code="tts_failed")
            self._finish(gen)
            return
        if gen != self._turn_gen:
            return
        self._speak_start = self._clock()
        self._speech_ms = 0
        self._set_state(State.SPEAKING)
        self._track.play(audio)
        while self._track.is_playing:
            await asyncio.sleep(self._poll)
        self._finish(gen)

    def _finish(self, gen: int) -> None:
        if gen == self._turn_gen and not self._closed.is_set():
            self._set_state(State.LISTENING)
