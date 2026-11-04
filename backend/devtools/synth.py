"""Synthetic invoice generator with ground truth, used by the tests and the evaluation dataset.

Every invoice is rendered from a truth dict, so the expected extraction is known exactly.
Variants: digital PDF, scanned PDF, phone-photo JPG/PNG, multi-page TIFF, bundled multi-invoice PDF,
XLSX (multi-sheet), XLS, CSV and corrupted files."""

import io
import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import fitz
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SUPPLIERS = [
    "Meghna Office Supplies Ltd", "Dhaka Tech Solutions", "Northwind Traders", "Padma Logistics Ltd",
    "Contoso Hardware Inc", "Bengal Print House", "Globex Medical Supply", "Karnaphuli Foods Ltd",
    "Initech Software LLC", "Sylhet Tea Exporters", "Acme Industrial Parts", "Chittagong Shipping Agency",
]
CUSTOMERS = [
    "Cottage Home Care LLC", "Care Guide BD", "Sunrise Clinic", "Green Valley School", "Harbor Health Partners",
    "Lakeside Pharmacy", "Rahman Textiles Ltd", "Blue Ocean Hotels", "City Hospital Dhaka", "Evergreen Seniors Home",
]
ITEMS = [
    ("A4 paper ream 80gsm", 4.5), ("Toner cartridge HP 26A", 89.0), ("Nitrile gloves box (100)", 12.75),
    ("Wheelchair standard", 240.0), ("Blood pressure monitor", 45.9), ("Laptop service visit", 60.0),
    ("Cloud hosting (monthly)", 120.0), ("Delivery charge", 15.0), ("Cleaning supplies kit", 32.4),
    ("Face masks pack (50)", 9.99), ("Office chair ergonomic", 180.0), ("Network switch 24-port", 310.0),
    ("First aid kit", 27.5), ("Software license (annual)", 499.0), ("Printer paper A3", 7.2), ("Hand sanitizer 5L", 21.0),
]
CURRENCIES = [("USD", "$"), ("BDT", "BDT "), ("EUR", "EUR "), ("GBP", "GBP ")]
DATE_FORMATS = ["%Y-%m-%d", "%d %b %Y", "%B %d, %Y", "%d.%m.%Y", "%d/%m/%Y"]
TAX_RATES = [Decimal("0.05"), Decimal("0.075"), Decimal("0.10"), Decimal("0.15")]
C = Decimal("0.01")


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(C, ROUND_HALF_UP)


def make_truth(rng: random.Random, n_items: int | None = None, with_tax: bool | None = None, inv_no: str | None = None) -> dict:
    n = n_items or rng.choice([1, 2, 3, 4, 5, 6, 8])
    items = []
    for desc, price in rng.sample(ITEMS, k=min(n, len(ITEMS))) + [rng.choice(ITEMS) for _ in range(max(0, n - len(ITEMS)))]:
        qty = rng.choice([1, 1, 2, 3, 5, 10, 12])
        unit = money(price * rng.uniform(0.8, 1.6))
        items.append({"description": desc, "quantity": qty, "unit_price": str(unit), "amount": str(money(unit * qty))})
    subtotal = sum(Decimal(i["amount"]) for i in items)
    has_tax = rng.random() < 0.8 if with_tax is None else with_tax
    tax = money(subtotal * rng.choice(TAX_RATES)) if has_tax else None
    code, _ = rng.choice(CURRENCIES)
    d = date(2025, 1, 1) + timedelta(days=rng.randint(0, 300))
    prefix = rng.choice(["INV-2025-", "INV", "BL-", "SI/25/", "TX-"])
    return {
        "invoice_number": inv_no or f"{prefix}{rng.randint(100, 99999):05d}",
        "invoice_date": d.isoformat(),
        "supplier_name": rng.choice(SUPPLIERS),
        "customer_name": rng.choice(CUSTOMERS),
        "subtotal": str(subtotal),
        "tax": str(tax) if tax is not None else None,
        "total": str(subtotal + (tax or 0)),
        "currency": code,
        "line_items": items,
        "_date_format": rng.choice(DATE_FORMATS),
        "_layout": rng.choice(["classic", "modern", "compact"]),
    }


def _fmt(amount: str, truth: dict) -> str:
    sym = dict(CURRENCIES)[truth["currency"]]
    return f"{sym}{Decimal(amount):,.2f}"


def _story(truth: dict) -> list:
    ss = getSampleStyleSheet()
    printed_date = date.fromisoformat(truth["invoice_date"]).strftime(truth["_date_format"])
    layout = truth["_layout"]
    head = [
        Paragraph(f"<b>{truth['supplier_name']}</b>", ss["Title"] if layout != "compact" else ss["Heading2"]),
        Paragraph("House 12, Road 5, Dhanmondi, Dhaka 1205 | accounts@example.com", ss["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph("<b>TAX INVOICE</b>" if layout == "modern" else "<b>INVOICE</b>", ss["Heading2"]),
    ]
    meta = [["Invoice No:", truth["invoice_number"]], ["Invoice Date:", printed_date], ["Bill To:", truth["customer_name"]]]
    if layout == "modern":
        meta = [["Invoice #", truth["invoice_number"], "Date", printed_date], ["Customer", truth["customer_name"], "Currency", truth["currency"]]]
    head.append(Table(meta, hAlign="LEFT"))
    head.append(Spacer(1, 6 * mm))
    rows = [["Description", "Qty", "Unit Price", "Amount"]]
    rows += [[i["description"], str(i["quantity"]), _fmt(i["unit_price"], truth), _fmt(i["amount"], truth)] for i in truth["line_items"]]
    table = Table(rows, colWidths=[85 * mm, 20 * mm, 35 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79") if layout == "modern" else colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white if layout == "modern" else colors.black),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    totals = [["Subtotal:", _fmt(truth["subtotal"], truth)]]
    if truth["tax"] is not None:
        totals.append(["VAT:" if layout == "classic" else "Tax:", _fmt(truth["tax"], truth)])
    totals.append(["Total Due:" if layout == "compact" else "Total:", _fmt(truth["total"], truth)])
    t2 = Table(totals, colWidths=[140 * mm, 35 * mm])
    t2.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    foot = [Spacer(1, 8 * mm), Paragraph("Payment due within 30 days. Thank you for your business.", ss["Italic"])]
    return head + [table, Spacer(1, 3 * mm), t2] + foot


def render_pdf(truths: list[dict]) -> bytes:
    """One or more invoices (each starts on a new page) as a digital PDF."""
    from reportlab.platypus import PageBreak

    buf = io.BytesIO()
    story = []
    for i, t in enumerate(truths):
        if i:
            story.append(PageBreak())
        story += _story(t)
    SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm).build(story)
    return buf.getvalue()


def pdf_to_images(pdf: bytes, dpi: int = 150) -> list[Image.Image]:
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        return [Image.frombytes("RGB", (p.width, p.height), p.samples) for p in (pg.get_pixmap(dpi=dpi) for pg in doc)]


def degrade(img: Image.Image, rng: random.Random, level: str = "medium") -> Image.Image:
    """Simulate a scan or phone photo: slight rotation, blur, noise, low contrast."""
    angle = {"light": 0.5, "medium": 1.5, "heavy": 3.0}[level]
    img = img.convert("L").rotate(rng.uniform(-angle, angle), expand=True, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur({"light": 0.3, "medium": 0.7, "heavy": 1.1}[level]))
    noise = Image.effect_noise(img.size, {"light": 10, "medium": 25, "heavy": 40}[level])
    img = Image.blend(img, noise, {"light": 0.05, "medium": 0.1, "heavy": 0.16}[level])
    if level == "heavy":
        img = img.resize((int(img.width * 0.7), int(img.height * 0.7)))
    return img.point(lambda p: int(40 + p * 0.8))  # washed-out contrast


def images_to_pdf(images: list[Image.Image]) -> bytes:
    """Image-only PDF (no text layer), like a scanner produces."""
    buf = io.BytesIO()
    images[0].convert("RGB").save(buf, "PDF", save_all=True, append_images=[i.convert("RGB") for i in images[1:]], resolution=150)
    return buf.getvalue()


def save_image(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=55)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def save_tiff(images: list[Image.Image]) -> bytes:
    buf = io.BytesIO()
    images[0].save(buf, "TIFF", save_all=True, append_images=images[1:], compression="tiff_deflate")
    return buf.getvalue()


def table_rows(truths: list[dict]) -> list[list]:
    """One row per line item; invoice-level columns repeated (common ERP export shape)."""
    rows = [["Invoice No", "Invoice Date", "Supplier", "Customer", "Description", "Qty", "Unit Price", "Amount",
             "Subtotal", "Tax", "Total", "Currency"]]
    for t in truths:
        for li in t["line_items"]:
            rows.append([t["invoice_number"], t["invoice_date"], t["supplier_name"], t["customer_name"], li["description"],
                         li["quantity"], float(li["unit_price"]), float(li["amount"]), float(t["subtotal"]),
                         float(t["tax"]) if t["tax"] is not None else "", float(t["total"]), t["currency"]])
    return rows


def write_xlsx(sheets: dict[str, list[dict]], path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for name, truths in sheets.items():
        ws = wb.create_sheet(name)
        for row in table_rows(truths):
            ws.append(row)
    wb.save(path)


def write_xls(truths: list[dict], path: Path) -> None:
    import xlwt

    wb = xlwt.Workbook()
    ws = wb.add_sheet("Invoices")
    for r, row in enumerate(table_rows(truths)):
        for c, v in enumerate(row):
            ws.write(r, c, v)
    wb.save(str(path))


def write_csv(truths: list[dict], path: Path) -> None:
    import csv

    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(table_rows(truths))


def public_truth(t: dict) -> dict:
    return {k: v for k, v in t.items() if not k.startswith("_")}


def write_case(out: Path, name: str, data: bytes | None, truths: list[dict], meta: dict) -> dict:
    if data is not None:
        (out / name).write_bytes(data)
    return {"file": name, **meta, "invoices": [public_truth(t) for t in truths]}


def build_dataset(out: Path, seed: int = 7, scale: int = 1) -> list[dict]:
    """Write the labeled dataset to `out` and return the manifest (also saved as labels.json)."""
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    cases = []

    for i in range(12 * scale):  # digital PDFs, varied layouts
        t = make_truth(rng)
        cases.append(write_case(out, f"digital_{i:02d}.pdf", render_pdf([t]), [t], {"kind": "pdf_digital"}))
    for i in range(3 * scale):  # long invoices spanning pages
        t = make_truth(rng, n_items=rng.randint(28, 45))
        cases.append(write_case(out, f"multipage_{i:02d}.pdf", render_pdf([t]), [t], {"kind": "pdf_multipage"}))
    for i in range(2 * scale):  # one PDF holding several invoices
        ts = [make_truth(rng) for _ in range(rng.randint(3, 6))]
        cases.append(write_case(out, f"bundle_{i:02d}.pdf", render_pdf(ts), ts, {"kind": "pdf_bundle"}))
    for i in range(8 * scale):  # scanned PDFs at varied quality
        t = make_truth(rng)
        level = ["light", "medium", "heavy"][i % 3]
        imgs = [degrade(im, rng, level) for im in pdf_to_images(render_pdf([t]), dpi=200)]
        cases.append(write_case(out, f"scanned_{level}_{i:02d}.pdf", images_to_pdf(imgs), [t], {"kind": "pdf_scanned", "quality": level}))
    for i in range(8 * scale):  # phone photos / scans as images
        t = make_truth(rng, n_items=rng.randint(1, 6))
        level = ["light", "medium", "heavy"][i % 3]
        img = degrade(pdf_to_images(render_pdf([t]), dpi=200)[0], rng, level)
        fmt, ext = (("JPEG", "jpg"), ("PNG", "png"))[i % 2]
        cases.append(write_case(out, f"image_{level}_{i:02d}.{ext}", save_image(img, fmt), [t], {"kind": f"image_{ext}", "quality": level}))
    for i in range(3 * scale):  # multi-page TIFF
        t = make_truth(rng, n_items=rng.randint(25, 35))
        imgs = [degrade(im, rng, "light") for im in pdf_to_images(render_pdf([t]), dpi=200)]
        cases.append(write_case(out, f"scan_{i:02d}.tiff", save_tiff(imgs), [t], {"kind": "tiff"}))
    for i in range(3 * scale):  # spreadsheets
        sheets = {"January": [make_truth(rng) for _ in range(3)], "February": [make_truth(rng) for _ in range(2)]}
        write_xlsx(sheets, out / f"ledger_{i:02d}.xlsx")
        cases.append(write_case(out, f"ledger_{i:02d}.xlsx", None, sum(sheets.values(), []), {"kind": "xlsx"}))
        ts = [make_truth(rng) for _ in range(3)]
        write_csv(ts, out / f"export_{i:02d}.csv")
        cases.append(write_case(out, f"export_{i:02d}.csv", None, ts, {"kind": "csv"}))
        ts = [make_truth(rng) for _ in range(2)]
        write_xls(ts, out / f"legacy_{i:02d}.xls")
        cases.append(write_case(out, f"legacy_{i:02d}.xls", None, ts, {"kind": "xls"}))

    # Cross verification: same invoice as PDF and in a spreadsheet; one pair disagrees on the total.
    t = make_truth(rng)
    cases.append(write_case(out, "xcheck_match.pdf", render_pdf([t]), [t], {"kind": "pdf_digital", "cross_check": "match"}))
    write_xlsx({"Sheet1": [t]}, out / "xcheck_match.xlsx")
    cases.append(write_case(out, "xcheck_match.xlsx", None, [t], {"kind": "xlsx", "cross_check": "match"}))
    t2 = make_truth(rng)
    cases.append(write_case(out, "xcheck_mismatch.pdf", render_pdf([t2]), [t2], {"kind": "pdf_digital", "cross_check": "mismatch"}))
    t2_bad = {**t2, "total": str(Decimal(t2["total"]) + 100)}
    write_xlsx({"Sheet1": [t2_bad]}, out / "xcheck_mismatch.xlsx")
    cases.append(write_case(out, "xcheck_mismatch.xlsx", None, [t2_bad], {"kind": "xlsx", "cross_check": "mismatch"}))

    # Validation: printed total is wrong (extraction must copy it, validation must flag it).
    t3 = make_truth(rng)
    t3["total"] = str(Decimal(t3["total"]) + Decimal("50.00"))
    cases.append(write_case(out, "wrong_total.pdf", render_pdf([t3]), [t3], {"kind": "pdf_digital", "expect_issue": "TOTAL_MISMATCH"}))

    # Failure cases: must fail cleanly, not crash.
    good = render_pdf([make_truth(rng)])
    cases.append(write_case(out, "corrupt_truncated.pdf", good[: len(good) // 3], [], {"kind": "corrupt", "expect_fail": True}))
    cases.append(write_case(out, "corrupt_random.pdf", bytes(rng.getrandbits(8) for _ in range(5000)), [], {"kind": "corrupt", "expect_fail": True}))
    cases.append(write_case(out, "corrupt_sheet.xlsx", b"PK\x03\x04" + b"\x00" * 200, [], {"kind": "corrupt", "expect_fail": True}))
    cases.append(write_case(out, "blank.png", save_image(Image.new("L", (1200, 1600), 255), "PNG"), [], {"kind": "blank", "expect_fail": True}))

    (out / "labels.json").write_text(json.dumps(cases, indent=2))
    return cases


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1] if len(sys.argv) > 1 else "dataset")
    print(f"{len(build_dataset(target))} cases written to {target}")
