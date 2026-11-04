"""Deterministic stand-in for the LLM: parses the synthetic layouts with regexes."""

import hashlib
import re

from app.llm import LLMError, ProviderConfig
from app.llm.base import ExtractionResult
from app.processing.normalize import parse_date

AMOUNT = r"(?:[A-Z]{3} |\$)?([\d,]+\.\d{2})"


def _find(pattern: str, text: str):
    m = re.search(pattern, text, re.I | re.M)
    return m.group(1).strip() if m else None


def _num(s):
    return float(s.replace(",", "")) if s else None


class FakeLLM:
    def __init__(self):
        self.calls = 0
        self.fail_with: LLMError | None = None  # set to simulate provider failures
        self.cfg = ProviderConfig("fake", "fake-model", "k", None, "fake-embed")
        self.embedding_enabled = True

    def active_config(self, db, kind):
        if kind == "embedding" and not self.embedding_enabled:
            return None
        return self.cfg

    def extract(self, cfg, text: str) -> ExtractionResult:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        # The pipeline sends one chunk per invoice; collapse the text layer's column padding.
        text = "\n".join(re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines())
        number = _find(r"Invoice (?:No:|#)\s*(\S+)", text)
        if not number:
            return ExtractionResult(invoices=[])
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("---")]
        raw_date = _find(r"(?:Invoice Date:|Date)\s*(.+?)$", text)
        d, _ = parse_date(raw_date)
        items = [
            {"description": desc.strip(), "quantity": float(q), "unit_price": _num(u), "amount": _num(a)}
            for desc, q, u, a in re.findall(rf"^(.+?) (\d+) {AMOUNT} {AMOUNT}$", text, re.M)
        ]
        fields = {
            "invoice_number": number,
            "invoice_date": d.isoformat() if d else None,
            "supplier_name": lines[0] if lines else None,
            "customer_name": _find(r"(?:Bill To:|Customer)\s*(.+?)(?: Currency.*)?$", text),
            "subtotal": _num(_find(rf"Subtotal:\s*{AMOUNT}", text)),
            "tax": _num(_find(rf"(?:VAT|Tax):\s*{AMOUNT}", text)),
            "total": _num(_find(rf"\bTotal(?: Due)?:\s*{AMOUNT}", text)),
            "currency": _find(r"\b(USD|BDT|EUR|GBP)\b", text) or ("USD" if "$" in text else None),
        }
        conf = {k: (0.95 if v is not None else 0.0) for k, v in fields.items()}
        invoices = [{**fields, "line_items": items, "confidence": conf}]
        return ExtractionResult.model_validate({"invoices": invoices})

    def embed(self, cfg, texts):
        """Bag-of-words hashing into 768 dims: similar texts get similar vectors."""
        out = []
        for t in texts:
            v = [0.0] * 768
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 768] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out
