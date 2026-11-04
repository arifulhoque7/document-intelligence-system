# Large document benchmark (text extraction, OCR and segmentation; no LLM)

Machine: darwin, Python 3.11.13. Measured by `eval/benchmark_large.py`.

Each load runs in a fresh process, so peak RSS is the loader's own memory.

| Case | Pages | Load time (s) | Pages/s | Segmentation (ms) | Chunks for the LLM | Peak RSS (MB) |
|---|---|---|---|---|---|---|
| digital PDF, 480 invoices bundled | 1005 | 4.8 | 209.2 | 23.5 | 480 | 115 |
| scanned PDF, OCR_THREADS=4 | 100 | 56.42 | 1.8 | 0.5 | 84 | 722 |
