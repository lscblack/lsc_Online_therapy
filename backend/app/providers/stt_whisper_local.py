"""Local speech-to-text with faster-whisper (CTranslate2).

Runs on the GPU when CUDA is available (fast), else on the CPU (free, offline, no API key).
The model is loaded once (module singleton) and inference runs in a worker thread so the event
loop is never blocked. Decodes webm/ogg/opus/wav via PyAV, so it accepts the same audio the
browser/app records.
"""
import asyncio
import io
import logging

from app.providers.base import Transcript

logger = logging.getLogger(__name__)

_model = None
_model_key: tuple | None = None


def _resolve_device(device: str, compute_type: str) -> tuple[str, str]:
    if device != "auto":
        ct = compute_type if compute_type != "auto" else ("float16" if device == "cuda" else "int8")
        return device, ct
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", (compute_type if compute_type != "auto" else "float16")
    except Exception:  # noqa: BLE001 - no CUDA/CTranslate2 GPU build -> CPU
        pass
    return "cpu", (compute_type if compute_type != "auto" else "int8")


class LocalWhisperSTT:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "auto"):
        self._size = model_size
        self._device = device
        self._compute_type = compute_type

    def _get_model(self):
        global _model, _model_key
        key = (self._size, self._device, self._compute_type)
        if _model is not None and _model_key == key:
            return _model
        from faster_whisper import WhisperModel
        dev, ct = _resolve_device(self._device, self._compute_type)
        try:
            _model = WhisperModel(self._size, device=dev, compute_type=ct)
            logger.info("Loaded faster-whisper '%s' on %s (%s)", self._size, dev, ct)
        except Exception:  # noqa: BLE001 - GPU/driver issue -> CPU fallback
            logger.warning("faster-whisper on %s failed; falling back to CPU int8", dev, exc_info=True)
            _model = WhisperModel(self._size, device="cpu", compute_type="int8")
        _model_key = key
        return _model

    async def transcribe(self, audio: bytes, language: str | None,
                         filename: str | None = None) -> Transcript:
        def _run() -> tuple[str, str | None]:
            model = self._get_model()
            segments, info = model.transcribe(
                io.BytesIO(audio), language=language, vad_filter=True, beam_size=1)
            text = "".join(seg.text for seg in segments).strip()
            return text, getattr(info, "language", None)

        text, detected = await asyncio.to_thread(_run)
        return Transcript(text=text, language=detected or language)
