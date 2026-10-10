from app.providers.base import Transcript

_MSG = "planned: self-hosted Kinyarwanda model"


class DigitalUmugandaSTT:
    async def transcribe(self, audio: bytes, language: str | None,
                         filename: str | None = None) -> Transcript:
        raise NotImplementedError(_MSG)


class DigitalUmugandaTTS:
    async def synthesize(self, text: str, language: str, voice: str | None) -> bytes:
        raise NotImplementedError(_MSG)


class MbazaTTS(DigitalUmugandaTTS):
    pass
