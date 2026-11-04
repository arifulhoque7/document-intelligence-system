"""Provider-neutral contract for LLM extraction and embeddings."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class LLMError(Exception):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient  # rate limit / timeout / 5xx: worth a retry


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    embedding_model: str | None


class LLMProvider(Protocol):
    """One adapter per vendor. Adapters translate their SDK errors into LLMError."""

    def __init__(self, cfg: ProviderConfig) -> None: ...

    def complete_json(self, system: str, user: str, schema: dict, schema_model: type[BaseModel]) -> str:
        """Return a JSON string matching `schema`."""
        ...

    def embed(self, texts: list[str], dim: int) -> list[list[float]]: ...


# ---------- extraction output schema (strict: every key required, nullable instead of optional) ----------

class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None
    quantity: float | None
    unit_price: float | None
    amount: float | None


class FieldConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_number: float
    invoice_date: float
    supplier_name: float
    customer_name: float
    subtotal: float
    tax: float
    total: float
    currency: float


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_number: str | None
    invoice_date: str | None
    supplier_name: str | None
    customer_name: str | None
    subtotal: float | None
    tax: float | None
    total: float | None
    currency: str | None
    line_items: list[LineItem]
    confidence: FieldConfidence


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoices: list[ExtractedInvoice]


def inline_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema with $refs inlined and titles dropped: the shape every provider's strict mode accepts."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)
