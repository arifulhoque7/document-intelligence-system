import openai
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMError, ProviderConfig


class OpenAIProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.client = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=get_settings().llm_timeout_s, max_retries=2)

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError) as e:
            raise LLMError(f"OpenAI temporarily unavailable: {e}", transient=True) from e
        except openai.APIStatusError as e:
            raise LLMError(f"OpenAI error {e.status_code}: {e.message}") from e

    def complete_json(self, system: str, user: str, schema: dict, schema_model: type[BaseModel]) -> str:
        resp = self._call(
            self.client.chat.completions.create,
            model=self.cfg.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": schema}},
        )
        msg = resp.choices[0].message
        if msg.refusal:
            raise LLMError(f"OpenAI declined: {msg.refusal}")
        return msg.content or ""

    def embed(self, texts: list[str], dim: int) -> list[list[float]]:
        resp = self._call(self.client.embeddings.create, model=self.cfg.embedding_model, input=texts, dimensions=dim)
        return [d.embedding for d in resp.data]
