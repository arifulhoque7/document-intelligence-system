"""Deterministic mapping of tabular invoice spreadsheets (one row per invoice or per line item).
Exact and free; sheets that do not look like an invoice table go to the LLM instead."""

import re

import pandas as pd

from app.processing.normalize import norm_invoice_number, parse_amount, parse_currency, parse_date

SYNONYMS = {
    "invoice_number": ["invoice no", "invoice number", "invoice #", "invoice id", "inv no", "inv #", "bill no", "invoice"],
    "invoice_date": ["invoice date", "inv date", "bill date", "date"],
    "supplier_name": ["supplier", "supplier name", "vendor", "vendor name", "seller", "from"],
    "customer_name": ["customer", "customer name", "client", "client name", "buyer", "bill to"],
    "subtotal": ["subtotal", "sub total", "net amount", "net total"],
    "tax": ["tax", "vat", "gst", "tax amount", "vat amount"],
    "total": ["total", "grand total", "invoice total", "total amount", "amount due", "gross amount"],
    "currency": ["currency", "ccy", "curr"],
    "description": ["description", "item", "item description", "product", "service", "particulars"],
    "quantity": ["qty", "quantity", "units"],
    "unit_price": ["unit price", "rate", "price", "unit cost"],
    "amount": ["amount", "line total", "line amount", "line_total"],
}
LINE_FIELDS = ("description", "quantity", "unit_price", "amount")
HEADER_FIELDS = ("invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency")


def _key(cell: str) -> str:
    return re.sub(r"[\s_]+", " ", re.sub(r"[^a-z0-9#_ ]", "", cell.lower())).strip()


def _match_header(row: list[str]) -> dict[str, int]:
    lookup = {syn: f for f, syns in SYNONYMS.items() for syn in syns}
    found: dict[str, int] = {}
    for idx, cell in enumerate(row):
        field = lookup.get(_key(cell))
        if field and field not in found:
            found[field] = idx
    return found


def find_table(df: pd.DataFrame) -> tuple[int, dict[str, int]] | None:
    """Header row within the first 10 rows that names an invoice number plus at least two other fields."""
    for r in range(min(10, len(df))):
        cols = _match_header([str(c) for c in df.iloc[r].tolist()])
        if "invoice_number" in cols and len(cols) >= 3:
            return r, cols
    return None


def map_sheet(df: pd.DataFrame, sheet_name: str) -> list[dict] | None:
    """Return invoice dicts, or None when the sheet is not a recognised invoice table."""
    found = find_table(df)
    if not found:
        return None
    header_row, cols = found
    invoices: dict[str, dict] = {}
    for r in range(header_row + 1, len(df)):
        row = [str(c).strip() for c in df.iloc[r].tolist()]
        if not any(row):
            continue
        get = lambda f: row[cols[f]] if f in cols and cols[f] < len(row) and row[cols[f]] else None  # noqa: E731
        number = get("invoice_number")
        if not number:
            continue  # totals/footer rows
        key = norm_invoice_number(number) or number
        inv = invoices.get(key)
        if inv is None:
            inv = invoices[key] = {
                "invoice_number": number,
                "line_items": [],
                "rows": [r + 1, r + 1],
                "confidence": {},
            }
            for f in HEADER_FIELDS:
                inv[f] = get(f)
        inv["rows"][1] = r + 1
        # Header values may only be filled on the first row of a group.
        for f in HEADER_FIELDS:
            if inv.get(f) is None and get(f):
                inv[f] = get(f)
        if any(f in cols for f in LINE_FIELDS) and (get("description") or get("amount")):
            inv["line_items"].append(
                {
                    "description": get("description"),
                    "quantity": parse_amount(get("quantity")),
                    "unit_price": parse_amount(get("unit_price")),
                    "amount": parse_amount(get("amount")),
                }
            )

    out = []
    for inv in invoices.values():
        d, ambiguous = parse_date(inv["invoice_date"])
        rows = inv.pop("rows")
        inv.update(
            invoice_date=d,
            subtotal=parse_amount(inv["subtotal"]),
            tax=parse_amount(inv["tax"]),
            total=parse_amount(inv["total"]),
            currency=parse_currency(inv["currency"]),
            source_ref=f"sheet {sheet_name} rows {rows[0]}-{rows[1]}",
        )
        # Values read straight from cells are certain; missing ones get 0.
        inv["confidence"] = {
            f: (0.6 if f == "invoice_date" and ambiguous else 1.0) if inv.get(f) not in (None, "") else 0.0
            for f in ("invoice_number", "invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency")
        }
        out.append(inv)
    return out
