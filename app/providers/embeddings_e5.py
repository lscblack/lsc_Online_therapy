import asyncio
from typing import Literal


class LocalE5Embeddings:
    """multilingual-e5 via sentence-transformers; model loaded lazily on first embed."""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-base"):
        self._name = model_name
        self._model = None

    @staticmethod
    def prefixed(texts: list[str], kind: Literal["query", "passage"]) -> list[str]:
        prefix = "query: " if kind == "query" else "passage: "
        return [prefix + t for t in texts]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy: imports torch

            self._model = SentenceTransformer(self._name)
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [[float(x) for x in v] for v in vecs]

    async def embed(
        self, texts: list[str], kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        # encode is CPU-bound and blocking: keep the event loop free
        return await asyncio.to_thread(self._encode, self.prefixed(texts, kind))
