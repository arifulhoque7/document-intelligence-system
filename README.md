# Document Intelligence System

An AI-powered system that reads business documents (digital and scanned PDF, JPG, PNG, TIFF, XLSX, XLS, CSV), extracts invoice data as structured JSON, validates it, cross-verifies the same invoice across documents (PDF-PDF, PDF-Excel), and makes everything searchable through a REST API and a web interface.

| | |
|---|---|
| **Backend** | Python 3.12, FastAPI, Celery workers on Redis, SQLAlchemy 2 |
| **Documents** | PyMuPDF (PDF text layer), Tesseract 5 (OCR), pandas + openpyxl + xlrd (spreadsheets) |
| **AI** | Pluggable LLM providers chosen in the UI: Claude, OpenAI, Gemini, Ollama (local). Strict JSON-schema extraction, grounding check |
| **Data** | PostgreSQL 16 + pgvector: full-text keyword search, semantic search, hybrid ranking |
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS v4, shadcn-style components, light and dark themes |
| **Delivery** | Docker Compose (5 services), 73 automated tests, an evaluation harness with measured results |
| **Not tested** | Live Claude, OpenAI and Gemini calls (only the local Ollama model ran end to end), scale-out and load, real company documents, non-English text, Safari/Firefox/mobile, security scanning. Full list of 27 gaps: [8.5 Not tested](#85-not-tested) |

## Contents

1. [Assignment coverage](#1-assignment-coverage)
2. [Screenshots](#2-screenshots)
3. [Installation](#3-installation)
4. [Architecture](#4-architecture)
5. [Architecture decision records](#5-architecture-decision-records)
6. [API](#6-api)
7. [Validation rules](#7-validation-rules)
8. [Testing and QA](#8-testing-and-qa)
9. [Evaluation results](#9-evaluation-results)
10. [Security](#10-security)
11. [Scaling, limitations and next steps](#11-scaling-limitations-and-next-steps)
12. [Project structure](#12-project-structure)
13. [Configuration](#13-configuration)

Further reading: [docs/QA_HANDOFF.md](docs/QA_HANDOFF.md) (QA handoff), [docs/database-schema.md](docs/database-schema.md) (column-level notes), [docs/schema.sql](docs/schema.sql) (generated DDL), [eval/results/report.md](eval/results/report.md), [eval/results/benchmark_large.md](eval/results/benchmark_large.md), [docs/test-results.txt](docs/test-results.txt), [AI_DISCLOSURE.md](AI_DISCLOSURE.md).

## 1. Assignment coverage

| Task | Where it lives |
|---|---|
| 1. Document processing (PDF, images, TIFF, XLSX, XLS, CSV; multi-page, multi-sheet, poor quality, corrupted) | `backend/app/processing/` ([pipeline](#43-processing-pipeline)) |
| 2. AI extraction to JSON, nulls instead of invented values | `backend/app/llm/` ([ADR-005](#adr-005-strict-json-schema-with-nullable-fields), [ADR-006](#adr-006-grounding-check-against-the-source-text)) |
| 3. Validation and manual-review flags | `backend/app/services/validation.py` ([rules](#7-validation-rules)) |
| 4. REST API with background processing and reprocessing | `backend/app/api/`, `backend/app/worker.py` ([API](#6-api)) |
| 5. Database, keyword filtering, semantic search | `backend/app/models.py`, `backend/app/services/search.py` ([data model](#46-data-model)) |
| 6. React/Next.js interface | `frontend/` ([screenshots](#2-screenshots)) |
| 7. Tests and evaluation with measured metrics | `backend/tests/`, `eval/` ([testing](#8-testing-and-qa), [results](#9-evaluation-results)) |
| Scenario extra: PDF-PDF and PDF-Excel cross verification | `backend/app/services/invoices.py`, Cross-checks page |

## 2. Screenshots

| Dashboard (light) | Dashboard (dark) |
|---|---|
| ![Dashboard](frontend/docs/screenshots/dashboard-light.png) | ![Dashboard dark](frontend/docs/screenshots/dashboard-dark.png) |
| **Invoice review** | **Documents** |
| ![Invoice detail](frontend/docs/screenshots/invoice-detail-light.png) | ![Documents](frontend/docs/screenshots/documents-light.png) |
| **Cross-checks (PDF vs Excel)** | **Documents (dark)** |
| ![Cross-checks](frontend/docs/screenshots/cross-checks-light.png) | ![Documents dark](frontend/docs/screenshots/documents-dark.png) |

## 3. Installation

### 3.1 Installation flow

```mermaid
flowchart TD
    A[Install Docker Desktop<br/>or Docker Engine + Compose v2] --> B[Clone the repository]
    B --> C[cp .env.example .env<br/>set JWT_SECRET, ENCRYPTION_KEY, ADMIN_PASSWORD]
    C --> D[docker compose up --build -d]
    D --> E{All 5 services healthy?<br/>docker compose ps}
    E -- no --> T[See troubleshooting 3.6]
    E -- yes --> F[Open http://localhost:3000<br/>log in as ADMIN_EMAIL]
    F --> G[Settings: add an API key<br/>Claude, OpenAI or Gemini, or point Ollama at your host]
    G --> H[Press Test, then choose the active LLM<br/>and the active embedding provider]
    H --> I[Dashboard: upload documents]
    I --> J[Review flagged invoices, correct, approve]
    I --> K[Optional: run tests and the evaluation]
```

### 3.2 Prerequisites

| Need | Version | Notes |
|---|---|---|
| Docker + Compose | Docker 24+, Compose v2 | Everything else runs in containers |
| Free ports | 3000, 8000, 5433, 6379 | All bound to 127.0.0.1 only |
| An LLM | any one | API key for Claude, OpenAI or Gemini, or a local [Ollama](https://ollama.com) |
| Embeddings (for semantic search) | any one | OpenAI, Gemini or Ollama (`nomic-embed-text`). Claude has no embeddings API |

### 3.3 Quick start with Docker

```bash
git clone git@github.com:arifulhoque7/document-intelligence-system.git
cd document-intelligence-system

cp .env.example .env
# Fill in the secrets. To generate them:
python3 -c "import secrets;print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import os,base64;print('ENCRYPTION_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())"

docker compose up --build -d
docker compose ps          # db, redis, api, worker, web should be running / healthy
curl localhost:8000/health # {"status":"ok","database":"ok","redis":"ok"}
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger UI) | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

### 3.4 First-run configuration

1. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`. The admin is created on the first start.
2. Open **Settings**. For each provider you want, paste the key (or, for Ollama, set the base URL to `http://host.docker.internal:11434`), adjust the model if needed and press **Save**, then **Test**.
3. Choose the **active LLM** and the **active embedding provider**. Keys are encrypted at rest and only ever shown masked (`sk-…1234`).
4. Upload files on the **Dashboard**. Spreadsheets with invoice columns are processed without the LLM, so they work even before a key is set.
5. Optional: under **Settings > Users** create reviewer accounts (reviewers cannot change providers or users).

Default models: Claude `claude-opus-5-5` (low effort), OpenAI `gpt-5-mini` + `text-embedding-3-small`, Gemini `gemini-2.5-flash` + `gemini-embedding-001`, Ollama `qwen2.5:7b` + `nomic-embed-text`. All are editable per provider.

Scale processing with `docker compose up -d --scale worker=4`.

### 3.5 Local development (app outside Docker)

```bash
docker compose up -d db redis                  # Postgres on 127.0.0.1:5433, Redis on 127.0.0.1:6379
brew install tesseract                         # Debian/Ubuntu: apt-get install tesseract-ocr

cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp ../.env .env
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/celery -A app.worker worker --loglevel=INFO --pool=threads --concurrency=4

cd ../frontend
npm ci
npm run dev                                    # http://localhost:3000, proxies /api to API_URL (default http://localhost:8000)
```

### 3.6 Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `bind: address already in use` on 5432/5433/6379 | Another Postgres or Redis is running. Stop it or change the host port in `docker-compose.yml` (and `DATABASE_URL` for local dev) |
| Celery on macOS crashes with `ValueError: not enough values to unpack` | Billiard's prefork pool on macOS. Run the worker with `--pool=threads` (Docker on Linux is unaffected) |
| Documents fail with "No active LLM provider" | Configure and activate a provider in Settings, then press **Retry failed or stuck** on Documents |
| Ollama unreachable from Docker | Use `http://host.docker.internal:11434` as the base URL and make sure Ollama listens on all interfaces (`OLLAMA_HOST=0.0.0.0`) |
| Semantic search returns 503 | No embedding provider is active; hybrid search falls back to keyword automatically |
| A document stays queued after a worker crash | Jobs with no progress for 10 minutes can be requeued from the UI or `POST /api/documents/reprocess-failed` |

## 4. Architecture

### 4.1 System context

```mermaid
flowchart LR
    U([Reviewer / admin<br/>browser]) -->|HTTPS| W[Next.js web<br/>UI + runtime /api proxy]
    W -->|same-origin /api/*<br/>httpOnly cookie| A[FastAPI API]
    S([Scripts / integrations]) -->|Bearer token| A
    A -->|SQL| P[(PostgreSQL 16<br/>+ pgvector)]
    A -->|enqueue| R[(Redis<br/>Celery broker)]
    A -->|stream upload| F[(File storage<br/>volume)]
    R --> K[Celery workers<br/>N replicas]
    K --> F
    K --> P
    K -->|text + OCR| T[PyMuPDF, Tesseract 5,<br/>pandas, openpyxl, xlrd]
    K -->|JSON-schema extraction| L{{LLM provider<br/>Claude / OpenAI / Gemini / Ollama}}
    K -->|768-d vectors| E{{Embedding provider<br/>OpenAI / Gemini / Ollama}}
    A -->|query vector| E
```

The API never runs OCR or LLM calls. It stores the upload, writes a `documents` row, enqueues a job and returns `202`. Workers do the slow work and record every stage in `processing_events`; the UI polls the document while it is active.

### 4.2 Deployment (Docker Compose)

```mermaid
flowchart TB
    subgraph host [Host: only 127.0.0.1 ports exposed]
        subgraph net [compose network]
            web["web<br/>node:22-alpine, non-root<br/>:3000"]
            api["api<br/>python:3.12-slim + tesseract, non-root<br/>:8000, healthcheck /health"]
            worker["worker x N<br/>same image as api<br/>celery worker"]
            db[("db<br/>pgvector/pgvector:pg16<br/>:5433 -> 5432")]
            redis[("redis<br/>redis:7-alpine<br/>:6379")]
        end
        vol1[(pgdata volume)]
        vol2[(storage volume)]
    end
    web -->|"API_URL=http://api:8000"| api
    api --> db
    api --> redis
    worker --> redis
    worker --> db
    api --- vol2
    worker --- vol2
    db --- vol1
    worker -.->|host.docker.internal| ollama([Ollama on host, optional])
```

Start order is enforced by health checks: `db` and `redis` healthy, then `api` (creates the schema and the first admin), then `worker` and `web`.

### 4.3 Processing pipeline

```mermaid
flowchart TD
    Q[queued] --> D{Detect type<br/>by magic bytes}
    D -->|pdf| PDF[Per page: text layer.<br/>Under 30 alphanumerics: render 300 dpi + OCR<br/>OCR in a thread pool, bounded queue]
    D -->|jpg / png / tiff| IMG[Every frame: grayscale, upscale, autocontrast,<br/>denoise, OCR. Low confidence: rotation fix,<br/>raw image and other layout modes]
    D -->|xlsx / xls / csv| XL[Every sheet with pandas]
    D -->|anything else| X[failed: unsupported content]
    PDF --> SEG[Segment pages into invoice chunks:<br/>a new chunk when the invoice number changes]
    IMG --> SEG
    XL --> MAP{Header row names<br/>invoice columns?}
    MAP -->|yes| DET[Deterministic column mapping<br/>exact values, no LLM]
    MAP -->|no| LLM
    SEG --> LLM[LLM extraction per chunk<br/>strict JSON schema, nulls allowed,<br/>bounded concurrency]
    LLM --> G[Grounding: value must appear in source text,<br/>otherwise confidence capped at 0.3]
    DET --> V
    G --> V[Validation rules, duplicates,<br/>cross-document comparison]
    V --> EMB[Embeddings, best effort]
    EMB --> R{Any invoice flagged?}
    R -->|yes| NR[needs_review]
    R -->|no| C[completed]
```

### 4.4 Request flow: upload to reviewed invoice

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Next.js
    participant API as FastAPI
    participant DB as Postgres
    participant Q as Redis
    participant W as Celery worker
    participant LLM as LLM provider

    User->>Web: drop files
    Web->>API: POST /api/documents (multipart, streamed)
    API->>API: size cap, magic-byte type check, random storage name
    API->>DB: insert documents (queued) + event
    API->>Q: enqueue process_document(id)
    API-->>Web: 202 accepted / rejected per file
    loop every 2 s while active
        Web->>API: GET /api/documents/{id}
        API-->>Web: status, progress, events
    end
    Q->>W: deliver job (acks_late)
    W->>DB: pages (text, OCR confidence)
    W->>LLM: chunk text + JSON schema
    LLM-->>W: invoices JSON
    W->>W: Pydantic validation, grounding, rules, cross-checks
    W->>LLM: embeddings
    W->>DB: invoices, issues, revision v1, events, status
    User->>Web: open flagged invoice, correct a field
    Web->>API: PATCH /api/invoices/{id} (changed fields only)
    API->>DB: apply, re-validate, revision v2, re-embed
    User->>Web: approve
    Web->>API: POST /api/invoices/{id}/approve
```

### 4.5 States

```mermaid
stateDiagram-v2
    direction LR
    state "Document" as doc {
        [*] --> queued: upload
        queued --> processing: worker picks up
        processing --> completed: all invoices clean
        processing --> needs_review: any invoice flagged or none found
        processing --> failed: corrupt / unsupported / LLM error
        processing --> queued: transient LLM error, retry with backoff
        failed --> queued: reprocess
        queued --> queued: stuck over 10 min, requeue
        needs_review --> completed: last flagged invoice approved or fixed
    }
```

```mermaid
stateDiagram-v2
    direction LR
    state "Invoice" as inv {
        [*] --> extracted: no errors
        [*] --> needs_review: rule error or money warning
        needs_review --> extracted: correction clears issues
        extracted --> needs_review: correction or new cross-document mismatch
        extracted --> approved: reviewer approves
        needs_review --> approved: reviewer approves
        approved --> extracted: edited after approval
    }
```

### 4.6 Data model

```mermaid
erDiagram
    users ||--o{ documents : uploads
    users ||--o{ invoice_revisions : edits
    documents ||--o{ document_pages : "pages / sheets"
    documents ||--o{ invoices : contains
    documents ||--o{ processing_events : history
    invoices ||--o{ invoice_revisions : versions
    invoices ||--o{ validation_issues : flags

    documents {
        uuid id PK
        varchar file_type "from content"
        varchar sha256
        varchar status
        int progress
        text error
        int attempts
        int processing_ms
    }
    document_pages {
        int page_no
        text text
        varchar method "text, ocr, sheet"
        float ocr_confidence
        tsvector tsv "GIN"
    }
    invoices {
        uuid id PK
        varchar invoice_number
        varchar invoice_number_norm "match key"
        date invoice_date
        varchar supplier_name
        varchar customer_name
        numeric subtotal
        numeric tax
        numeric total
        char currency
        jsonb line_items
        jsonb confidence
        bool needs_review
        vector embedding "768, HNSW"
        tsvector search_tsv "weighted, GIN"
    }
    invoice_revisions {
        int version
        varchar source "extraction, manual, approval"
        jsonb data
        jsonb changes
    }
    validation_issues {
        varchar code
        varchar field
        varchar severity
        text message
    }
    processing_events {
        varchar stage
        varchar status
        text message
        int duration_ms
    }
    provider_settings {
        varchar provider PK
        text api_key_enc "AES-256-GCM"
        bool active_llm
        bool active_embedding
    }
```

Money is `NUMERIC(18,2)`, search columns are generated (`GENERATED ALWAYS AS ... STORED`) so they never drift from the data, and every change to an invoice is kept as a full snapshot plus a field diff. Details: [docs/database-schema.md](docs/database-schema.md).

### 4.7 Backend layering

```mermaid
flowchart TB
    api["api/<br/>routers, auth dependencies, serializers<br/>HTTP only, no business rules"]
    worker["worker.py<br/>Celery tasks"]
    services["services/<br/>pipeline, validation, invoices (corrections, approval, cross-checks),<br/>search, storage"]
    processing["processing/<br/>detect, loaders (PDF, OCR, sheets), segment, sheets mapping, normalize"]
    llm["llm/<br/>base.py contract + schema, prompts.py,<br/>providers/claude, openai, gemini, ollama"]
    core["core/ + models.py<br/>config, DB engine, security (bcrypt, JWT, AES-GCM), ORM"]
    api --> services
    worker --> services
    services --> processing
    services --> llm
    processing --> core
    llm --> core
    services --> core
```

Dependencies point inwards only. The same services run from the API, the worker, the tests and the evaluation. Adding an LLM vendor is one file in `llm/providers/` implementing `complete_json` and `embed`, plus one registry line.

### 4.8 Frontend structure

```mermaid
flowchart LR
    pages["app/(app)/*<br/>dashboard, documents, review, invoices,<br/>search, cross-checks, settings"] --> comps["components/<br/>shell, documents, invoices, settings, ui primitives"]
    pages --> hooks["hooks/<br/>useApi, usePoll, useSession, use-appearance"]
    hooks --> lib["lib/api.ts<br/>typed fetch, ApiError, 401 redirect"]
    lib --> proxy["app/api/[...path]/route.ts<br/>runtime proxy: streams bodies, forwards cookies"]
    proxy --> backend[(FastAPI)]
```

### 4.9 Failure handling

| Failure | Behaviour |
|---|---|
| Corrupted, encrypted, empty, blank or oversized file | Clean `ProcessingError` with a user-safe message; document `failed`; never retried automatically |
| LLM 429 / 5xx / timeout / connection error | Transient: Celery retries after 15 s, 30 s, 60 s, then `failed` with the reason |
| LLM 4xx, refusal, invalid JSON, schema violation | Permanent: `failed` with the provider's message; reprocess after fixing settings |
| Worker killed mid-job | `acks_late` + `reject_on_worker_lost` return the job to the queue; jobs with no progress for 10 minutes can be requeued |
| Same job delivered twice (broker or machine restart) | The worker skips any document that is no longer queued or processing, so a duplicate message never reprocesses a finished document or wipes reviewer corrections |
| Embedding provider down | Document still completes with a warning event; hybrid search falls back to keyword |
| Unexpected exception | Stack trace logged; document `failed` with a generic message (no internals leaked) |

## 5. Architecture decision records

Each record states the context, the decision, the alternatives that were weighed and the consequences accepted.

### ADR-001: One backend language: Python FastAPI + Celery

- **Status**: accepted
- **Context**: The brief suggests Node.js/NestJS with Redis/BullMQ, and also Python OCR tools and pandas/openpyxl. Every heavy step (OCR, PDF parsing, spreadsheets, LLM SDKs) is Python-first.
- **Decision**: FastAPI for the API, Celery on Redis for background jobs, all in Python.
- **Alternatives**: NestJS + BullMQ with a Python OCR microservice; all-Node with tesseract.js and SheetJS.
- **Consequences**: One runtime, one set of models, no internal HTTP hop between "API language" and "OCR language". Celery gives the same queue semantics as BullMQ (retries with backoff, late acks, horizontal workers). The deviation from the suggested NestJS stack is deliberate and recorded here.

### ADR-002: Asynchronous processing with late-acknowledged jobs

- **Status**: accepted
- **Context**: A 1000-page scanned PDF can take many minutes; HTTP requests must stay fast and workers can die.
- **Decision**: Upload returns `202`; one Celery task per document with `acks_late`, `reject_on_worker_lost`, prefetch 1, retry with exponential backoff only for transient LLM errors. Progress and history go to `processing_events`; the UI polls.
- **Alternatives**: synchronous processing; WebSockets/SSE for progress.
- **Consequences**: API latency is independent of document size, and workers scale with `--scale worker=N`. Redis re-delivers unacknowledged jobs only after its visibility timeout, so stale-job recovery (10 minutes without progress) is exposed in the UI and API. Polling is simpler than push and works behind any proxy.

### ADR-003: PostgreSQL + pgvector as the single data store

- **Status**: accepted
- **Context**: We need metadata, text, results, issues, history, keyword search and semantic search.
- **Decision**: PostgreSQL 16 with pgvector: GIN-indexed `tsvector` columns for keyword search, an HNSW cosine index for vectors, hybrid ranking by reciprocal rank fusion.
- **Alternatives**: MongoDB; a separate vector database (Qdrant, Pinecone); Elasticsearch.
- **Consequences**: One transaction covers an invoice and its vector, so they never drift; filters and similarity combine in one engine. A dedicated vector DB is a later step only if vectors reach a scale Postgres cannot serve.

### ADR-004: Text layer first, OCR only where needed, deterministic spreadsheets

- **Status**: accepted
- **Context**: OCR is slow and lossy; many PDFs have a text layer; exported ledgers have exact values.
- **Decision**: Per PDF page, use the text layer when it has at least 30 alphanumerics, otherwise render at 300 dpi and OCR. Images get clean-up and confidence-driven retries. Spreadsheets whose header row names invoice columns are mapped deterministically; only unrecognised sheets go to the LLM.
- **Alternatives**: OCR everything; send everything, including spreadsheets, to the LLM; a vision LLM for every page.
- **Consequences**: Digital PDFs read at about 200 pages/s, mixed PDFs are handled page by page, and spreadsheets are free, instant and exact. OCR quality limits scanned accuracy (see [results](#9-evaluation-results)).

### ADR-005: Strict JSON schema with nullable fields

- **Status**: accepted
- **Context**: The brief requires structured JSON and no invented values.
- **Decision**: One Pydantic schema (`ExtractionResult`) is sent as a strict JSON schema to every provider (Claude structured outputs, OpenAI `json_schema` strict, Gemini response schema, Ollama `format`). Every field is required but nullable, the prompt says "null if not printed", and the response is validated again with Pydantic.
- **Alternatives**: free-form JSON parsed with regexes; function calling per field.
- **Consequences**: The model can say "not present" instead of guessing; malformed output becomes a clear, retryable error rather than bad data.

### ADR-006: Grounding check against the source text

- **Status**: accepted
- **Context**: Model confidence is not reliable evidence of correctness.
- **Decision**: After extraction, each invoice number, party name and amount must appear in the source text (amounts in several print formats). If not, its confidence is capped at 0.3 and an `UNGROUNDED_VALUE` issue is raised. Values a reviewer typed are trusted.
- **Alternatives**: trust self-reported confidence; a second LLM pass to verify.
- **Consequences**: Hallucinated values are caught cheaply and deterministically. OCR misreads that are consistent in the text itself (for example `SI/` read as `S1/`) still pass, which is why validation rules and human review remain.

### ADR-007: Provider-neutral LLM layer configured at runtime

- **Status**: accepted
- **Context**: The user wanted to choose the provider from a settings page with masked keys; vendors and prices change.
- **Decision**: An `LLMProvider` protocol (`complete_json`, `embed`) with one adapter per vendor; each adapter maps its SDK errors to `LLMError(transient=...)`. Active provider, model and keys live in `provider_settings`, editable by admins in the UI.
- **Alternatives**: one hard-coded provider configured by environment variables; a third-party abstraction library.
- **Consequences**: Switching providers is a UI action, and adding one is a single file. Keys in the database require encryption at rest ([ADR-010](#adr-010-secrets-encrypted-at-rest-sessions-in-httponly-cookies)).

### ADR-008: Embeddings from a provider, pinned to 768 dimensions

- **Status**: accepted
- **Context**: Claude has no embeddings API; models have different native sizes.
- **Decision**: A separate "active embedding provider" (OpenAI, Gemini or Ollama), always requested at 768 dimensions. The model name is stored per row; changing the provider or model re-embeds every invoice in a background job; semantic queries only compare vectors from the current model.
- **Alternatives**: a local embedding model inside the worker; native dimensions with one column per model.
- **Consequences**: One column and one index for every provider. Semantic search depends on an external service, so hybrid search degrades to keyword when it is unavailable.

### ADR-009: Segment large documents by invoice number

- **Status**: accepted
- **Context**: A 1000-page PDF may hold hundreds of invoices; one LLM call per document would overflow context, one per page would split multi-page invoices.
- **Decision**: Start a new chunk when a page shows a different invoice number; pages without one (continuations) join the current chunk; chunks are capped at 60k characters. The LLM may still return several invoices per chunk. Chunks are extracted with bounded concurrency.
- **Alternatives**: one call per page; fixed page windows; LLM-based boundary detection.
- **Consequences**: Requests stay bounded and parallel, and multi-page invoices stay whole (1005-page benchmark: 480 chunks for 480 invoices). When OCR misreads a number, two invoices can share a chunk, which the list-shaped output still handles.

### ADR-010: Secrets encrypted at rest, sessions in httpOnly cookies

- **Status**: accepted
- **Context**: API keys are entered in the UI; the brief asks for strong security.
- **Decision**: Provider keys are AES-256-GCM encrypted with `ENCRYPTION_KEY`, never returned (masked only), editable by admins only. Sessions are JWTs in an httpOnly, SameSite=Strict cookie; the Next.js runtime proxy keeps the API same-origin. Bearer tokens are accepted for scripts.
- **Alternatives**: keys only in environment variables; tokens in localStorage.
- **Consequences**: A database leak alone does not expose keys, and the web app never stores the session token where page scripts can read it (login also returns the token in the body for API clients; the browser ignores it). `ENCRYPTION_KEY` rotation would need a re-encrypt step (not built).

### ADR-011: Human review as a first-class step

- **Status**: accepted
- **Context**: No extractor is perfect; financial data needs accountability.
- **Decision**: Any validation error, or a warning on a money field, sets `needs_review`. Reviewers correct values (only changed fields are sent), corrections are marked certain, everything is re-validated and versioned (`invoice_revisions`), and approval is an explicit, recorded action. Cross-document checks re-validate the earlier record too.
- **Alternatives**: auto-accept above a confidence threshold; overwrite results in place.
- **Consequences**: A full audit trail, and the review queue is the main working screen. About 10% of fully correct invoices were still sent to review in the evaluation (false alarms), the price of conservative rules.

### ADR-012: Measure with a reproducible, API-level evaluation

- **Status**: accepted
- **Context**: The brief asks for actual measured accuracy, time, success and failure rates.
- **Decision**: A synthetic generator renders invoices from known truth in every format and quality (seeded, reproducible); 20 real scanned receipts come from ICDAR 2019 SROIE. `eval/run_eval.py` drives the real stack through its public API and scores fields, detection, line items, rates and time. Tests use a deterministic fake LLM.
- **Alternatives**: hand-labelled samples only; unit-level scoring without the full stack.
- **Consequences**: Numbers reflect the deployed system, can be rerun for any provider, and the raw run is saved so scoring changes do not need new LLM calls.

## 6. API

All endpoints are under `/api` and need a session (cookie from `/api/auth/login`, or `Authorization: Bearer <token>`). Interactive docs at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login`, `/auth/logout`; GET `/auth/me` | Session |
| GET, POST | `/auth/users` | List and create users (admin) |
| POST | `/documents` | Upload many files (multipart field `files`); `202` with accepted and rejected files |
| GET | `/documents` | List: `status`, `file_type`, `q` (filename or full text), pagination |
| GET | `/documents/{id}` | Status, progress, processing history, pages, invoices |
| GET | `/documents/{id}/text` | Extracted text per page or sheet |
| GET | `/documents/{id}/file` | Original file (attachment) |
| POST | `/documents/{id}/reprocess` | Reprocess one document |
| POST | `/documents/reprocess-failed` | Requeue every failed or stuck document |
| GET | `/invoices` | Keyword filtering: `q`, `supplier`, `customer`, `invoice_number`, `currency`, `status`, `needs_review`, `date_from`, `date_to`, `min_total`, `max_total`, `document_id`, `sort`, pagination |
| GET, PATCH | `/invoices/{id}` | Result with issues and confidence; manual correction |
| POST | `/invoices/{id}/approve` | Reviewer sign-off |
| GET | `/invoices/{id}/history` | Revisions with field-level diffs |
| GET | `/search?q=&mode=keyword\|semantic\|hybrid` | Search |
| GET | `/cross-checks?only_mismatches=` | Same invoice in several documents, field by field |
| GET / PUT / PUT / POST | `/settings/providers`, `/settings/providers/{p}`, `/settings/active`, `/settings/providers/{p}/test` | Providers (admin writes) |
| GET | `/stats` | Dashboard numbers |

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s localhost:8000/api/documents -H "Authorization: Bearer $TOKEN" -F files=@invoice.pdf -F files=@ledger.xlsx
curl -s "localhost:8000/api/search?q=wheelchair%20Dhaka&mode=hybrid" -H "Authorization: Bearer $TOKEN"
```

Extracted invoice (`GET /api/invoices/{id}`, abridged). Missing values are `null`, never guessed:

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

## 7. Validation rules

| Code | Severity | Rule |
|---|---|---|
| `MISSING_FIELD` | error / warning | Invoice number, date, supplier and total required; customer, subtotal and currency recommended |
| `TOTAL_MISMATCH` | error | subtotal + tax differs from total (tolerance 0.01 or 0.5%) |
| `LINE_ITEM_MISMATCH` | error | quantity x unit price differs from the line amount |
| `LINE_ITEMS_SUM_MISMATCH` | error | line items do not add up to the subtotal (or total) |
| `NEGATIVE_AMOUNT`, `TAX_EXCEEDS_TOTAL` | error | Impossible amounts |
| `TAX_RATE_IMPLAUSIBLE` | warning | Tax above 40% of subtotal |
| `FUTURE_DATE`, `IMPLAUSIBLE_DATE` | error, warning | Date in the future or before 2000 |
| `UNKNOWN_CURRENCY` | warning | Not an ISO 4217 code |
| `LOW_CONFIDENCE` | warning | Model confidence below 0.6 |
| `UNGROUNDED_VALUE` | warning | Value not found in the document text |
| `DUPLICATE_INVOICE` | error / warning | Same supplier and number seen before (in the same document: error) |
| `CROSS_DOC_MISMATCH` | error | Same invoice in another document with different values |

## 8. Testing and QA

Everything below was run on this codebase; nothing is estimated. What was **not** tested is listed just as clearly in [8.5 Not tested](#85-not-tested). The full QA handoff, with step-by-step test cases per feature, the fixes found during QA and what was **not** covered, is in [docs/QA_HANDOFF.md](docs/QA_HANDOFF.md).

### 8.1 How to run

```bash
docker compose up -d db redis
cd backend && .venv/bin/python -m pytest -v     # 73 passed, output in docs/test-results.txt
cd ../frontend && npm test && npm run build     # invoice form diff check, type check, lint
```

Backend tests run against a real PostgreSQL database (`docintel_test`, created by `backend/initdb/`), execute Celery tasks inline, and replace the network LLM with a deterministic fake that parses the synthetic layouts, so they are fast (about 27 s), free and repeatable. Test files are rendered on the fly by `devtools/synth.py`.

### 8.2 Automated tests (73)

| Suite | Tests | What is proven |
|---|---|---|
| `test_processing.py` | 19 | Types detected by content even with the wrong extension; digital PDFs use the text layer; scanned PDFs fall back to OCR (confidence above 70%, number and total read); OCR on light and heavy degraded photos; a 40-item invoice spanning pages stays one chunk; a 4-invoice PDF splits into 4; every TIFF frame is read, totals on the last page; XLSX with two sheets, XLS and CSV map every field exactly; an unrecognised sheet layout is left for the LLM; truncated PDF, blank image, corrupt PNG, corrupt XLSX, empty CSV and password-protected PDF fail with clean messages; the page limit is enforced |
| `test_normalize_validation.py` | 21 | Amount parsing for 10 formats (`1,234.50`, `1.234,50`, `(12.00)`, `BDT 3,000`, empty, text); dates in several formats with day-first ambiguity flagged; currency symbols and invoice-number keys; a clean invoice raises nothing; missing fields, total mismatch, line-item and sum mismatches, rounding tolerance, negative, future, implausible tax and unknown currency; invoices without tax; grounding caps confidence on values not in the text; reviewer-typed values are not flagged |
| `test_llm.py` | 12 | The schema is strict at every level (closed objects, all keys required); invalid JSON and schema violations become errors; a missing key fails before any call; nulls stay null and are never filled in; a hallucinated supplier loses confidence; Claude 429 is transient and 400 permanent; Claude refusals are reported and requests carry structured output, low effort and fallbacks; OpenAI timeouts are transient; Claude has no embeddings; the Gemini schema is accepted by the Google SDK |
| `test_api.py` | 21 | Login required; login rate limit; reviewers cannot change settings; security headers; a mixed batch (PDF, bundle, XLSX, CSV, a fake PDF with `../../` in its name) processes end to end with correct fields, events, text and attachment download; duplicates flagged; a wrong total is flagged, corrected, re-validated, versioned and approved; bad corrections refused (422); keyword filters and sort whitelist; keyword, semantic and hybrid search; semantic without an embedding provider (503) and hybrid fallback; PDF vs Excel cross-check flags both records; LLM failure then bulk reprocess; transient failure gives up cleanly; corrupted, empty and oversized uploads; spreadsheets never call the LLM; provider keys encrypted at rest and only shown masked; a redelivered job never reprocesses a finished document or wipes a correction; a second worker skips a document another worker is processing |
| `frontend/lib/invoiceForm.test.mjs` | 1 | The invoice form sends only changed fields, with null to clear |

### 8.3 End-to-end and manual verification

| Check | How | Result |
|---|---|---|
| Full Docker stack | `docker compose up --build -d` from a clean build | 5 services running; api, db and redis healthy |
| Upload to result inside Docker | Log in through the web container's proxy, test the provider, upload a CSV and a heavily degraded scanned PDF | CSV: 3 invoices in 0.47 s. Scanned PDF: Tesseract in the container plus the LLM, all 8 fields and 4/4 line items correct in 22 s. Celery prefork pool works on Linux |
| Every screen | Playwright against the production build in light and dark: login, dashboard, documents, document detail, invoice review (edit, save, history, approve), review queue, invoices, search, cross-checks, settings | All render with real data; screenshots in [section 2](#2-screenshots) |
| Accuracy, success and failure rates | `eval/run_eval.py`: 74 labeled documents uploaded through the API | [Section 9](#9-evaluation-results) |
| Large documents | `eval/benchmark_large.py`: 1005-page digital PDF and 100-page scanned PDF | 4.8 s and 56 s; [section 9](#9-evaluation-results) |
| Recovery after a machine restart | Restarted the host with jobs pending | Found the redelivery and parallel-run bugs below; both fixed with regression tests |
| Diagrams | Parsed and rendered all 10 Mermaid diagrams with Mermaid 11 | All render |

### 8.4 Bugs found by testing (all fixed)

| Found by | Bug | Fix |
|---|---|---|
| Running OCR on a multi-page TIFF | Auto-contrast with a 1% cutoff erased all text on nearly blank pages, losing the totals on page 2 | Contrast without cutoff, plus a raw-image retry |
| Restarting the machine | Redelivered queue messages reprocessed finished documents and could wipe reviewer corrections | Worker skips documents that are not queued or processing |
| Requeueing a job that was still running | Two workers processed the same document at once and each saved its invoices, so the document showed every invoice twice | Per-document Postgres advisory lock for the whole run; a duplicate job skips, and the lock frees itself if a worker crashes |
| Killing a worker | Unacknowledged jobs stayed queued for the broker's one-hour visibility timeout | Stale-job recovery after 10 minutes, in the UI and the API |
| Testing a Gemini key from Settings | The Google SDK rejected the JSON schema; the endpoint returned a bare 500 | Schema converted to Gemini's subset; test endpoint reports any error as text |
| Uploading the same file several times | The duplicate warning was repeated once per earlier copy | Issues de-duplicated |
| Running the worker on macOS | Celery's prefork pool crashed | Threads pool for local development (documented); prefork in Docker |

### 8.5 Not tested

Read this before relying on the numbers above. Everything in this table was **not** run or **not** verified; the system may work, but there is no evidence yet.

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

## 9. Evaluation results

Reproduce:

```bash
cd backend && .venv/bin/python -m devtools.synth ../eval/dataset/synthetic && cd ..   # synthetic set with known truth
backend/.venv/bin/python eval/fetch_public.py 20                                      # 20 real scanned receipts (SROIE)
backend/.venv/bin/python eval/run_eval.py --password <admin password>                 # full run through the API
backend/.venv/bin/python eval/run_eval.py --password <admin password> --rescore       # re-score the saved run
cd backend && .venv/bin/python ../eval/benchmark_large.py                             # 1000-page benchmark
```

**Run measured on 2026-11-04** with a small local model (Ollama `qwen2.5-coder:7b`, `nomic-embed-text`), 74 documents: 54 synthetic (every format and three scan qualities, cross-check pairs, a wrong-total invoice, corrupted files) and 20 real receipts. Full report: [eval/results/report.md](eval/results/report.md).

| Metric | Value |
|---|---|
| Document success rate (valid files) | 98.6% |
| Document failure rate (valid files) | 0.0% |
| Corrupted or blank files rejected cleanly | 4 / 4 |
| Field-level extraction accuracy | 96.3% |
| Invoices with every field correct | 91.0% |
| Invoice detection recall / precision | 99.0% / 99.0% |
| Line items precision / recall / F1 | 99.1% / 96.9% / 98.0% |
| Validation and cross-verification checks | 3 / 3 pass |
| Correct invoices still sent to review | 10.6% |

| Document kind | Accuracy |
|---|---|
| Digital, multi-page and bundled PDF, TIFF, XLSX, XLS | 100% on every field |
| CSV | 100%, except customer and tax at 88.9% |
| Scanned PDF and photos | 100% on amounts, dates, supplier; invoice number 75% (OCR reads `SI/` as `S1/`) |
| Real receipts (SROIE, labeled for supplier, date, total) | date 80%, total 70%, supplier 65% |

Processing time: spreadsheets 0.5 to 1.2 s per file (p50). LLM-bound documents took a median of about 100 s, because one local GPU served the 7B model to four concurrent workers while the queue was shared with interactive testing. These times measure that laptop, not the design; a hosted model removes the bottleneck.

**Large documents** (no LLM, fresh process per run, [eval/results/benchmark_large.md](eval/results/benchmark_large.md)):

| Case | Pages | Time | Pages/s | Chunks | Peak memory |
|---|---|---|---|---|---|
| Digital PDF, 480 invoices bundled | 1005 | 4.8 s | 209 | 480 | 115 MB |
| Scanned PDF, OCR with 4 threads | 100 | 56.4 s | 1.8 | 84 | 722 MB |

Read the scanned row as: OCR, not the design, is the throughput limit (about 0.55 s per page per worker at 300 dpi), and 16 of 100 single-page invoices had their number misread, so they shared a chunk with a neighbour; the extractor still returns them as separate invoices.

## 10. Security

- **Auth**: bcrypt hashes; JWT in an httpOnly, SameSite=Strict cookie (Bearer for scripts); roles `admin` and `reviewer`; admin-only provider and user management; login rate limit of 10 attempts per IP and email per 15 minutes.
- **Uploads**: type from content, not extension; streamed size limit; file count and page limits; Pillow decompression-bomb guard; random storage names outside any web root; originals served only as attachments.
- **Secrets**: provider keys AES-256-GCM encrypted, masked in every response; `.env` git-ignored; no secrets in images.
- **LLM**: document text is delimited and declared as data, the prompt tells the model to ignore instructions inside it, output must pass a strict schema before storage.
- **Data access**: parameterised SQL only (SQLAlchemy); whitelisted sort fields; Pydantic with `extra="forbid"` on every write body; the frontend never renders API strings as HTML.
- **HTTP and runtime**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, restrictive CSP on API responses; ports bound to 127.0.0.1; non-root containers.

## 11. Scaling, limitations and next steps

- **Scale out**: more workers (`--scale worker=N`), `OCR_THREADS` per job, `LLM_CONCURRENCY` per job. Separate queues for OCR-heavy and LLM-heavy work are the next step.
- **OCR**: Tesseract is set up for English; add language packs (for example `tesseract-ocr-ben`). Handwriting and very poor photos remain hard; a vision-LLM pass on low-confidence pages is the planned improvement and would also fix misread invoice numbers.
- **Platform**: schema is created on start (production: Alembic migrations); files on a Docker volume (production: object storage with signed URLs); add tracing and per-call LLM cost accounting.
- **Security**: key rotation for `ENCRYPTION_KEY`, trusted-proxy configuration so the login limiter sees client IPs behind the web proxy, SSO.

## 12. Project structure

```
.
├── docker-compose.yml          db, redis, api, worker, web
├── .env.example
├── backend/
│   ├── Dockerfile              python:3.12-slim + tesseract, non-root
│   ├── initdb/                 creates the test database
│   ├── app/
│   │   ├── main.py             FastAPI app, security headers, health, startup
│   │   ├── worker.py           Celery app and tasks
│   │   ├── models.py           ORM: the schema
│   │   ├── core/               config, db, security
│   │   ├── api/                routers, deps, serializers
│   │   ├── services/           pipeline, validation, invoices, search, storage
│   │   ├── processing/         detect, loaders, ocr, segment, sheets, normalize
│   │   └── llm/                base, prompts, providers/{claude,openai,gemini,ollama}
│   ├── devtools/synth.py       synthetic invoice generator with ground truth
│   └── tests/                  73 tests + fake LLM
├── frontend/
│   ├── app/                    pages, runtime API proxy
│   ├── components/             shell, documents, invoices, settings, ui
│   ├── hooks/, lib/            data fetching, types, API client
│   └── docs/screenshots/
├── eval/                       run_eval.py, fetch_public.py, benchmark_large.py, results/
├── docs/                       QA_HANDOFF.md, database-schema.md, schema.sql, test-results.txt
└── AI_DISCLOSURE.md
```

## 13. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `JWT_SECRET`, `ENCRYPTION_KEY` | dev values | Must be set for any real use; `ENCRYPTION_KEY` is 32 bytes, base64 |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | | First admin, created on first start |
| `MAX_FILE_MB`, `MAX_FILES_PER_UPLOAD`, `MAX_PAGES` | 50, 50, 2000 | Upload limits |
| `OCR_DPI`, `OCR_THREADS` | 300, 4 | OCR quality and parallelism per job |
| `LLM_CONCURRENCY`, `LLM_TIMEOUT_S` | 4, 120 | Parallel LLM calls per job and timeout |
| `EMBEDDING_DIM` | 768 | Vector size for every embedding provider |
| `COOKIE_SECURE` | false | Set to true behind HTTPS |
| `CORS_ORIGINS` | empty | Only needed if the frontend is not proxied |
| `API_URL` (web) | `http://localhost:8000` | Where the Next.js proxy forwards `/api` |
