"""Document processing: type detection, PDF text, OCR, spreadsheets, segmentation and failure modes."""

from decimal import Decimal

import fitz
import pytest

from app.core.config import get_settings
from app.processing.detect import detect_type
from app.processing.loaders import ProcessingError, load
from app.processing.segment import segment_pages
from app.processing.sheets import map_sheet
from devtools import synth


def write(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return p


@pytest.fixture
def truth(rng):
    return synth.make_truth(rng, n_items=3)


def test_detects_types_by_content_not_extension(tmp_path, truth):
    pdf = write(tmp_path, "looks_like.png", synth.render_pdf([truth]))
    png = write(tmp_path, "x.pdf", synth.save_image(synth.pdf_to_images(pdf.read_bytes())[0], "PNG"))
    synth.write_xlsx({"S": [truth]}, tmp_path / "a.xlsx")
    synth.write_xls([truth], tmp_path / "a.xls")
    synth.write_csv([truth], tmp_path / "a.csv")
    assert detect_type(pdf) == "pdf"
    assert detect_type(png) == "image"
    assert detect_type(tmp_path / "a.xlsx") == "xlsx"
    assert detect_type(tmp_path / "a.xls") == "xls"
    assert detect_type(tmp_path / "a.csv") == "csv"
    assert detect_type(write(tmp_path, "r.bin", bytes(range(256)) * 10)) == "unknown"
    assert detect_type(write(tmp_path, "e.pdf", b"")) == "unknown"


def test_digital_pdf_uses_text_layer(tmp_path, truth):
    content = load(write(tmp_path, "d.pdf", synth.render_pdf([truth])), "pdf")
    assert [p.method for p in content.pages] == ["text"]
    assert truth["invoice_number"] in content.pages[0].text
    assert truth["supplier_name"] in content.pages[0].text


def test_scanned_pdf_falls_back_to_ocr(tmp_path, truth, rng):
    imgs = [synth.degrade(i, rng, "medium") for i in synth.pdf_to_images(synth.render_pdf([truth]), dpi=200)]
    content = load(write(tmp_path, "s.pdf", synth.images_to_pdf(imgs)), "pdf")
    page = content.pages[0]
    assert page.method == "ocr" and page.ocr_confidence > 70
    assert truth["invoice_number"] in page.text
    assert f"{Decimal(truth['total']):,.2f}" in page.text


@pytest.mark.parametrize("level", ["light", "heavy"])
def test_ocr_on_poor_quality_images(tmp_path, truth, rng, level):
    img = synth.degrade(synth.pdf_to_images(synth.render_pdf([truth]), dpi=200)[0], rng, level)
    content = load(write(tmp_path, "p.jpg", synth.save_image(img, "JPEG")), "image")
    assert truth["invoice_number"] in content.pages[0].text


def test_multipage_pdf_stays_one_invoice_chunk(tmp_path, rng):
    t = synth.make_truth(rng, n_items=40)
    content = load(write(tmp_path, "m.pdf", synth.render_pdf([t])), "pdf")
    assert len(content.pages) >= 2
    assert len(segment_pages(content.pages)) == 1


def test_bundle_pdf_splits_per_invoice(tmp_path, rng):
    ts = [synth.make_truth(rng) for _ in range(4)]
    content = load(write(tmp_path, "b.pdf", synth.render_pdf(ts)), "pdf")
    chunks = segment_pages(content.pages)
    assert len(chunks) == 4
    assert all(t["invoice_number"] in c[0].text for t, c in zip(ts, chunks))


def test_multiframe_tiff_reads_every_page(tmp_path, rng):
    t = synth.make_truth(rng, n_items=30)
    imgs = [synth.degrade(i, rng, "light") for i in synth.pdf_to_images(synth.render_pdf([t]), dpi=200)]
    content = load(write(tmp_path, "t.tiff", synth.save_tiff(imgs)), "tiff")
    assert len(content.pages) == len(imgs) >= 2
    assert f"{Decimal(t['total']):,.2f}" in content.pages[-1].text  # totals on the last page


def _check_mapped(mapped, truths):
    by_no = {m["invoice_number"]: m for m in mapped}
    assert set(by_no) == {t["invoice_number"] for t in truths}
    for t in truths:
        m = by_no[t["invoice_number"]]
        assert m["invoice_date"].isoformat() == t["invoice_date"]
        assert m["supplier_name"] == t["supplier_name"] and m["customer_name"] == t["customer_name"]
        assert str(m["total"]) == t["total"] and m["currency"] == t["currency"]
        assert (str(m["tax"]) if m["tax"] is not None else None) == t["tax"]
        assert len(m["line_items"]) == len(t["line_items"])


def test_xlsx_multiple_sheets_mapped_exactly(tmp_path, rng):
    sheets = {"Jan": [synth.make_truth(rng) for _ in range(3)], "Feb": [synth.make_truth(rng) for _ in range(2)]}
    synth.write_xlsx(sheets, tmp_path / "l.xlsx")
    content = load(tmp_path / "l.xlsx", "xlsx")
    assert [p.sheet_name for p in content.pages] == ["Jan", "Feb"]
    for name, truths in sheets.items():
        _check_mapped(map_sheet(content.tables[name], name), truths)


@pytest.mark.parametrize("kind", ["xls", "csv"])
def test_xls_and_csv(tmp_path, rng, kind):
    ts = [synth.make_truth(rng) for _ in range(3)]
    path = tmp_path / f"f.{kind}"
    (synth.write_xls if kind == "xls" else synth.write_csv)(ts, path)
    content = load(path, kind)
    name = content.pages[0].sheet_name
    _check_mapped(map_sheet(content.tables[name], name), ts)


def test_unrecognised_sheet_layout_is_left_for_llm(tmp_path):
    (tmp_path / "kv.csv").write_text("Invoice,INV-9\nVendor details,Acme\nGrand,10\n")
    content = load(tmp_path / "kv.csv", "csv")
    assert map_sheet(content.tables["Sheet1"], "Sheet1") is None


@pytest.mark.parametrize(
    "name,data,ftype,msg",
    [
        ("trunc.pdf", None, "pdf", "Corrupted"),
        ("blank.png", synth.save_image(__import__("PIL.Image").Image.new("L", (800, 1000), 255), "PNG"), "image", "No readable text"),
        ("bad.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "image", "Corrupted"),
        ("bad.xlsx", b"PK\x03\x04" + b"\x00" * 100, "xlsx", "Corrupted"),
        ("empty.csv", b",,\n,,\n", "csv", "empty"),
    ],
)
def test_failures_raise_clean_errors(tmp_path, rng, name, data, ftype, msg):
    if data is None:
        good = synth.render_pdf([synth.make_truth(rng)])
        data = good[: len(good) // 3]
    with pytest.raises(ProcessingError, match=msg):
        load(write(tmp_path, name, data), ftype)


def test_encrypted_pdf_rejected(tmp_path, truth):
    doc = fitz.open(stream=synth.render_pdf([truth]), filetype="pdf")
    path = tmp_path / "enc.pdf"
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(ProcessingError, match="password"):
        load(path, "pdf")


def test_page_limit_enforced(tmp_path, truth, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_pages", 1)
    with pytest.raises(ProcessingError, match="limit"):
        load(write(tmp_path, "m.pdf", synth.render_pdf([truth, truth])), "pdf")
