"""Embeddings via a local Ollama server. Free, no API key, no network egress."""

from __future__ import annotations

import httpx


class EmbeddingError(RuntimeError):
    pass


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _available_models(self) -> list[str]:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]

    def check(self) -> None:
        """Fail loudly and early: a missing model is the #1 first-run error here."""
        try:
            models = self._available_models()
        except httpx.HTTPError as exc:
            raise EmbeddingError(
                f"cannot reach Ollama at {self.base_url} ({exc}). Is the ollama container up?"
            ) from exc
        if not any(m == self.model or m.startswith(f"{self.model}:") for m in models):
            raise EmbeddingError(
                f"embedding model {self.model!r} is not pulled. Run: ollama pull {self.model}\n"
                f"available: {', '.join(models) or '(none)'}"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed. /api/embed takes a list and returns vectors in input order."""
        if not texts:
            return []
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            if r.status_code == 404:
                self.check()  # turns a 404 into an actionable message
            r.raise_for_status()
            vectors = r.json().get("embeddings") or []
        if len(vectors) != len(texts):
            raise EmbeddingError(f"expected {len(texts)} vectors, got {len(vectors)}")
        return vectors
