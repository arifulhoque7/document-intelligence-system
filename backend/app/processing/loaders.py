"""Turn an uploaded file into pages of text (and raw tables for spreadsheets)."""

import io
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
from PIL import Image, ImageSequence, UnidentifiedImageError

from app.core.config import get_settings
from app.processing.ocr import ocr_image

# Reject decompression bombs: ~100 MP is far above any real A4 scan at 600 dpi.
Image.MAX_IMAGE_PIXELS = 100_000_000
MIN_TEXT_CHARS = 30  # fewer alphanumerics than this on a PDF page means "scanned", so OCR it

Progress = Callable[[int, int], None]


class ProcessingError(Exception):
    """Expected failure with a message safe to show the user (corrupted, encrypted, empty, too large)."""


@dataclass
class Page:
    page_no: int
    text: str
    method: str  # text|ocr|sheet
    ocr_confidence: float | None = None
    sheet_name: str | None = None


@dataclass
class Content:
    pages: list[Page]
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)  # spreadsheets only


def _alnum(s: str) -> int:
    return sum(c.isalnum() for c in s)


def load_pdf(path: Path, progress: Progress | None = None) -> Content:
    cfg = get_settings()
    try:
        doc = fitz.open(path)
    except Exception as e:  # fitz raises several types for broken files
        raise ProcessingError(f"Corrupted or unreadable PDF: {e}") from e
    with doc:
        if doc.needs_pass and not doc.authenticate(""):
            raise ProcessingError("PDF is password protected")
        n = doc.page_count
        if n == 0:
            raise ProcessingError("PDF has no pages")
        if n > cfg.max_pages:
            raise ProcessingError(f"PDF has {n} pages, limit is {cfg.max_pages}")

        pages: list[Page | None] = [None] * n
        done = 0
        # PyMuPDF is not thread-safe, so render on this thread; Tesseract runs as a subprocess,
        # so OCR in a thread pool runs in parallel.
        with ThreadPoolExecutor(cfg.ocr_threads) as pool:
            pending = []
            for i in range(n):
                try:
                    page = doc.load_page(i)
                    text = page.get_text("text", sort=True)
                except Exception as e:
                    raise ProcessingError(f"Page {i + 1} is corrupted: {e}") from e
                if _alnum(text) >= MIN_TEXT_CHARS:
                    pages[i] = Page(i + 1, text.strip(), "text")
                    done += 1
                else:
                    pix = page.get_pixmap(dpi=cfg.ocr_dpi, colorspace=fitz.csGRAY)
                    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    pending.append((i, pool.submit(ocr_image, img)))
                # Bound memory on very large scanned PDFs: drain when the queue gets long.
                if len(pending) >= cfg.ocr_threads * 2 or i == n - 1:
                    for j, fut in pending:
                        text, conf = fut.result()
                        pages[j] = Page(j + 1, text, "ocr", round(conf, 1))
                        done += 1
                    pending.clear()
                if progress:
                    progress(done, n)
    return Content([p for p in pages if p is not None])


def load_image(path: Path, progress: Progress | None = None) -> Content:
    try:
        img = Image.open(path)
        frames = [f.copy() for f in ImageSequence.Iterator(img)]  # TIFF can hold many pages
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ProcessingError(f"Corrupted or unsupported image: {e}") from e
    if len(frames) > get_settings().max_pages:
        raise ProcessingError(f"Image has {len(frames)} frames, limit is {get_settings().max_pages}")
    pages = []
    with ThreadPoolExecutor(get_settings().ocr_threads) as pool:
        for i, (text, conf) in enumerate(pool.map(ocr_image, frames)):
            pages.append(Page(i + 1, text, "ocr", round(conf, 1)))
            if progress:
                progress(i + 1, len(frames))
    return Content(pages)


def _read_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ProcessingError("CSV encoding not recognised")
    try:
        # sep=None sniffs , ; tab |
        return pd.read_csv(io.StringIO(text), sep=None, engine="python", header=None, dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as e:
        raise ProcessingError(f"Malformed CSV: {e}") from e


def load_spreadsheet(path: Path, file_type: str, progress: Progress | None = None) -> Content:
    try:
        if file_type == "csv":
            tables = {"Sheet1": _read_csv(path)}
        else:
            engine = "openpyxl" if file_type == "xlsx" else "xlrd"
            tables = pd.read_excel(path, sheet_name=None, header=None, dtype=str, engine=engine)
    except ProcessingError:
        raise
    except Exception as e:  # zip, xml and OLE errors from the engines
        raise ProcessingError(f"Corrupted or unreadable spreadsheet: {e}") from e

    tables = {name: df.fillna("").astype(str) for name, df in tables.items()}
    tables = {name: df for name, df in tables.items() if df.map(str.strip).ne("").any().any()}
    if not tables:
        raise ProcessingError("Spreadsheet is empty")
    pages = []
    for i, (name, df) in enumerate(tables.items(), start=1):
        rows = [" | ".join(c.strip() for c in row if c.strip()) for row in df.itertuples(index=False)]
        pages.append(Page(i, "\n".join(r for r in rows if r), "sheet", sheet_name=str(name)))
        if progress:
            progress(i, len(tables))
    return Content(pages, tables)


def load(path: Path, file_type: str, progress: Progress | None = None) -> Content:
    if file_type == "pdf":
        content = load_pdf(path, progress)
    elif file_type in ("image", "tiff"):
        content = load_image(path, progress)
    elif file_type in ("xlsx", "xls", "csv"):
        content = load_spreadsheet(path, file_type, progress)
    else:
        raise ProcessingError("Unsupported file type. Allowed: PDF, JPG, PNG, TIFF, XLSX, XLS, CSV")
    if not any(_alnum(p.text) for p in content.pages):
        raise ProcessingError("No readable text found (blank or unreadable document)")
    return content
