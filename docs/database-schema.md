# Database schema

PostgreSQL 16 with the `pgvector` extension. The ORM models in `backend/app/models.py` are the source of truth; `docs/schema.sql` is the generated DDL (`pg_dump --schema-only`).

```mermaid
erDiagram
    users ||--o{ documents : uploads
    users ||--o{ invoice_revisions : edits
    documents ||--o{ document_pages : "has pages / sheets"
    documents ||--o{ invoices : contains
    documents ||--o{ processing_events : "history"
    invoices ||--o{ invoice_revisions : "versions"
    invoices ||--o{ validation_issues : flags

    users {
        int id PK
        varchar email UK
        varchar password_hash "bcrypt"
        varchar role "admin | reviewer"
    }
    provider_settings {
        varchar provider PK "claude | openai | gemini | ollama"
        text api_key_enc "AES-256-GCM"
        varchar model
        varchar embedding_model
        varchar base_url
        bool active_llm
        bool active_embedding
    }
    documents {
        uuid id PK
        varchar filename "display only"
        varchar file_type "detected from content"
        bigint size_bytes
        varchar sha256 "identical-file detection"
        varchar storage_path "random name"
        varchar status "queued | processing | completed | needs_review | failed"
        int progress "0-100"
        int page_count
        text error
        int attempts
        int processing_ms
    }
    document_pages {
        bigint id PK
        uuid document_id FK
        int page_no
        varchar sheet_name
        text text "extracted text"
        varchar method "text | ocr | sheet"
        float ocr_confidence
        tsvector tsv "generated, GIN"
    }
    invoices {
        uuid id PK
        uuid document_id FK
        int seq
        varchar source_ref "pages 3-4 / sheet Jan rows 2-9"
        text source_text "text the values came from"
        varchar invoice_number
        varchar invoice_number_norm "match key"
        date invoice_date
        varchar supplier_name
        varchar customer_name
        numeric subtotal
        numeric tax
        numeric total
        char currency "ISO 4217"
        jsonb line_items
        jsonb confidence "per field 0..1"
        varchar status "extracted | needs_review | approved"
        bool needs_review
        varchar extracted_by "provider/model or spreadsheet"
        vector embedding "768, HNSW cosine"
        varchar embedding_model
        tsvector search_tsv "generated, weighted, GIN"
    }
    invoice_revisions {
        bigint id PK
        uuid invoice_id FK
        int version
        varchar source "extraction | manual | approval"
        jsonb data "full snapshot"
        jsonb changes "field: [old, new]"
        int user_id FK
    }
    validation_issues {
        bigint id PK
        uuid invoice_id FK
        varchar code
        varchar field
        varchar severity "error | warning"
        text message
    }
    processing_events {
        bigint id PK
        uuid document_id FK
        varchar stage
        varchar status "started | ok | warning | failed"
        text message
        int duration_ms
    }
```

## Design notes

- **Money** is `NUMERIC(18,2)`, never float, so validation arithmetic is exact.
- **Search columns are generated** (`GENERATED ALWAYS AS ... STORED`): `invoices.search_tsv` weights invoice number and party names (A) above the source text (B); they can never drift from the data.
- **History**: `invoice_revisions` keeps a full snapshot per change (the original extraction is version 1) plus a field-level diff and the user; `processing_events` keeps every pipeline stage with timings, across reprocessing attempts.
- **Duplicates and cross-document checks** use `invoice_number_norm` (letters and digits only, upper case) plus a normalised supplier name, indexed.
- **Indexes**: GIN on both `tsvector` columns, HNSW (`vector_cosine_ops`) on `invoices.embedding`, B-tree on status, created_at, sha256, invoice number, date, total, needs_review and every foreign key.
- **Deletes cascade** from documents to pages, invoices, issues, revisions and events.

| Table | Purpose |
|---|---|
| `documents` | One uploaded file, its processing state and metadata |
| `document_pages` | Extracted text per PDF page, image frame or spreadsheet sheet |
| `invoices` | Structured extraction result (one document can hold many invoices) |
| `validation_issues` | Current rule violations per invoice |
| `invoice_revisions` | Version history: extraction, manual corrections, approvals |
| `processing_events` | Processing history and progress per document |
| `provider_settings` | LLM and embedding provider configuration with encrypted keys |
| `users` | Accounts and roles |
