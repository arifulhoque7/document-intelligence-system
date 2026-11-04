# Document Intelligence System v1.0: QA Handoff

**Release QA · Local Docker stack** · branch `main` · state as of **2026-11-04** (commit `acecb7d` plus this handoff)

Baseline: **none**. This is the first release; every feature below is new. The repository is `arifulhoque7/document-intelligence-system` (private until submission).

The whole system was built in one cycle and has been exercised on one machine (macOS, Docker Desktop) only. Nothing here has run on a shared staging server or with a hosted LLM provider.

| Scope | Count |
|---|---|
| Major features | 8 |
| Hardening found during QA | 6 fixes |
| Services | 5 (web, api, worker, db, redis) |
| Automated tests | 72 backend + 1 frontend unit check |
| Labeled evaluation documents | 74 (54 synthetic, 20 real receipts) |
| Commits | 9 · 162 files · +20,348 lines |

---

## Not tested: read this first

Nothing in this table was run or verified in this cycle. Treat these areas as unknown, not as working.

| # | Area | Not tested | Why | Risk if it is wrong | How to test it |
|---|---|---|---|---|---|
| 1 | Hosted LLMs | **No live call to Claude, OpenAI or Gemini.** Their adapters are unit-tested with mocked SDKs only | No API key was available; the run used the local Ollama model | A live API may reject the schema or a default model name (`claude-opus-5-5`, `gpt-5-mini`, `gemini-2.5-flash`); Claude refusal fallback never ran for real | Add a key in Settings, press **Test**, upload a PDF, then run `eval/run_eval.py` |
| 2 | Hosted embeddings | OpenAI and Gemini embeddings at 768 dimensions were never called | Same as above | Semantic search breaks if a provider ignores the dimension setting | **Test** an embedding provider; run a semantic search |
| 3 | Accuracy with a hosted model | All accuracy numbers come from a **7B local model** | No hosted key | Real accuracy with Claude/GPT/Gemini is unknown (expected higher, not measured) | `eval/run_eval.py` with the hosted provider active |
| 4 | Processing time | Times were measured on one laptop with one local GPU shared by 4 jobs | No hosted model, no server | Real-world latency per document is unknown | Same eval run on target hardware with a hosted model |
| 5 | Full 1000-page document with the LLM | The 1005-page benchmark covers text extraction and segmentation only; no LLM pass over 480 chunks | Hours of local LLM time | Rate limits, cost and total time for a 1000-page file are unmeasured | Upload a 1000-page PDF with a hosted provider and watch the timeline |
| 6 | Scaling out | `--scale worker=N` and multi-host deployment were never run | One machine, one worker container | Duplicate processing or lock issues under several workers are untested | `docker compose up -d --scale worker=4`, upload 50 files |
| 7 | Load and soak | No load test of the API (many users, many concurrent uploads) and no long soak run | Out of time for the assessment | Throughput limits and memory growth are unknown | k6 or Locust against `/api/documents` and `/api/search` |
| 8 | Large uploads through the web proxy | The 50 MB limit was tested by lowering it to 0 MB in a unit test; no real 50 MB file through the Next.js proxy | Not run | Proxy streaming or timeouts on big files may fail | Upload a 45 MB scanned PDF from the browser |
| 9 | Real business documents | Only synthetic invoices and 20 public receipts (SROIE); no real company invoices, no handwriting | No real data available | Accuracy on real layouts may be lower than measured | Run the eval on a labeled sample of real invoices |
| 10 | Languages | Only English; Tesseract has only the English pack | Not requested in the brief | Bangla or Arabic documents will OCR badly | Install `tesseract-ocr-ben`, test a Bangla invoice |
| 11 | Rotated scans | Synthetic scans tilt at most 3 degrees; pages rotated 90 or 180 degrees were never tested | Not in the dataset | The rotation fix (OSD) may not trigger as expected | Upload a scan rotated 90 degrees |
| 12 | Spreadsheet edge cases | Key-value invoice layouts in Excel going through the LLM, formulas without cached values, merged cells, password-protected XLSX | Not in the dataset | Wrong or empty values from unusual workbooks | Upload such workbooks and check the extracted fields |
| 13 | PDF edge cases | PDFs with only an owner password (opened with an empty user password) | Only a user-password PDF is tested | Such PDFs might be rejected or read wrongly | Upload an owner-password-only PDF |
| 14 | Re-embedding job | `reembed_all_task` after changing the embedding provider or model has no test | Not covered | Semantic search could return nothing after a switch | Switch embedding provider, wait, run a semantic search |
| 15 | Retry timing on a real outage | Backoff (15 s, 30 s, 60 s) was tested only in eager mode with a fake error | Not run against a real outage | Real retry timing and the final failure message are unverified | Stop Ollama during a job and watch the timeline |
| 16 | Killing a worker mid-job in Docker | Recovery was seen after a machine restart, not with `docker compose kill worker` | Not run | Behaviour may differ from the restart case | Kill the worker container during a long OCR job |
| 17 | Prompt injection | The prompt treats document text as data, but no adversarial document was tried | Not run | A crafted invoice could steer extraction | Upload an invoice that contains "ignore previous instructions..." |
| 18 | Security scanning | No penetration test, no OWASP ZAP scan, no `pip-audit`; `npm audit` flags PostCSS bundled in Next 15 (build time only) | Out of time | Unknown vulnerabilities in code or dependencies | Run ZAP against the stack, `pip-audit`, upgrade Next |
| 19 | CSRF and HTTPS | CSRF relies on SameSite=Strict cookies; never tested cross-site; never run behind TLS with `COOKIE_SECURE=true` | Local HTTP only | Misconfiguration in production | Deploy behind HTTPS and try a cross-site POST |
| 20 | Login rate limit per client | Behind the web proxy the limiter sees the proxy address, so the limit is per email only | Known design gap | One client can try many emails | Trusted-proxy header handling (next step) |
| 21 | Browsers and devices | Only Chromium (Playwright) at 1440 px; no Safari, Firefox or mobile layout | Not run | Layout or input issues on other browsers | Open each screen in Safari, Firefox and a phone |
| 22 | Accessibility | Labels, roles and keyboard focus only; no screen reader and no axe audit | Not run | Screen-reader users may hit barriers | axe DevTools plus VoiceOver pass |
| 23 | Frontend automated tests | One unit check; the browser checks were manual (Playwright) and are not in the repository as a test suite | Out of time | UI regressions are not caught automatically | Add a Playwright suite to CI |
| 24 | Database lifecycle | No migrations (schema created on start), no backup and restore, no upgrade of an existing database | Not needed for the assessment | Schema changes later need Alembic | Add Alembic, rehearse backup and restore |
| 25 | Secret rotation | Changing `ENCRYPTION_KEY` makes stored provider keys unreadable; no rotation tool | Not implemented | Keys must be re-entered after a rotation | Build a re-encrypt command |
| 26 | Linux Docker host | Only Docker Desktop on macOS; `host.docker.internal` on Linux relies on `host-gateway` | One machine | Ollama on the host may be unreachable from containers on Linux | Run the stack on a Linux server |
| 27 | Ambiguous dates | Day-first is assumed for dates like `03/04/2025` (flagged at confidence 0.6); US-format invoices were not evaluated | Not in the dataset | US invoices with ambiguous dates may be read wrongly (flagged for review) | Evaluate US-format invoices |

---

## Release train: what is actually in scope

| Service | Image | Scope |
|---|---|---|
| `web` | Next.js 15, `node:22-alpine`, non-root | All screens, runtime `/api` proxy, light and dark themes |
| `api` | `python:3.12-slim` + Tesseract 5, non-root | REST API, auth, uploads, settings, search; creates the schema and first admin on start |
| `worker` | same image as `api` | Celery: OCR, extraction, validation, embeddings, re-embedding |
| `db` | `pgvector/pgvector:pg16` | 8 tables, GIN full-text and HNSW vector indexes, `docintel_test` database for tests |
| `redis` | `redis:7-alpine` | Celery broker, login rate-limit counters |
| `eval/` | runs on the host | Evaluation harness, public-data fetcher, 1000-page benchmark |

---

## Major Features: test in depth

### 1. Document upload and processing (PDF, scanned PDF, JPG, PNG, TIFF, XLSX, XLS, CSV)

**Code:** `backend/app/processing/`, `backend/app/services/pipeline.py`, `backend/app/worker.py`, Dashboard upload zone

Files are typed by their content (magic bytes), not their extension. PDFs use the text layer per page and fall back to 300 dpi Tesseract OCR on pages without text; images and every TIFF frame get clean-up and confidence-driven OCR retries; every spreadsheet sheet is read with pandas. Processing runs in a Celery worker; the UI polls progress.

**Gating, read this first:** spreadsheets with recognisable invoice columns process **without any LLM**. Everything else needs an **active LLM provider** in Settings. Without one, PDFs and images fail with "No active LLM provider", which is correct behaviour, not a crash.

**How to test**

1. Upload one of each type in a single drop: digital PDF, scanned PDF, JPG, PNG, multi-page TIFF, XLSX with two sheets, XLS, CSV. All are accepted and move queued, processing, then completed or needs review; the progress bar advances.
2. Open a document: the timeline lists every stage with durations; the pages table shows `text`, `ocr` or `sheet` per page with OCR confidence; the text viewer shows the extracted text per page.
3. Upload a multi-page invoice (items spill to page 2): one invoice, totals read from the last page.
4. Upload a PDF holding several invoices: one invoice per invoice in the file.
5. Rename a PDF to `.png` and a PNG to `.pdf`: both are detected by content and processed correctly.
6. Download the original from the document page: it downloads as an attachment, never opens inline.

**Edge:** a nearly blank scanned page (only totals) must still OCR its text (this was a real bug, see Fixes). A 1000-page digital PDF loads in about 5 s; a scanned page takes about 0.55 s of OCR per worker thread.

**Regression risk:** OCR quality on poor scans; memory on very large scanned files (722 MB peak measured for 100 OCR pages).

---

### 2. AI extraction with grounding

**Code:** `backend/app/llm/`, `backend/app/services/pipeline.py` (`build_invoice`), `backend/app/services/validation.py` (`ground`)

Each chunk of text goes to the active provider with a strict JSON schema in which every field may be `null`. The answer is validated with Pydantic, then grounded: a value that is not printed in the source text has its confidence capped at 0.3 and raises `UNGROUNDED_VALUE`.

**Gating, read this first:** provider and model come from Settings. The only provider exercised live is **Ollama** (`qwen2.5-coder:7b`, `nomic-embed-text`). Claude, OpenAI and Gemini adapters are covered by unit tests with mocked SDKs only.

**How to test**

1. Upload an invoice with no tax line: tax shows **Not found**, never `0`.
2. Upload a receipt with no invoice number: the field is empty and `MISSING_FIELD` is raised, nothing is invented.
3. Edit a document's source so a supplier name the model returns is not in the text (or use the unit test `test_hallucinated_value_loses_confidence`): confidence drops and `UNGROUNDED_VALUE` appears.
4. Check per-field confidence badges on the invoice page: green, amber, red, grey for empty.

**Edge:** OCR misreads that are consistent in the text (an `SI/` prefix read as `S1/`) pass grounding; validation and review are the backstop.

**Regression risk:** any provider change (model, schema handling) must keep the "null, not guessed" behaviour.

---

### 3. Validation, review queue, corrections and approval

**Code:** `backend/app/services/validation.py`, `backend/app/services/invoices.py`, Review queue and invoice pages

14 rule codes (missing fields, totals, line items, tax, dates, currency, confidence, grounding, duplicates, cross-document). Any error, or a warning on a money field, sends the invoice to review.

**How to test**

1. Upload `eval/dataset/synthetic/wrong_total.pdf`: `TOTAL_MISMATCH` with the exact arithmetic in the message; the total field is outlined red.
2. Correct the total and **Save**: only changed fields are sent, the diff is shown, the issue clears, history shows v1 extraction and v2 manual.
3. Enter an invalid currency (`XYZ`) or text in a money field: the API refuses it with a field message (422).
4. **Approve**: v3 approval in history; when the document has no flagged invoices left, it turns Completed.
5. Edit an approved invoice: it returns to extracted and needs a fresh approval.
6. Upload the same file twice: `DUPLICATE_INVOICE` warning, shown once (not once per copy).

**Edge:** rounding tolerance is 0.01 or 0.5%; a 0.01 difference must not flag.

**Regression risk:** re-validation after edits also re-validates the matching invoice in other documents.

---

### 4. Cross-document verification (PDF-PDF, PDF-Excel)

**Code:** `backend/app/services/invoices.py` (`cross_checks`), `backend/app/services/validation.py` (`compare`), Cross-checks page

**How to test**

1. Upload `xcheck_match.pdf` and `xcheck_match.xlsx`: Cross-checks shows one `excel-pdf` pair marked **Match**; no issue on either invoice.
2. Upload `xcheck_mismatch.pdf` and `xcheck_mismatch.xlsx`: one pair marked **Mismatch** with the differing total side by side; **both** invoices get `CROSS_DOC_MISMATCH`, including the one processed first.
3. Toggle **Only show mismatches**.

**Edge:** the same invoice number twice inside one document is a `DUPLICATE_INVOICE` error, not a cross-check.

---

### 5. Search: keyword filters, keyword, semantic and hybrid

**Code:** `backend/app/services/search.py`, `backend/app/api/routers/invoices.py`, Search and Invoices pages

**Gating, read this first:** semantic search needs an **active embedding provider** (OpenAI, Gemini or Ollama; Claude has none). Without one, semantic returns a 503 with a clear message and hybrid silently falls back to keyword.

**How to test**

1. Invoices page filters: supplier, customer, invoice number, currency, status, needs review, date range, amount range, sort. Combine two filters.
2. Search a customer name plus an item ("Green Valley wheelchair") in each mode: the right invoice ranks in the top 3; keyword shows highlighted snippets.
3. Turn the embedding provider off: semantic shows the 503 message, hybrid still returns keyword results.
4. Change the embedding model: a re-embed job runs; semantic results come only from the current model.

**Regression risk:** HNSW index and generated `tsvector` columns must exist after a fresh start (created by the API on boot).

---

### 6. Settings: providers with masked keys, users and roles

**Code:** `backend/app/api/routers/settings.py`, `backend/app/core/security.py`, Settings page

**How to test**

1. Save a key for a provider: the card shows `abc…1234`; the key never appears in any API response or page source; in the database `provider_settings.api_key_enc` is ciphertext.
2. **Test** a provider: LLM and embedding results are reported, including a readable error for a bad key (never a bare 500).
3. **Remove key** clears it; an Ollama base URL like `file:///etc/passwd` is refused.
4. Create a reviewer: the reviewer can upload, correct and approve, but cannot save providers or create users (403, controls hidden).
5. 11 wrong passwords for one email: the 11th attempt is refused for 15 minutes (429).

**Edge:** behind the web proxy, the login limiter sees the proxy's address, so the limit is effectively per email, not per client IP.

---

### 7. Failure handling and reprocessing

**Code:** `backend/app/services/pipeline.py`, `backend/app/worker.py`, `backend/app/api/routers/documents.py`

**How to test**

1. Upload `corrupt_truncated.pdf`, `corrupt_random.pdf`, `corrupt_sheet.xlsx`, `blank.png`, a password-protected PDF and an empty file: each fails or is rejected with a readable reason; nothing crashes; other files in the same upload still process.
2. Deactivate the LLM, upload a PDF (fails), activate it again, press **Retry failed or stuck**: the document reprocesses, attempts becomes 2.
3. Stop Ollama mid-run: the job retries with backoff (15 s, 30 s, 60 s) and then fails with "gave up after N attempts".
4. Kill the worker container during a job (`docker compose kill worker`, then `up -d worker`): the job is redelivered and completes.
5. Restart the whole machine with jobs in the queue: finished documents are **not** reprocessed and reviewer corrections survive (see Fixes).
6. A document stuck in queued or processing for more than 10 minutes can be requeued with **Retry failed or stuck**.

**Regression risk:** anything that changes document status transitions (the redelivery guard relies on them).

---

### 8. Web interface

**Code:** `frontend/`

**How to test:** log in and out; every page in light and dark (Settings has the toggle; the choice survives a reload); collapse the sidebar to icons; open a deep link while logged out (redirect to login, then back); empty states (no documents, no search results); loading skeletons; toasts on save, approve and errors; keyboard: tab to every button and the line-item delete; no API text is rendered as HTML (try an invoice with `<b>` in a description).

---

## Hardening: verify behaviour

| Area | Change | What to check | Ref |
|---|---|---|---|
| OCR | Retry ladder on low confidence: rotation fix, raw image, other layout modes, binarisation | A rotated or faint scan still reads | `processing/ocr.py` |
| Settings | Provider test catches every SDK error and returns it as text | A bad Gemini or OpenAI key shows a message, not a 500 | `routers/settings.py` |
| Upload | Per-file results: a bad file in a batch does not reject the batch | Mixed batch with one corrupt file: others process | `routers/documents.py` |
| Eval | Single expected and single found invoice are paired even if the number was misread | Re-score with `--rescore` gives field-level credit | `eval/run_eval.py` |

---

## Fixes: confirm resolved + regression

| Area | Fix | What to check | Ref |
|---|---|---|---|
| OCR | Auto-contrast with a 1% cutoff erased all text on nearly blank pages (lost totals on page 2 of multi-page scans) | Multi-page TIFF: totals on the last page are read | `test_multiframe_tiff_reads_every_page` |
| Worker | A job redelivered after a restart reprocessed finished documents and could wipe reviewer corrections | Correct an invoice, restart the stack with messages pending: the correction survives | `test_redelivered_job_does_not_reprocess_finished_document` |
| Worker | Jobs lost when a worker died before acknowledging stayed queued for an hour | Requeue from **Retry failed or stuck** after 10 minutes without progress | `routers/documents.py` `_stale` |
| Gemini | The SDK rejected our JSON schema (`additionalProperties`, `anyOf null`), so the provider test returned a bare 500 | Gemini test returns a result or a readable error | `test_gemini_schema_conversion_is_accepted_by_sdk` |
| Validation | The same duplicate message appeared once per earlier copy of a file | Upload a file three times: one `DUPLICATE_INVOICE` line | `services/validation.py` |
| Local dev | Celery's prefork pool crashes on macOS (`ValueError: not enough values to unpack`) | Local worker uses `--pool=threads`; Docker keeps prefork | README troubleshooting |

---

## Release blockers and scope notes

> Read before starting the cycle.

**1. Configure a provider first.** Settings, add a key or set Ollama's base URL, press **Test**, then choose the active LLM and the active embedding provider. Without this, PDFs and images fail and semantic search returns 503. For Ollama inside Docker the base URL must be `http://host.docker.internal:11434`; for the app run outside Docker it is `http://localhost:11434`.

**2. Ports.** 3000, 8000, 5433 and 6379 on 127.0.0.1 must be free. A local Postgres on 5432 is fine (the stack uses 5433).

**3. Speed depends on the model host.** With the local 7B model on a laptop, an LLM document takes 20 s alone and about 100 s when four run at once on one GPU. Spreadsheets take under 1.5 s. Do not file slow local processing as a defect.

**4. Scale knobs.** `docker compose up -d --scale worker=4`; `OCR_THREADS` and `LLM_CONCURRENCY` per job.

**5. Secrets.** `.env` must set `JWT_SECRET`, `ENCRYPTION_KEY` (32 bytes, base64) and `ADMIN_PASSWORD`. Changing `ENCRYPTION_KEY` later makes stored provider keys unreadable (re-enter them).

**6. Measured baseline to compare against** (local Ollama, 74 documents): field accuracy 96.3%, invoice detection 99.0%, line items F1 98.0%, document success 98.6%, unexpected failures 0%, corrupted files rejected 4/4, correct invoices still sent to review 10.6%. Weakest areas: invoice numbers on scans (75%, OCR) and real receipts (date 80%, total 70%, supplier 65%).

**7. Coverage this cycle did not give you:** see [Not tested](#not-tested-read-this-first) at the top; 27 areas are listed there with the risk and how to test each.

---

## What was verified for this handoff

| Check | How | Result |
|---|---|---|
| Automated backend tests | `pytest -v` against Postgres `docintel_test` | 72 passed ([test-results.txt](test-results.txt)) |
| Frontend | `npm test`, `npm run build` (type check, lint) | passed |
| Full Docker stack | `docker compose up --build -d` | 5 services up; api, db, redis healthy |
| End to end in Docker | Login through the web proxy, provider test, CSV upload, heavy scanned PDF upload | CSV 3 invoices in 0.47 s; scanned PDF 8/8 fields and 4/4 line items correct in 22 s; Celery prefork in Linux |
| Every screen | Browser (Playwright) against the production build, light and dark | Screenshots in `frontend/docs/screenshots/` |
| Accuracy and rates | `eval/run_eval.py`, 74 documents through the API | [eval/results/report.md](../eval/results/report.md) |
| Large files | `eval/benchmark_large.py` | 1005 pages in 4.8 s; 100 OCR pages in 56 s ([benchmark](../eval/results/benchmark_large.md)) |
| Diagrams | Mermaid 11 parse and render of all 10 README diagrams | all render |
| Restart recovery | Machine restart with jobs pending | found and fixed the redelivery bug; regression test added |

*Generated from `git log` and `git diff --shortstat` on `main` (9 commits, 162 files, +20,348 lines), the test run in `docs/test-results.txt`, and the measured results in `eval/results/`, on 2026-11-04.*
