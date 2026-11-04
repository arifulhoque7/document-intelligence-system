"""Value parsing and validation rules."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Invoice
from app.processing.normalize import norm_invoice_number, parse_amount, parse_currency, parse_date
from app.services.validation import check_invoice, ground, is_grounded


@pytest.mark.parametrize(
    "raw,expected",
    [("1,234.50", "1234.50"), ("1.234,50", "1234.50"), ("$ 12", "12.00"), ("(12.00)", "-12.00"), (12.5, "12.50"),
     ("BDT 3,000", "3000.00"), ("12,5", "12.50"), ("abc", None), ("", None), (None, None)],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == (Decimal(expected) if expected else None)


def test_parse_date_formats_and_ambiguity():
    assert parse_date("2025-03-04") == (date(2025, 3, 4), False)
    assert parse_date("15 Mar 2025") == (date(2025, 3, 15), False)
    assert parse_date("March 15, 2025") == (date(2025, 3, 15), False)
    assert parse_date("03/04/2025") == (date(2025, 4, 3), True)  # day-first, flagged ambiguous
    assert parse_date("not a date") == (None, False)


def test_currency_and_invoice_number():
    assert parse_currency("$") == "USD" and parse_currency("Tk") == "BDT" and parse_currency("eur") == "EUR"
    assert parse_currency("dollars?") is None
    assert norm_invoice_number(" inv-00123 ") == "INV00123"


def inv(**kw) -> Invoice:
    base = dict(invoice_number="INV-1", invoice_date=date(2025, 5, 1), supplier_name="Acme", customer_name="Care Guide",
                subtotal=Decimal("100.00"), tax=Decimal("10.00"), total=Decimal("110.00"), currency="USD",
                line_items=[{"description": "A", "quantity": "2", "unit_price": "50.00", "amount": "100.00"}],
                confidence={}, source_text="INV-1 Acme Care Guide 100.00 10.00 110.00 2 50.00")
    base.update(kw)
    return Invoice(**base)


def codes(i: Invoice) -> set[str]:
    return {c for c, *_ in check_invoice(i)}


def test_clean_invoice_has_no_issues():
    assert codes(inv()) == set()


def test_missing_required_fields():
    found = check_invoice(inv(invoice_number=None, total=None, source_text="Acme"))
    assert {(c, f) for c, f, s, _ in found if s == "error"} >= {("MISSING_FIELD", "invoice_number"), ("MISSING_FIELD", "total")}


def test_total_mismatch():
    assert "TOTAL_MISMATCH" in codes(inv(total=Decimal("120.00"), source_text="INV-1 Acme 100.00 10.00 120.00 2 50.00"))


def test_line_item_and_sum_mismatch():
    bad_line = [{"description": "A", "quantity": "2", "unit_price": "50.00", "amount": "90.00"}]
    assert {"LINE_ITEM_MISMATCH", "LINE_ITEMS_SUM_MISMATCH"} <= codes(inv(line_items=bad_line, source_text="INV-1 Acme 100.00 10.00 110.00 2 50.00 90.00"))


def test_rounding_within_tolerance_is_accepted():
    assert "TOTAL_MISMATCH" not in codes(inv(total=Decimal("110.01"), source_text="INV-1 Acme 100.00 10.00 110.01 2 50.00"))


def test_negative_future_tax_currency():
    future = date.today() + timedelta(days=30)
    found = codes(inv(invoice_date=future, tax=Decimal("60.00"), total=Decimal("160.00"), currency="XYZ",
                      source_text="INV-1 Acme 100.00 60.00 160.00 2 50.00"))
    assert {"FUTURE_DATE", "TAX_RATE_IMPLAUSIBLE", "UNKNOWN_CURRENCY"} <= found
    assert "NEGATIVE_AMOUNT" in codes(inv(subtotal=Decimal("-5.00")))


def test_no_tax_line_items_sum_to_total():
    assert codes(inv(subtotal=None, tax=None, total=Decimal("100.00"), source_text="INV-1 Acme Care Guide 100.00 2 50.00")) == {
        "MISSING_FIELD"
    }


def test_grounding_flags_values_not_in_text():
    conf = {"supplier_name": 0.9, "total": 0.9}
    ground({"supplier_name": "Invented Corp", "total": Decimal("999.00")}, conf, "Acme Ltd total 110.00")
    assert conf == {"supplier_name": 0.3, "total": 0.3}
    assert is_grounded("total", Decimal("1234.50"), "Total: $1,234.50")
    assert is_grounded("total", Decimal("1234.50"), "Total: 1.234,50 EUR")
    assert "UNGROUNDED_VALUE" in codes(inv(supplier_name="Invented Corp"))


def test_manually_confirmed_values_are_not_flagged_ungrounded():
    assert "UNGROUNDED_VALUE" not in codes(inv(supplier_name="Typed By Reviewer", confidence={"supplier_name": 1.0}))
