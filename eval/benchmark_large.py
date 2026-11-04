"""Benchmark the document stages on large files (no LLM): a 1000-page digital PDF and a 100-page scanned PDF.
Measures wall time, pages per second, chunking and peak memory of the loader.

    cd backend && .venv/bin/python ../eval/benchmark_large.py
"""

import random
import resource
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.processing.loaders import load  # noqa: E402
from app.processing.segment import segment_pages  # noqa: E402
from devtools import synth  # noqa: E402


def peak_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024  # bytes on macOS, KB on Linux


def bench(name: str, path: Path, ftype: str) -> dict:
    t = time.perf_counter()
    content = load(path, ftype)
    load_s = time.perf_counter() - t
    t = time.perf_counter()
    chunks = segment_pages(content.pages)
    seg_s = time.perf_counter() - t
    n = len(content.pages)
    row = {"case": name, "pages": n, "load_s": round(load_s, 2), "pages_per_s": round(n / load_s, 1),
           "segment_ms": round(seg_s * 1000, 1), "chunks": len(chunks), "peak_rss_mb": round(peak_mb())}
    print(row, flush=True)
    return row


def main() -> None:
    rng = random.Random(3)
    tmp = Path(tempfile.mkdtemp())
    rows = []

    # ~1000 pages: 330 invoices of 2-4 pages each (long item lists), as one bundled PDF.
    truths = [synth.make_truth(rng, n_items=rng.randint(28, 70)) for _ in range(330)]
    big = tmp / "big.pdf"
    big.write_bytes(synth.render_pdf(truths))
    rows.append(bench(f"digital PDF, {len(truths)} invoices", big, "pdf"))

    # 100 scanned pages (image-only PDF): every page goes through OCR.
    scans = []
    while len(scans) < 100:
        t = synth.make_truth(rng)
        scans += [synth.degrade(i, rng, "medium") for i in synth.pdf_to_images(synth.render_pdf([t]), dpi=200)]
    scanned = tmp / "scanned.pdf"
    scanned.write_bytes(synth.images_to_pdf(scans[:100]))
    rows.append(bench(f"scanned PDF, OCR_THREADS={get_settings().ocr_threads}", scanned, "pdf"))

    out = Path(__file__).parent / "results" / "benchmark_large.md"
    out.parent.mkdir(exist_ok=True)
    lines = ["# Large document benchmark (text extraction, OCR and segmentation; no LLM)", "",
             f"Machine: {sys.platform}, Python {sys.version.split()[0]}. Measured by `eval/benchmark_large.py`.", "",
             "| Case | Pages | Load time (s) | Pages/s | Segmentation (ms) | Chunks for the LLM | Peak RSS (MB) |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['case']} | {r['pages']} | {r['load_s']} | {r['pages_per_s']} | {r['segment_ms']} | {r['chunks']} | {r['peak_rss_mb']} |" for r in rows]
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    main()
