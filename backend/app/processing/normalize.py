"""Parse and normalise values coming from OCR text, spreadsheets, LLMs and manual edits."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "৳": "BDT", "¥": "JPY", "₹": "INR", "tk": "BDT", "tk.": "BDT"}
ISO_CURRENCIES = {
    "USD", "EUR", "GBP", "BDT", "INR", "JPY", "CNY", "AUD", "CAD", "CHF", "SGD", "AED", "SAR", "MYR",
    "PKR", "LKR", "NPR", "THB", "HKD", "NZD", "SEK", "NOK", "DKK", "ZAR", "QAR", "KWD", "IDR", "PHP",
}


def parse_amount(value) -> Decimal | None:
    """'1,234.50' / '1.234,50' / '$ 12' / '(12.00)' / 12.5 -> Decimal. None if not a number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
    s = str(value).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = re.sub(r"[^\d.,]", "", s)
    if not s or not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        # The right-most separator is the decimal one.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = s.replace(",", ".") if len(tail) in (1, 2) and "," not in head else s.replace(",", "")
    try:
        d = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -d if negative else d


_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%d %b, %Y", "%Y%m%d", "%d/%m/%y", "%m/%d/%y",
)


def parse_date(value) -> tuple[date | None, bool]:
    """Return (date, ambiguous). Day-first wins for dd/mm vs mm/dd ambiguity (regional default); flagged."""
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return value.date(), False
    if isinstance(value, date):
        return value, False
    s = re.sub(r"\s+", " ", str(value).strip()).replace(" 00:00:00", "")
    if not s:
        return None, False
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        ambiguous = False
        m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
        if m and int(m.group(1)) <= 12 and int(m.group(2)) <= 12 and m.group(1) != m.group(2):
            ambiguous = True
        return d, ambiguous
    return None, False


def parse_currency(value) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if s.upper() in ISO_CURRENCIES:
        return s.upper()
    if s.lower() in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[s.lower()]
    for sym, code in CURRENCY_SYMBOLS.items():
        if len(sym) == 1 and sym in s:
            return code
    m = re.search(r"\b([A-Z]{3})\b", s.upper())
    return m.group(1) if m and m.group(1) in ISO_CURRENCIES else None


def norm_invoice_number(value) -> str | None:
    """Key for duplicate and cross-document matching: 'INV-00123 ' -> 'INV00123'."""
    if not value:
        return None
    s = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return s or None


def norm_name(value) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", str(value or "").lower())
    s = re.sub(r"\b(ltd|limited|inc|llc|co|corp|plc|pvt|the)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()
