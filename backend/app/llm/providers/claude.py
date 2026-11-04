import re

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMError, ProviderConfig


class ClaudeProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.client = anthropic.Anthropic(api_key=cfg.api_key, timeout=get_settings().llm_timeout_s, max_retries=2)

    def complete_json(self, system: str, user: str, schema: dict, schema_model: type[BaseModel]) -> str:
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        # Extraction is a simple task: low effort keeps latency and cost down on Claude 5-family models.
        if re.match(r"claude-(opus|sonnet|haiku|fable)-5", self.cfg.model):
            output_config["effort"] = "low"
        try:
            resp = self.client.beta.messages.create(
                model=self.cfg.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
                # On a policy decline the API retries on its default fallback model; no-op where none exists.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            raise LLMError(f"Claude temporarily unavailable: {e}", transient=True) from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude error {e.status_code}: {e.message}") from e
        if resp.stop_reason == "refusal":
            raise LLMError("Claude declined to process this document")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Claude output was cut off (max_tokens)")
        return next(b.text for b in resp.content if b.type == "text")

    def embed(self, texts: list[str], dim: int) -> list[list[float]]:
        raise LLMError("Claude has no embeddings API; choose OpenAI, Gemini or Ollama for embeddings")
