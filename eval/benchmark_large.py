"""Benchmark the document stages on large files (no LLM): a 1000-page digital PDF and a 100-page scanned PDF.
Measures wall time, pages per second, chunking and peak memory of the loader.

    cd backend && .venv/bin/python ../eval/benchmark_large.py
"""

import json
import random
import resource
import subprocess
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
    """Measure in a fresh process so peak memory is the loader's, not the generator's."""
    proc = subprocess.run([sys.executable, __file__, "--one", str(path), ftype], capture_output=True, text=True, check=True)
    row = {"case": name, **json.loads(proc.stdout.strip().splitlines()[-1])}
    print(row, flush=True)
    return row


def bench_one(path: Path, ftype: str) -> dict:
    t = time.perf_counter()
    content = load(path, ftype)
    load_s = time.perf_counter() - t
    t = time.perf_counter()
    chunks = segment_pages(content.pages)
    seg_s = time.perf_counter() - t
    n = len(content.pages)
    return {"pages": n, "load_s": round(load_s, 2), "pages_per_s": round(n / load_s, 1),
            "segment_ms": round(seg_s * 1000, 1), "chunks": len(chunks), "peak_rss_mb": round(peak_mb())}


def main() -> None:
    rng = random.Random(3)
    tmp = Path(tempfile.mkdtemp())
    rows = []

    # At least 1000 pages: invoices with long item lists (1-3 pages each) bundled into one PDF.
    truths = [synth.make_truth(rng, n_items=rng.randint(28, 70)) for _ in range(480)]
    big = tmp / "big.pdf"
    big.write_bytes(synth.render_pdf(truths))
    import fitz

    assert fitz.open(big).page_count >= 1000, "increase the invoice count"
    rows.append(bench(f"digital PDF, {len(truths)} invoices bundled", big, "pdf"))

    # 100 scanned pages (image-only PDF): every page goes through OCR.
    scans = []
    while len(scans) < 100:
        t = synth.make_truth(rng)
        scans += [synth.degrade(i, rng, "medium") for i in synth.pdf_to_images(synth.render_pdf([t]), dpi=200)]
    scanned = tmp / "scanned.pdf"
    scanned.write_bytes(synth.images_to_pdf(scans[:100]))
    del scans
    rows.append(bench(f"scanned PDF, OCR_THREADS={get_settings().ocr_threads}", scanned, "pdf"))

    out = Path(__file__).parent / "results" / "benchmark_large.md"
    out.parent.mkdir(exist_ok=True)
    lines = ["# Large document benchmark (text extraction, OCR and segmentation; no LLM)", "",
             f"Machine: {sys.platform}, Python {sys.version.split()[0]}. Measured by `eval/benchmark_large.py`.", "",
             "Each load runs in a fresh process, so peak RSS is the loader's own memory.", "",
             "| Case | Pages | Load time (s) | Pages/s | Segmentation (ms) | Chunks for the LLM | Peak RSS (MB) |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['case']} | {r['pages']} | {r['load_s']} | {r['pages_per_s']} | {r['segment_ms']} | {r['chunks']} | {r['peak_rss_mb']} |" for r in rows]
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    if sys.argv[1:2] == ["--one"]:
        print(json.dumps(bench_one(Path(sys.argv[2]), sys.argv[3])))
    else:
        main()
