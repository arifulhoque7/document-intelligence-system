"""LLM service: picks the active provider from Settings and exposes extraction and embeddings."""

import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.llm.base import ExtractionResult, LLMError, LLMProvider, ProviderConfig, inline_schema
from app.llm.prompts import SYSTEM_PROMPT, user_prompt
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai import OpenAIProvider
from app.models import ProviderSetting

__all__ = ["LLMError", "ProviderConfig", "active_config", "build_config", "extract_invoices", "embed", "PROVIDERS", "DEFAULTS"]

REGISTRY: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}
PROVIDERS = tuple(REGISTRY)
EMBEDDING_PROVIDERS = ("openai", "gemini", "ollama")  # Anthropic has no embeddings API
DEFAULTS = {
    "claude": {"model": "claude-opus-5-5", "embedding_model": None, "base_url": None},
    "openai": {"model": "gpt-5-mini", "embedding_model": "text-embedding-3-small", "base_url": None},
    "gemini": {"model": "gemini-2.5-flash", "embedding_model": "gemini-embedding-001", "base_url": None},
    "ollama": {"model": "qwen2.5:7b", "embedding_model": "nomic-embed-text", "base_url": "http://host.docker.internal:11434"},
}
EXTRACTION_SCHEMA = inline_schema(ExtractionResult)


def build_config(row: ProviderSetting) -> ProviderConfig:
    d = DEFAULTS[row.provider]
    return ProviderConfig(
        provider=row.provider,
        model=row.model or d["model"],
        api_key=decrypt_secret(row.api_key_enc) if row.api_key_enc else None,
        base_url=row.base_url or d["base_url"],
        embedding_model=row.embedding_model or d["embedding_model"],
    )


def active_config(db: Session, kind: str) -> ProviderConfig | None:
    col = ProviderSetting.active_llm if kind == "llm" else ProviderSetting.active_embedding
    row = db.scalar(select(ProviderSetting).where(col.is_(True)))
    return build_config(row) if row else None


def _provider(cfg: ProviderConfig) -> LLMProvider:
    if cfg.provider != "ollama" and not cfg.api_key:
        raise LLMError(f"No API key set for {cfg.provider}. Add it in Settings.")
    return REGISTRY[cfg.provider](cfg)


def extract_invoices(cfg: ProviderConfig, text: str) -> ExtractionResult:
    raw = _provider(cfg).complete_json(SYSTEM_PROMPT, user_prompt(text), EXTRACTION_SCHEMA, ExtractionResult)
    try:
        return ExtractionResult.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise LLMError(f"LLM returned invalid JSON: {str(e)[:300]}") from e


def embed(cfg: ProviderConfig, texts: list[str]) -> list[list[float]]:
    return _provider(cfg).embed(texts, get_settings().embedding_dim)
