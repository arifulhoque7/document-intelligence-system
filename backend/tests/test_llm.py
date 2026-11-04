"""AI extraction layer: schema strictness, provider error mapping, JSON validation, no invented values."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import openai
import pytest

from app import llm
from app.llm import EXTRACTION_SCHEMA, LLMError, ProviderConfig, extract_invoices
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.openai import OpenAIProvider
from app.services.pipeline import build_invoice

REQ = httpx.Request("POST", "https://api.example")


def test_schema_is_strict_everywhere():
    """Strict structured output: every object closes extra keys and requires every property."""
    def walk(node):
        if isinstance(node, dict):
            assert "$ref" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(EXTRACTION_SCHEMA)


class StubProvider:
    reply = "{}"

    def __init__(self, cfg):
        pass

    def complete_json(self, system, user, schema, schema_model):
        assert "<document>" in user and "never" in system.lower()
        return StubProvider.reply


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setitem(llm.REGISTRY, "claude", StubProvider)
    return ProviderConfig("claude", "m", "key", None, None)


def test_invalid_json_is_an_error(stub):
    StubProvider.reply = "not json"
    with pytest.raises(LLMError, match="invalid JSON"):
        extract_invoices(stub, "text")


def test_schema_violation_is_an_error(stub):
    StubProvider.reply = '{"invoices": [{"invoice_number": "X"}]}'
    with pytest.raises(LLMError, match="invalid JSON"):
        extract_invoices(stub, "text")


def test_missing_key_is_reported_before_any_call():
    with pytest.raises(LLMError, match="No API key"):
        extract_invoices(ProviderConfig("openai", "m", None, None, None), "x")


def test_nulls_stay_null_never_invented(stub):
    StubProvider.reply = (
        '{"invoices": [{"invoice_number": "INV-7", "invoice_date": null, "supplier_name": "Acme", "customer_name": null,'
        ' "subtotal": null, "tax": null, "total": 50, "currency": null, "line_items": [],'
        ' "confidence": {"invoice_number": 0.9, "invoice_date": 0, "supplier_name": 0.9, "customer_name": 0,'
        ' "subtotal": 0, "tax": 0, "total": 0.9, "currency": 0}}]}'
    )
    raw = extract_invoices(stub, "x").invoices[0].model_dump()
    inv = build_invoice(raw, "INV-7 Acme Total 50.00", "page 1", "claude/m", from_llm=True)
    assert inv.tax is None and inv.subtotal is None and inv.currency is None and inv.invoice_date is None
    assert inv.total is not None and inv.confidence["tax"] == 0.0


def test_hallucinated_value_loses_confidence(stub):
    StubProvider.reply = (
        '{"invoices": [{"invoice_number": "INV-7", "invoice_date": "2025-01-02", "supplier_name": "Totally Made Up Ltd",'
        ' "customer_name": null, "subtotal": null, "tax": null, "total": 50, "currency": "USD", "line_items": [],'
        ' "confidence": {"invoice_number": 0.9, "invoice_date": 0.9, "supplier_name": 0.95, "customer_name": 0,'
        ' "subtotal": 0, "tax": 0, "total": 0.9, "currency": 0.9}}]}'
    )
    raw = extract_invoices(stub, "x").invoices[0].model_dump()
    inv = build_invoice(raw, "INV-7 Acme Ltd Total $50.00", "page 1", "claude/m", from_llm=True)
    assert inv.confidence["supplier_name"] == 0.3 and inv.confidence["total"] == 0.9


def _claude(monkeypatch, effect):
    p = ClaudeProvider(ProviderConfig("claude", "claude-opus-5-5", "k", None, None))
    p.client = MagicMock()
    p.client.beta.messages.create.side_effect = effect
    return p


def test_claude_rate_limit_is_transient(monkeypatch):
    err = anthropic.RateLimitError("slow down", response=httpx.Response(429, request=REQ), body=None)
    with pytest.raises(LLMError) as e:
        _claude(monkeypatch, err).complete_json("s", "u", {}, None)
    assert e.value.transient


def test_claude_bad_request_is_permanent(monkeypatch):
    err = anthropic.BadRequestError("bad", response=httpx.Response(400, request=REQ), body=None)
    with pytest.raises(LLMError) as e:
        _claude(monkeypatch, err).complete_json("s", "u", {}, None)
    assert not e.value.transient


def test_claude_refusal_and_request_shape(monkeypatch):
    p = _claude(monkeypatch, None)
    p.client.beta.messages.create.return_value = SimpleNamespace(stop_reason="refusal", content=[])
    with pytest.raises(LLMError, match="declined"):
        p.complete_json("s", "u", {"type": "object"}, None)
    kwargs = p.client.beta.messages.create.call_args.kwargs
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["effort"] == "low" and kwargs["fallbacks"] == "default"


def test_openai_timeout_is_transient():
    p = OpenAIProvider(ProviderConfig("openai", "m", "k", None, "e"))
    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = openai.APITimeoutError(request=REQ)
    with pytest.raises(LLMError) as e:
        p.complete_json("s", "u", {}, None)
    assert e.value.transient


def test_claude_has_no_embeddings():
    with pytest.raises(LLMError, match="no embeddings"):
        ClaudeProvider(ProviderConfig("claude", "m", "k", None, None)).embed(["x"], 768)


def test_gemini_schema_conversion_is_accepted_by_sdk():
    from google.genai import types

    from app.llm.providers.gemini import to_gemini_schema

    g = to_gemini_schema(EXTRACTION_SCHEMA)
    assert "additionalProperties" not in str(g) and "anyOf" not in str(g)
    assert g["properties"]["invoices"]["items"]["properties"]["tax"] == {"type": "number", "nullable": True}
    types.GenerateContentConfig(response_mime_type="application/json", response_schema=g)  # raises if rejected
