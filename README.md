# Document Intelligence System

An AI-powered system that reads business documents (PDF, scanned PDF, JPG, PNG, TIFF, XLSX, XLS, CSV), extracts invoice data as structured JSON, validates it, cross-verifies the same invoice across documents, and makes everything searchable through a REST API and a web interface.

- **Backend**: Python 3.12, FastAPI, Celery workers on Redis, SQLAlchemy 2
- **Documents**: PyMuPDF (text layer), Tesseract 5 (OCR), pandas + openpyxl + xlrd (spreadsheets)
- **AI**: pluggable LLM providers selected in the UI: Claude, OpenAI, Gemini, Ollama (local); strict JSON-schema extraction
- **Data**: PostgreSQL 16 + pgvector (full-text keyword search, semantic search, hybrid ranking)
- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS
- **Delivery**: Docker Compose

| Doc | What is in it |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Architecture and pipeline diagrams, layering, design decisions, failure handling, scaling, security |
| [docs/database-schema.md](docs/database-schema.md) | ER diagram and table notes; generated DDL in [docs/schema.sql](docs/schema.sql) |
| [eval/results/report.md](eval/results/report.md) | Measured accuracy, success and failure rates, processing time |
| [docs/test-results.txt](docs/test-results.txt) | Output of the automated test run |
| [AI_DISCLOSURE.md](AI_DISCLOSURE.md) | Runtime prompts and AI-assisted development disclosure |

## Quick start (Docker)

Requirements: Docker Desktop (or Docker Engine + Compose v2).

```bash
cp .env.example .env
# Set JWT_SECRET, ENCRYPTION_KEY and ADMIN_PASSWORD in .env. To generate a key:
python3 -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

docker compose up --build -d
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API + Swagger UI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

1. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`.
2. Open **Settings**, paste an API key for Claude, OpenAI or Gemini (or point Ollama at `http://host.docker.internal:11434`), press **Test**, then choose the active LLM and the active embedding provider. Keys are encrypted at rest and only ever shown masked.
3. Upload documents on the **Dashboard** and watch them process.

Scale workers: `docker compose up -d --scale worker=4`.

## Local development (without Docker for the app)

```bash
docker compose up -d db redis              # Postgres on 127.0.0.1:5433, Redis on 6379
brew install tesseract                     # or: apt-get install tesseract-ocr

cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp ../.env .env
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/celery -A app.worker worker --loglevel=INFO --pool=threads --concurrency=4   # threads pool on macOS

cd ../frontend
npm ci && npm run dev                      # http://localhost:3000, proxies /api to API_URL (default http://localhost:8000)
```

## Tests

```bash
docker compose up -d db redis
cd backend && .venv/bin/python -m pytest -q
```

Tests use a separate `docintel_test` database (created by `backend/initdb/`), run Celery tasks inline, and replace the network LLM with a deterministic fake, so they are fast, free and repeatable. Suites:

| File | Covers |
|---|---|
| `tests/test_processing.py` | Type detection by content, digital PDF, scanned PDF OCR, poor-quality images, multi-page PDF, multi-invoice PDF splitting, multi-frame TIFF, XLSX with several sheets, XLS, CSV, corrupted/blank/encrypted files, page limit |
| `tests/test_normalize_validation.py` | Amount, date and currency parsing; every validation rule; tolerance; grounding |
| `tests/test_llm.py` | Strict schema, invalid JSON and schema violations, null handling (no invented values), hallucination detection, provider error mapping (transient vs permanent), refusals |
| `tests/test_api.py` | Auth, roles, rate limiting, upload of mixed batches, status, results, corrections and history, approval, keyword filters, keyword / semantic / hybrid search, cross-document checks, failed-job reprocessing, transient-failure retries, corrupted and oversized uploads, encrypted and masked provider keys |

## Evaluation

```bash
backend/.venv/bin/python eval/fetch_public.py 20                 # real scanned receipts (ICDAR 2019 SROIE)
backend/.venv/bin/python -m devtools.synth eval/dataset/synthetic   # run inside backend/: synthetic set with known truth
backend/.venv/bin/python eval/run_eval.py --password <admin password>
```

`run_eval.py` uploads every labeled file to the running stack through the API, waits for processing and scores the results. The synthetic set covers digital, multi-page, multi-invoice and scanned PDFs at three quality levels, JPG/PNG photos, multi-page TIFF, XLSX with several sheets, XLS, CSV, cross-verification pairs, a wrong-total invoice and corrupted files. Results: [eval/results/report.md](eval/results/report.md).

## API

All endpoints are under `/api` and need a session (cookie from `/api/auth/login`, or `Authorization: Bearer <token>`). Full schema at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login`, `/auth/logout`; GET `/auth/me` | Session |
| GET, POST | `/auth/users` | List and create users (admin) |
| POST | `/documents` | Upload many files (multipart field `files`); returns 202 with accepted and rejected files |
| GET | `/documents` | List with filters: `status`, `file_type`, `q` (filename or full text), pagination |
| GET | `/documents/{id}` | Status, progress, processing history, pages, invoices |
| GET | `/documents/{id}/text` | Extracted text per page or sheet |
| GET | `/documents/{id}/file` | Original file (download) |
| POST | `/documents/{id}/reprocess` | Reprocess one document |
| POST | `/documents/reprocess-failed` | Requeue every failed or stuck document |
| GET | `/invoices` | Keyword filtering: `q`, `supplier`, `customer`, `invoice_number`, `currency`, `status`, `needs_review`, `date_from`, `date_to`, `min_total`, `max_total`, `document_id`, `sort`, pagination |
| GET, PATCH | `/invoices/{id}` | Extracted result with issues and confidence; manual correction (re-validates, writes a revision) |
| POST | `/invoices/{id}/approve` | Reviewer sign-off |
| GET | `/invoices/{id}/history` | Revisions with field-level diffs |
| GET | `/search?q=&mode=keyword\|semantic\|hybrid` | Search; hybrid fuses both rankings (reciprocal rank fusion) |
| GET | `/cross-checks` | Same invoice in several documents (PDF-PDF, PDF-Excel), field by field |
| GET | `/settings/providers`; PUT `/settings/providers/{p}`; PUT `/settings/active`; POST `/settings/providers/{p}/test` | LLM and embedding providers (admin writes) |
| GET | `/stats` | Dashboard numbers |

Example:

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s localhost:8000/api/documents -H "Authorization: Bearer $TOKEN" -F files=@invoice.pdf -F files=@ledger.xlsx
curl -s "localhost:8000/api/search?q=wheelchair%20Dhaka&mode=hybrid" -H "Authorization: Bearer $TOKEN"
```

Extracted invoice (shape of `GET /api/invoices/{id}`, abridged):

```json
{
  "invoice_number": "INV-2025-00279",
  "invoice_date": "2025-10-10",
  "supplier_name": "Northwind Traders",
  "customer_name": "Green Valley School",
  "subtotal": "2608.98",
  "tax": "391.35",
  "total": "3000.33",
  "currency": "USD",
  "line_items": [{"description": "Printer paper A3", "quantity": "1.00", "unit_price": "7.05", "amount": "7.05"}],
  "confidence": {"invoice_number": 0.98, "tax": 0.95, "customer_name": 0.97},
  "needs_review": false,
  "issues": []
}
```

Missing values are `null`, never guessed.

## Validation rules

| Code | Severity | Rule |
|---|---|---|
| `MISSING_FIELD` | error / warning | Invoice number, date, supplier, total required; customer, subtotal, currency recommended |
| `TOTAL_MISMATCH` | error | subtotal + tax differs from total (tolerance 0.01 or 0.5%) |
| `LINE_ITEM_MISMATCH` | error | quantity x unit price differs from the line amount |
| `LINE_ITEMS_SUM_MISMATCH` | error | line items do not add up to the subtotal (or total) |
| `NEGATIVE_AMOUNT`, `TAX_EXCEEDS_TOTAL` | error | Impossible amounts |
| `TAX_RATE_IMPLAUSIBLE` | warning | Tax above 40% of subtotal |
| `FUTURE_DATE` / `IMPLAUSIBLE_DATE` | error / warning | Date in the future or before 2000 |
| `UNKNOWN_CURRENCY` | warning | Not an ISO 4217 code |
| `LOW_CONFIDENCE` | warning | Model confidence below 0.6 |
| `UNGROUNDED_VALUE` | warning | Value not found in the document text (possible hallucination) |
| `DUPLICATE_INVOICE` | error / warning | Same supplier and invoice number seen before (same document: error) |
| `CROSS_DOC_MISMATCH` | error | Same invoice in another document with different values |

An invoice needs review when it has any error, or a warning on a money field. The reviewer corrects values in the UI (each change is versioned) and approves.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `JWT_SECRET`, `ENCRYPTION_KEY` | dev values | Must be set for any real use |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | | First admin, created on first start |
| `MAX_FILE_MB` / `MAX_FILES_PER_UPLOAD` / `MAX_PAGES` | 50 / 50 / 2000 | Upload limits |
| `OCR_DPI` / `OCR_THREADS` | 300 / 4 | OCR quality and parallelism per job |
| `LLM_CONCURRENCY` / `LLM_TIMEOUT_S` | 4 / 120 | Parallel LLM calls per job and timeout |
| `COOKIE_SECURE` | false | Set true behind HTTPS |

## Limitations and next steps

- Tesseract is configured for English; other scripts need extra language packs (`tesseract-ocr-ben` for Bangla).
- Handwriting and very low-resolution photos remain hard for Tesseract; a vision-capable LLM pass on low-confidence pages is the natural next step.
- Schema is created on startup; production would use Alembic migrations.
- Files live on a Docker volume; production would use object storage with signed URLs.
