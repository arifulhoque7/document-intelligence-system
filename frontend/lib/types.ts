// Shapes returned by the FastAPI backend (see backend/app/api/serializers.py and routers).

export type Role = "admin" | "reviewer";

export interface User {
  id: number;
  email: string;
  role: Role;
}

export type DocumentStatus = "queued" | "processing" | "completed" | "needs_review" | "failed";
export type FileType = "pdf" | "image" | "tiff" | "xlsx" | "xls" | "csv" | "unknown";

export interface DocumentSummary {
  id: string;
  filename: string;
  file_type: FileType;
  size_bytes: number;
  status: DocumentStatus;
  progress: number;
  page_count: number | null;
  error: string | null;
  attempts: number;
  processing_ms: number | null;
  created_at: string | null;
  updated_at: string | null;
  invoice_count: number;
  review_count: number;
}

export interface ProcessingEvent {
  stage: string;
  status: "started" | "ok" | "warning" | "failed";
  message: string | null;
  duration_ms: number | null;
  at: string;
}

export interface DocumentPageInfo {
  page_no: number;
  sheet_name: string | null;
  method: "text" | "ocr" | "sheet";
  ocr_confidence: number | null;
  chars: number;
}

export interface DocumentDetail extends DocumentSummary {
  events: ProcessingEvent[];
  pages: DocumentPageInfo[];
  invoices: Invoice[];
}

export interface PageText {
  page_no: number;
  sheet_name: string | null;
  method: "text" | "ocr" | "sheet";
  ocr_confidence: number | null;
  text: string;
}

export interface LineItem {
  description: string | null;
  quantity: string | null;
  unit_price: string | null;
  amount: string | null;
}

export const INVOICE_FIELDS = [
  "invoice_number",
  "invoice_date",
  "supplier_name",
  "customer_name",
  "subtotal",
  "tax",
  "total",
  "currency",
] as const;
export type InvoiceField = (typeof INVOICE_FIELDS)[number];

export interface Issue {
  code: string;
  field: string | null;
  severity: "error" | "warning";
  message: string;
}

export type InvoiceStatus = "extracted" | "needs_review" | "approved";

export interface Invoice {
  id: string;
  document_id: string;
  filename: string | null;
  seq: number;
  source_ref: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  supplier_name: string | null;
  customer_name: string | null;
  // Money is sent as decimal strings to avoid float rounding.
  subtotal: string | null;
  tax: string | null;
  total: string | null;
  currency: string | null;
  line_items: LineItem[];
  confidence: Partial<Record<InvoiceField, number>>;
  status: InvoiceStatus;
  needs_review: boolean;
  extracted_by: string | null;
  has_embedding: boolean;
  issues: Issue[];
  updated_at: string | null;
}

export interface InvoiceDetail extends Invoice {
  source_text: string | null;
}

export type FieldDiff = Record<string, [unknown, unknown]>;

export interface CorrectionResult {
  changed: FieldDiff;
  invoice: InvoiceDetail;
}

export interface Revision {
  version: number;
  source: string; // extraction | manual | approval
  changes: FieldDiff | null;
  data: Record<string, unknown>;
  user_id: number | null;
  at: string;
}

export interface Paged<T> {
  total: number;
  page: number;
  items: T[];
}

export interface UploadResult {
  accepted: { id: string; filename: string; file_type: FileType; duplicate_of: string | null }[];
  rejected: { filename: string; reason: string; id?: string }[];
}

export interface Stats {
  documents: number;
  documents_by_status: Partial<Record<DocumentStatus, number>>;
  invoices: number;
  invoices_needing_review: number;
  failure_rate: number | null;
  avg_processing_ms: number | null;
}

export type SearchMode = "keyword" | "semantic" | "hybrid";

export interface SearchHit extends Invoice {
  score: number;
  snippet: string | null;
}

export interface SearchResult {
  mode: SearchMode;
  items: SearchHit[];
}

export interface CrossCheckSide {
  invoice_id: string;
  document_id: string;
  filename: string;
}

export interface CrossCheck {
  invoice_number: string;
  kind: string;
  status: "match" | "mismatch";
  differences: Record<string, [string, string]>;
  a: CrossCheckSide;
  b: CrossCheckSide;
}

export type Provider = "claude" | "openai" | "gemini" | "ollama";

export interface ProviderSettings {
  provider: Provider;
  api_key_masked: string | null;
  has_key: boolean;
  model: string | null;
  embedding_model: string | null;
  base_url: string | null;
  supports_embeddings: boolean;
  needs_key: boolean;
  active_llm: boolean;
  active_embedding: boolean;
}

export interface ProviderTestResult {
  provider: Provider;
  llm: { ok: true; invoices: number } | { ok: false; error: string } | null;
  embedding: { ok: true; dims: number } | { ok: false; error: string } | null;
}
