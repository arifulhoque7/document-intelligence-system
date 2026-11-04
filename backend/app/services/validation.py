"""Validation rules, grounding check, duplicate detection and cross-document verification."""

import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice, ValidationIssue
from app.processing.normalize import ISO_CURRENCIES, norm_name, parse_amount

REQUIRED = ("invoice_number", "invoice_date", "supplier_name", "total")
RECOMMENDED = ("customer_name", "subtotal", "currency")
MONEY = ("subtotal", "tax", "total")
LOW_CONFIDENCE = 0.6


def tolerance(amount: Decimal) -> Decimal:
    """0.01 or 0.5%, whichever is larger: absorbs per-line rounding without hiding real errors."""
    return max(Decimal("0.01"), abs(amount) * Decimal("0.005"))


# ---------- grounding: is the value actually printed in the source text? ----------

def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _number_variants(d: Decimal) -> set[str]:
    q = abs(d).quantize(Decimal("0.01"))
    whole = int(q)
    plain = f"{q:.2f}"
    out = {plain, f"{whole:,}.{plain[-2:]}", f"{whole:,}".replace(",", ".") + "," + plain[-2:]}
    if plain.endswith(".00"):
        out |= {str(whole), f"{whole:,}"}
    elif plain.endswith("0"):
        out.add(plain[:-1])
    return out


def is_grounded(field: str, value, source_text: str) -> bool:
    if value in (None, ""):
        return True
    if field in MONEY:
        d = parse_amount(value)
        if d is None:
            return False
        return any(v in source_text for v in _number_variants(d))
    if field == "invoice_date" or field == "currency":
        return True  # normalised formats (ISO date, ISO code) rarely match the printed form
    return _squash(str(value)) in _squash(source_text)


def ground(fields: dict, confidence: dict, source_text: str) -> None:
    """Cap the LLM's confidence for values that are not printed in the source text (likely invented or misread)."""
    for f in ("invoice_number", "supplier_name", "customer_name", *MONEY):
        if not is_grounded(f, fields.get(f), source_text):
            confidence[f] = min(confidence.get(f, 0.0), 0.3)


# ---------- rules ----------

def ungrounded_fields(inv: Invoice) -> list[str]:
    """Fields whose value is not printed in the source. Values a person confirmed (confidence 1.0) are trusted."""
    conf = inv.confidence or {}
    return [
        f for f in ("invoice_number", "supplier_name", "customer_name", *MONEY)
        if conf.get(f, 0) < 1.0 and not is_grounded(f, getattr(inv, f), inv.source_text or "")
    ]


def check_invoice(inv: Invoice) -> list[tuple[str, str | None, str, str]]:
    """Pure rule checks on one invoice. Returns (code, field, severity, message)."""
    issues = []
    ungrounded = ungrounded_fields(inv)
    add = lambda code, field, sev, msg: issues.append((code, field, sev, msg))  # noqa: E731

    for f in REQUIRED:
        if getattr(inv, f) in (None, ""):
            add("MISSING_FIELD", f, "error", f"{f.replace('_', ' ').capitalize()} is missing")
    for f in RECOMMENDED:
        if getattr(inv, f) in (None, ""):
            add("MISSING_FIELD", f, "warning", f"{f.replace('_', ' ').capitalize()} is missing")

    for f in MONEY:
        v = getattr(inv, f)
        if v is not None and v < 0:
            add("NEGATIVE_AMOUNT", f, "error", f"{f.capitalize()} is negative ({v})")

    sub, tax, total = inv.subtotal, inv.tax, inv.total
    if sub is not None and total is not None:
        expected = sub + (tax or Decimal("0"))
        if abs(expected - total) > tolerance(total):
            add(
                "TOTAL_MISMATCH", "total", "error",
                f"Subtotal {sub} + tax {tax or 0} = {expected}, but total is {total}",
            )
    if sub is not None and tax is not None and sub > 0:
        rate = tax / sub * 100
        if rate > 40:
            add("TAX_RATE_IMPLAUSIBLE", "tax", "warning", f"Tax is {rate:.1f}% of subtotal")
    if tax is not None and total is not None and tax > total:
        add("TAX_EXCEEDS_TOTAL", "tax", "error", f"Tax {tax} is larger than total {total}")

    items = inv.line_items or []
    line_sum = Decimal("0")
    have_amounts = False
    for i, li in enumerate(items, start=1):
        qty, price, amount = (parse_amount(li.get(k)) for k in ("quantity", "unit_price", "amount"))
        if amount is not None:
            have_amounts = True
            line_sum += amount
        if qty is not None and price is not None and amount is not None:
            if abs(qty * price - amount) > tolerance(amount):
                add("LINE_ITEM_MISMATCH", "line_items", "error", f"Line {i}: {qty} x {price} != {amount}")
    if have_amounts:
        target, name = (sub, "subtotal") if sub is not None else (total, "total")
        if target is not None and abs(line_sum - target) > tolerance(target):
            # When there is no subtotal, line items may legitimately sum to total minus tax.
            if not (name == "total" and tax is not None and abs(line_sum + tax - target) <= tolerance(target)):
                add("LINE_ITEMS_SUM_MISMATCH", name, "error", f"Line items sum to {line_sum}, but {name} is {target}")

    if inv.invoice_date:
        if inv.invoice_date > date.today() + timedelta(days=1):
            add("FUTURE_DATE", "invoice_date", "error", f"Invoice date {inv.invoice_date} is in the future")
        elif inv.invoice_date.year < 2000:
            add("IMPLAUSIBLE_DATE", "invoice_date", "warning", f"Invoice date {inv.invoice_date} looks wrong")

    if inv.currency and inv.currency not in ISO_CURRENCIES:
        add("UNKNOWN_CURRENCY", "currency", "warning", f"Currency '{inv.currency}' is not a recognised code")

    for f, c in (inv.confidence or {}).items():
        if getattr(inv, f, None) not in (None, "") and c < LOW_CONFIDENCE and f not in ungrounded:
            add("LOW_CONFIDENCE", f, "warning", f"Low extraction confidence for {f.replace('_', ' ')} ({c:.2f})")
    for f in ungrounded:
        add("UNGROUNDED_VALUE", f, "warning", f"Value for {f.replace('_', ' ')} was not found in the document text")
    return issues


def find_duplicates(db: Session, inv: Invoice) -> list[Invoice]:
    if not inv.invoice_number_norm:
        return []
    others = db.scalars(
        select(Invoice).where(Invoice.invoice_number_norm == inv.invoice_number_norm, Invoice.id != inv.id)
    ).all()
    return [o for o in others if not inv.supplier_name or not o.supplier_name or norm_name(o.supplier_name) == norm_name(inv.supplier_name)]


COMPARE = ("invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency")


def compare(a: Invoice, b: Invoice) -> dict[str, list]:
    """Field differences between two records of the same invoice (cross verification)."""
    diffs = {}
    for f in COMPARE:
        va, vb = getattr(a, f), getattr(b, f)
        if va in (None, "") or vb in (None, ""):
            continue
        same = norm_name(va) == norm_name(vb) if f in ("supplier_name", "customer_name") else va == vb
        if not same:
            diffs[f] = [str(va), str(vb)]
    if a.line_items and b.line_items and len(a.line_items) != len(b.line_items):
        diffs["line_items"] = [f"{len(a.line_items)} items", f"{len(b.line_items)} items"]
    return diffs


def validate(db: Session, inv: Invoice) -> list[Invoice]:
    """Replace the invoice's issues, run every rule, set needs_review. Returns the other records of the
    same invoice so the caller can re-validate them too (cross-document checks are symmetric). Caller commits."""
    found = check_invoice(inv)
    duplicates = find_duplicates(db, inv)
    for other in duplicates:
        if other.document_id == inv.document_id:
            found.append(("DUPLICATE_INVOICE", "invoice_number", "error", "Invoice number appears twice in this document"))
            continue
        diffs = compare(inv, other)
        fname = other.document.filename
        if diffs:
            detail = "; ".join(f"{f}: {x} vs {y}" for f, (x, y) in diffs.items())
            found.append(("CROSS_DOC_MISMATCH", None, "error", f"Same invoice in '{fname}' differs: {detail}"))
        else:
            found.append(("DUPLICATE_INVOICE", "invoice_number", "warning", f"Same invoice already processed in '{fname}'"))

    found = list(dict.fromkeys(found))  # the same file uploaded twice yields identical messages
    inv.issues = [ValidationIssue(code=c, field=f, severity=s, message=m) for c, f, s, m in found]
    money_warning = any(s == "warning" and f in MONEY for _, f, s, _ in found)
    inv.needs_review = any(s == "error" for _, _, s, _ in found) or money_warning
    if inv.status != "approved":
        inv.status = "needs_review" if inv.needs_review else "extracted"
    return duplicates
