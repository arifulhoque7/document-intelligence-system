from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMError, ProviderConfig

TRANSIENT = {429, 500, 502, 503, 504}


def to_gemini_schema(node):
    """JSON Schema -> Gemini's OpenAPI subset: `anyOf [T, null]` becomes `nullable`, and keys Gemini
    rejects (additionalProperties) are dropped. Strictness is still enforced by our Pydantic validation."""
    if isinstance(node, list):
        return [to_gemini_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node:
        options = [o for o in node["anyOf"] if o.get("type") != "null"]
        out = to_gemini_schema(options[0]) if len(options) == 1 else {"any_of": to_gemini_schema(options)}
        if len(options) < len(node["anyOf"]):
            out["nullable"] = True
        return out
    return {k: to_gemini_schema(v) for k, v in node.items() if k not in ("additionalProperties", "title", "default")}


class GeminiProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.client = genai.Client(api_key=cfg.api_key, http_options=types.HttpOptions(timeout=get_settings().llm_timeout_s * 1000))

    def _call(self, fn, **kwargs):
        try:
            return fn(**kwargs)
        except errors.APIError as e:
            raise LLMError(f"Gemini error {e.code}: {e.message}", transient=e.code in TRANSIENT) from e

    def complete_json(self, system: str, user: str, schema: dict, schema_model: type[BaseModel]) -> str:
        resp = self._call(
            self.client.models.generate_content,
            model=self.cfg.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=to_gemini_schema(schema),
                temperature=0,
            ),
        )
        return resp.text or ""

    def embed(self, texts: list[str], dim: int) -> list[list[float]]:
        resp = self._call(
            self.client.models.embed_content,
            model=self.cfg.embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=dim),
        )
        return [e.values for e in resp.embeddings]
