import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMError, ProviderConfig


class OllamaProvider:
    """Local models over Ollama's REST API. No key; slower and less accurate than hosted models."""

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.base = (cfg.base_url or "").rstrip("/")

    def _post(self, path: str, body: dict, timeout: float) -> dict:
        try:
            r = httpx.post(f"{self.base}{path}", json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            raise LLMError(f"Ollama unreachable at {self.base}: {e}", transient=True) from e
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Ollama error {e.response.status_code}: {e.response.text[:200]}", transient=e.response.status_code >= 500) from e

    def complete_json(self, system: str, user: str, schema: dict, schema_model: type[BaseModel]) -> str:
        data = self._post(
            "/api/chat",
            {
                "model": self.cfg.model,
                "stream": False,
                "format": schema,
                "options": {"temperature": 0},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=get_settings().llm_timeout_s * 3,
        )
        return data["message"]["content"]

    def embed(self, texts: list[str], dim: int) -> list[list[float]]:
        vectors = self._post("/api/embed", {"model": self.cfg.embedding_model, "input": texts}, timeout=120)["embeddings"]
        if vectors and len(vectors[0]) != dim:
            raise LLMError(f"Ollama model {self.cfg.embedding_model} returns {len(vectors[0])} dims, need {dim}")
        return vectors
