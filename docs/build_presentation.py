"""Build doc-intel/docs/presentation.html: diagrams come from README.md, code excerpts from the source files."""
import html, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
readme = (ROOT / "README.md").read_text()
D = re.findall(r"```mermaid\n(.*?)```", readme, re.S)
assert len(D) == 10, len(D)
INSTALL, CONTEXT, DEPLOY, PIPELINE, SEQUENCE, DOCSTATE, INVSTATE, ER, LAYERS, FRONT = D


# Same flow as the README pipeline, with short labels so it reads at slide size.
PIPELINE_SLIDE = """flowchart LR
    Q[Queued] --> D{Detect type<br/>from content}
    D -->|PDF| T[Text layer,<br/>OCR if scanned]
    D -->|image / TIFF| O[Clean-up<br/>+ OCR]
    D -->|Excel / CSV| M{Invoice<br/>columns?}
    D -->|other| F[Failed:<br/>unsupported]
    M -->|yes| X[Exact mapping<br/>no LLM]
    M -->|no| L
    T --> S[Split into<br/>invoice chunks]
    O --> S
    S --> L[LLM extraction<br/>strict JSON]
    L --> G[Grounding<br/>check]
    G --> V[Validation +<br/>cross-checks]
    X --> V
    V --> E[Embeddings]
    E --> R{Flagged?}
    R -->|yes| NR[Needs review]
    R -->|no| C[Completed]
"""


def excerpt(rel, start, end=None, stop_before=True):
    """Lines from `start` (a line prefix) up to the line starting with `end` (excluded)."""
    lines = (ROOT / rel).read_text().splitlines()
    i = next(n for n, l in enumerate(lines) if l.lstrip().startswith(start))
    j = len(lines)
    if end:
        j = next(n for n in range(i + 1, len(lines)) if lines[n].lstrip().startswith(end))
    out = lines[i:j]
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


CODE = {
    "ocr": excerpt("backend/app/processing/loaders.py", "for i in range(n):", "# Bound memory"),
    "provider": excerpt("backend/app/llm/base.py", "class LLMProvider", "# ----------"),
    "extract": excerpt("backend/app/llm/__init__.py", "def extract_invoices", "def embed"),
    "schema": excerpt("backend/app/llm/base.py", "class ExtractedInvoice", "class ExtractionResult"),
    "prompt": "\n".join(l for l in excerpt("backend/app/llm/prompts.py", "SYSTEM_PROMPT", "def user_prompt").splitlines()
                        if l.startswith("- Copy") or l.startswith("  read it") or l.startswith("  total") or l.startswith("- The document text")).replace('"""', ''),
    "ground": excerpt("backend/app/services/validation.py", "def is_grounded", "# ---------- rules"),
    "rule": excerpt("backend/app/services/validation.py", "sub, tax, total = inv.subtotal", "if sub is not None and tax is not None"),
    "lock": excerpt("backend/app/services/pipeline.py", "def process_document", "def _run_pipeline"),
    "hybrid": excerpt("backend/app/services/search.py", "def hybrid", "MODES ="),
    "proxy": excerpt("frontend/lib/proxy.ts", "export async function proxy", "const out = new Headers();"),
    "sheet": excerpt("backend/app/processing/sheets.py", "def find_table", "def map_sheet"),
}


def code(key, lang="python", title=""):
    t = f'<div class="ctitle">{html.escape(title)}</div>' if title else ""
    return f'<div class="code">{t}<pre><code class="language-{lang}">{html.escape(CODE[key])}</code></pre></div>'


def diagram(src, cls=""):
    return f'<div class="mermaid-box {cls}"><script type="text/plain" class="mmd">{src}</script></div>'


def ul(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


slides = []


def slide(kicker, title, body, cls=""):
    slides.append(f'<section class="slide {cls}"><div class="kicker">{kicker}</div><h2>{title}</h2><div class="body">{body}</div></section>')


# 1. Title
slides.append('''<section class="slide title-slide">
  <div class="bar"></div>
  <div class="tbody">
    <div class="pill">AI Engineer assessment · Care Guide</div>
    <h1>Document <span>Intelligence</span> System</h1>
    <p class="sub">Read invoices from PDFs, scans, photos and spreadsheets, extract them as structured JSON with an LLM,
    validate and cross-check them, and make everything searchable.</p>
    <div class="chips"><span>FastAPI</span><span>Celery + Redis</span><span>Tesseract OCR</span><span>LLM extraction</span><span>PostgreSQL + pgvector</span><span>Next.js</span></div>
    <div class="who">Ariful Hoque · github.com/arifulhoque7/document-intelligence-system · November 2026</div>
  </div></section>''')

# 2. Problem and scope
slide("The brief", "From thousands of documents to <span>trusted</span> data", '''
<div class="grid3">
 <div class="card"><b>1 · Read anything</b><p>PDF (digital and scanned), JPG, PNG, TIFF, XLSX, XLS, CSV. Multi-page, multi-sheet, poor quality, corrupted.</p></div>
 <div class="card"><b>2 · Extract</b><p>Invoice number, date, supplier, customer, subtotal, tax, total, currency, line items, as JSON. Missing stays null.</p></div>
 <div class="card"><b>3 · Validate</b><p>Missing fields, wrong arithmetic, duplicates, PDF-PDF and PDF-Excel mismatches. Flag for review.</p></div>
 <div class="card"><b>4 · Serve</b><p>REST API for upload, status, results, search, corrections, reprocessing. Slow work in the background.</p></div>
 <div class="card"><b>5 · Store and search</b><p>Metadata, text, results, issues and history. Keyword filters and semantic search.</p></div>
 <div class="card"><b>6 · Prove it</b><p>Automated tests for every path, and an evaluation with measured accuracy, time and failure rates.</p></div>
</div>''')

# 3. What we used
slide("What we used and why", "The <span>stack</span>", '''
<table class="stack">
<tr><th>Layer</th><th>Technology</th><th>Why this choice</th></tr>
<tr><td>API</td><td><b>Python 3.12 · FastAPI</b></td><td>Typed request validation (Pydantic), async uploads, auto-generated OpenAPI docs. One language with the OCR and data tools.</td></tr>
<tr><td>Background jobs</td><td><b>Celery · Redis</b></td><td>OCR and LLM calls never block a request. Late acknowledgement, retries with backoff, horizontal workers.</td></tr>
<tr><td>Reading documents</td><td><b>PyMuPDF · Tesseract 5 · pandas, openpyxl, xlrd</b></td><td>Exact text from digital PDFs, OCR only where a page has no text, every sheet of every workbook.</td></tr>
<tr><td>AI extraction</td><td><b>Claude · OpenAI · Gemini · Ollama</b></td><td>Chosen in Settings. One adapter per vendor behind one interface; strict JSON schema with nullable fields.</td></tr>
<tr><td>Data and search</td><td><b>PostgreSQL 16 · pgvector</b></td><td>Full-text keyword search (GIN) and vector search (HNSW) next to the rows they describe, in one transaction.</td></tr>
<tr><td>Web app</td><td><b>Next.js 15 · TypeScript · Tailwind v4</b></td><td>Review interface with live progress; a runtime proxy keeps the session in an httpOnly cookie.</td></tr>
<tr><td>Delivery</td><td><b>Docker Compose</b></td><td>Five services, health-checked start order, non-root containers, one command to run.</td></tr>
<tr><td>Quality</td><td><b>pytest · Playwright · evaluation harness</b></td><td>73 tests on a real database; accuracy and timing measured through the public API.</td></tr>
</table>''')

# 4-12 architecture: one diagram per slide with a full description
def arch(kicker, title, src, points, cls=""):
    if cls == "wide":  # wide diagrams: full width on top, descriptions as columns below
        cols = "".join(f'<div class="dcol">{pt}</div>' for pt in points)
        slide(kicker, title, f'<div class="wide">{diagram(src, "w")}<div class="dcols n{len(points)}">{cols}</div></div>')
    else:
        slide(kicker, title, f'<div class="split">{diagram(src, cls)}<div class="desc">{ul(points)}</div></div>')

arch("Architecture 1 / 8 · System context", "Who talks to <span>whom</span>", CONTEXT, [
    "<b>Browser</b> talks only to the <b>Next.js</b> app. Its runtime proxy forwards <code>/api/*</code>, so the session cookie stays httpOnly and same-origin.",
    "<b>FastAPI</b> validates input, stores the file, writes a <code>documents</code> row and returns <b>202</b> at once.",
    "<b>Redis</b> carries jobs to <b>Celery workers</b>. Workers read the file, run OCR and spreadsheet parsing, call the LLM and the embedding provider, and write results to <b>PostgreSQL</b>.",
    "Scripts and integrations use the same API with a <b>Bearer</b> token.",
    "The API never runs OCR or LLM calls, so requests stay fast however large the file.",
], "wide")
arch("Architecture 2 / 8 · Deployment", "Five containers, <span>one command</span>", DEPLOY, [
    "<b>web</b> (Node 22) and <b>api</b> / <b>worker</b> (Python 3.12 + Tesseract) run as non-root users.",
    "<b>db</b> is PostgreSQL 16 with pgvector; <b>redis</b> is the queue. Data and uploads live on named volumes.",
    "Start order is enforced by health checks: db and redis, then api (creates the schema and first admin), then worker and web.",
    "Only 127.0.0.1 ports are published. Ollama on the host is reached through <code>host.docker.internal</code>.",
    "Scale with <code>docker compose up --scale worker=N</code>.",
])
arch("Architecture 3 / 8 · Processing pipeline", "What happens to <span>every file</span>", PIPELINE_SLIDE, [
    "<b>Detect</b> the real type from magic bytes, never the extension. Unknown content fails with a clear reason.",
    "<b>PDF</b>: text layer per page; pages with fewer than 30 alphanumerics are rendered at 300 dpi and OCR'd in a thread pool.",
    "<b>Images and TIFF</b>: clean-up, OCR, then rotation fix and other layout modes when confidence is low.",
    "<b>Spreadsheets</b> with invoice columns are mapped exactly, with no LLM. Other sheets go to the LLM.",
    "<b>Segment</b> pages into invoice chunks, <b>extract</b> with a strict schema, <b>ground</b> every value in the source text, <b>validate</b>, <b>embed</b>, then mark completed or needs review.",
], "wide")
arch("Architecture 4 / 8 · Request flow", "Upload to <span>approved</span> invoice", SEQUENCE, [
    "Upload is streamed with a size cap; the API answers per file: accepted or rejected with a reason.",
    "The UI polls the document every 2 s only while it is queued or processing.",
    "The worker receives the job with late acknowledgement, so a crash puts it back on the queue.",
    "Results, issues, revision v1 and every stage event are written in the database.",
    "A correction sends only changed fields; the API re-validates, re-embeds and writes revision v2. Approval is a recorded action.",
], "tall")
arch("Architecture 5 / 8 · Document states", "Every document has a <span>clear state</span>", DOCSTATE, [
    "<b>queued</b> to <b>processing</b> when a worker takes the job; progress 0-100 is stored as it runs.",
    "<b>completed</b> when every invoice is clean; <b>needs_review</b> when any invoice is flagged or none was found.",
    "<b>failed</b> for corrupt or unsupported files and permanent LLM errors; transient LLM errors retry with backoff first.",
    "Failed or stuck jobs (10 minutes without progress) can be requeued from the UI or the API.",
    "Only one worker may process a document at a time: a Postgres advisory lock guards the run.",
])
arch("Architecture 6 / 8 · Invoice review", "Human review is part of the <span>design</span>", INVSTATE, [
    "Any validation <b>error</b>, or a <b>warning on a money field</b>, sends the invoice to review.",
    "A correction marks edited values as certain, re-runs every rule and records a new version.",
    "Approval is explicit and versioned; editing an approved invoice needs a fresh approval.",
    "A new cross-document mismatch flags both records, including the one processed first.",
])
arch("Architecture 7 / 8 · Data model", "One database for <span>everything</span>", ER, [
    "<b>documents</b>: file, detected type, hash, status, progress, error, attempts, timing.",
    "<b>document_pages</b>: text per page or sheet, method (text, ocr, sheet), OCR confidence, full-text index.",
    "<b>invoices</b>: fields as NUMERIC money, line items and confidence as JSONB, a 768-d <b>vector</b> (HNSW) and a weighted <b>tsvector</b> (GIN).",
    "<b>invoice_revisions</b> (full snapshot + diff), <b>validation_issues</b>, <b>processing_events</b>: the audit trail.",
    "<b>provider_settings</b>: API keys encrypted with AES-256-GCM, never returned unmasked.",
], "tall")
arch("Architecture 8 / 8 · Code layout", "Layers that point <span>inwards</span>", LAYERS, [
    "<b>api/</b> is HTTP only: routers, auth dependencies, serializers. No business rules.",
    "<b>services/</b> hold the logic: pipeline, validation, corrections and cross-checks, search, storage.",
    "<b>processing/</b> turns files into text; <b>llm/</b> is a provider-neutral contract with one adapter per vendor.",
    "<b>core/</b> has config, the database engine and security (bcrypt, JWT, AES-GCM).",
    "The same services run from the API, the worker, the tests and the evaluation.",
])
arch("Frontend", "The review interface", FRONT, [
    "Pages under <code>app/(app)</code>: dashboard, documents, review queue, invoices, search, cross-checks, settings.",
    "<code>lib/api.ts</code>: typed fetch with one error type carrying the status and the API's message; 401 redirects to login.",
    "<code>usePoll</code> refreshes only while something is processing and pauses when the tab is hidden.",
    "API text is never rendered as HTML; light and dark themes; keyboard reachable controls.",
], "wide")

# Code slides
slide("Code 1 · Reading PDFs", "Text layer first, <span>OCR</span> only where needed", code("ocr", "python", "backend/app/processing/loaders.py") +
      '<p class="note">PyMuPDF is not thread-safe, so pages render on one thread; Tesseract runs as a subprocess, so OCR runs in a thread pool. The queue is drained in batches so memory stays flat on 1000-page files.</p>')
slide("Code 2 · Spreadsheets", "Exact values <span>without</span> the LLM", code("sheet", "python", "backend/app/processing/sheets.py") +
      '<p class="note">A header row naming an invoice number plus two other known columns means the sheet is mapped deterministically: free, instant and exact. Anything else goes to the LLM.</p>')
slide("Code 3 · Pluggable LLMs", "One interface, <span>four</span> providers", '<div class="two">' + code("provider", "python", "backend/app/llm/base.py") + code("extract", "python", "backend/app/llm/__init__.py") + '</div>' +
      '<p class="note">Each adapter maps its SDK errors to <code>LLMError(transient=...)</code>, so the worker knows whether to retry. Output is validated with Pydantic before anything is stored.</p>')
slide("Code 4 · No invented values", "Strict schema, <span>nullable</span> fields", '<div class="two">' + code("schema", "python", "backend/app/llm/base.py") + code("prompt", "text", "backend/app/llm/prompts.py (rules excerpt)") + '</div>' +
      '<p class="note">Every key is required but may be null, so the model can say "not printed" instead of guessing. The same schema is sent to Claude, OpenAI, Gemini and Ollama.</p>')
slide("Code 5 · Grounding", "Is the value really <span>in the document</span>?", code("ground", "python", "backend/app/services/validation.py") +
      '<p class="note">Amounts are checked in several print formats (1,234.50 · 1.234,50 · 1234.5). A value that is not in the source text gets confidence 0.3 and an UNGROUNDED_VALUE warning: a cheap, deterministic hallucination check.</p>')
slide("Code 6 · Validation", "Arithmetic the model <span>cannot</span> skip", code("rule", "python", "backend/app/services/validation.py") +
      '<p class="note">14 rule codes: missing fields, total, line items and their sum, negative amounts, tax rate, dates, currency, low confidence, grounding, duplicates and cross-document mismatches. Money is Decimal; tolerance is 0.01 or 0.5%.</p>')
slide("Code 7 · Reliability", "At most <span>one</span> run per document", code("lock", "python", "backend/app/services/pipeline.py") +
      '<p class="note">Found by testing: after a restart, a redelivered job and a requeued one ran in parallel and saved every invoice twice. The advisory lock lives on its own connection, so Postgres frees it if a worker crashes.</p>')
slide("Code 8 · Search", "Keyword + semantic = <span>hybrid</span>", code("hybrid", "python", "backend/app/services/search.py") +
      '<p class="note">Keyword search uses PostgreSQL full-text (GIN), semantic search uses pgvector cosine distance (HNSW). Reciprocal rank fusion merges them; without an embedding provider it degrades to keyword.</p>')
slide("Code 9 · Frontend proxy", "Same-origin API, <span>httpOnly</span> session", code("proxy", "typescript", "frontend/lib/proxy.ts") +
      '<p class="note">API_URL is read per request, so one image runs anywhere. Upload bodies are streamed, cookies are forwarded both ways, and an unreachable API returns a readable 502.</p>')

# Screens
slide("The product", "Review interface", '''<div class="shots">
<figure><img src="../frontend/docs/screenshots/dashboard-light.png"><figcaption>Dashboard: totals, status, needs attention</figcaption></figure>
<figure><img src="../frontend/docs/screenshots/invoice-detail-light.png" class="top"><figcaption>Invoice review: confidence, issues, source text</figcaption></figure>
<figure><img src="../frontend/docs/screenshots/cross-checks-light.png"><figcaption>Cross-checks: PDF vs Excel</figcaption></figure>
<figure><img src="../frontend/docs/screenshots/documents-dark.png"><figcaption>Documents with live progress (dark theme)</figcaption></figure>
</div>''')

# Testing
slide("Quality", "<span>73</span> automated tests on a real database", '''
<table class="stack small">
<tr><th>Suite</th><th>Tests</th><th>What is proven</th></tr>
<tr><td>Processing</td><td>19</td><td>Type by content; digital and scanned PDF; poor photos; multi-page and multi-invoice PDFs; TIFF frames; XLSX, XLS, CSV mapped exactly; corrupt, blank, encrypted files; page limit</td></tr>
<tr><td>Normalise and validate</td><td>21</td><td>10 amount formats, dates, currencies; every rule; rounding tolerance; grounding</td></tr>
<tr><td>LLM layer</td><td>12</td><td>Strict schema; invalid JSON; nulls stay null; hallucination detection; transient vs permanent errors; refusals; Gemini schema</td></tr>
<tr><td>API end to end</td><td>21</td><td>Auth, roles, rate limit; uploads to results; corrections, history, approval; filters; three search modes; cross-checks; reprocessing; redelivery and parallel-run safety; encrypted keys</td></tr>
</table>
<p class="note">Plus end-to-end checks: the full Docker stack, every screen in light and dark, a machine-restart recovery test, and all diagrams rendered.</p>''')

slide("Measured, not estimated", "Evaluation on <span>74</span> labeled documents", '''
<div class="kpis">
 <div><b>96.3%</b><span>field accuracy</span></div>
 <div><b>98.6%</b><span>document success</span></div>
 <div><b>99.0%</b><span>invoice detection</span></div>
 <div><b>98.0%</b><span>line items F1</span></div>
 <div><b>4 / 4</b><span>corrupt files rejected</span></div>
 <div><b>4.8 s</b><span>1005-page PDF read</span></div>
</div>
<p class="note">54 synthetic documents with known truth (every format, three scan qualities, cross-check pairs, a wrong total, corrupted files) and 20 real scanned receipts (ICDAR 2019 SROIE), run through the public API with a local 7B model (Ollama). Weakest: invoice numbers on scans (OCR reads SI/ as S1/) and real receipts (date 80%, total 70%, supplier 65%).</p>''')

slide("Honest scope", "What was <span>not</span> tested", ul([
    "<b>Live calls to Claude, OpenAI and Gemini</b>: adapters are unit-tested with mocked SDKs; only the local model ran end to end.",
    "Accuracy and speed with a hosted model; a full 1000-page document through the LLM.",
    "Scale-out across several workers and hosts; load and soak tests.",
    "Real company invoices, handwriting, non-English text, scans rotated 90 degrees.",
    "Security scanning, CSRF and TLS in a real deployment; Safari, Firefox, mobile and screen readers.",
    "Database migrations, backups and encryption-key rotation.",
]) + '<p class="note">All 27 gaps, with the risk and how to test each, are in README section 8.5 and docs/QA_HANDOFF.md.</p>')

slide("Getting started", "Run it in <span>one</span> command", f'<div class="split">{diagram(INSTALL)}<div class="desc">' +
      '<div class="code"><pre><code class="language-bash">cp .env.example .env   # set secrets\ndocker compose up --build -d\nopen http://localhost:3000</code></pre></div>' +
      ul(["Log in as the admin from <code>.env</code>.", "Settings: add a key (or point Ollama at the host), press Test, choose the active LLM and embedding provider.", "Upload documents on the dashboard and review flagged invoices."]) + '</div></div>')

slides.append('''<section class="slide title-slide end">
  <div class="bar"></div>
  <div class="tbody">
    <div class="pill">Thank you</div>
    <h1>Questions <span>welcome</span></h1>
    <p class="sub">Code, setup, architecture decisions, QA handoff, test results and the evaluation report are all in the repository.</p>
    <div class="who">github.com/arifulhoque7/document-intelligence-system · Ariful Hoque · hoquea57@gmail.com</div>
  </div></section>''')

CSS = """
:root{--p:#1d5ff0;--tint:#eaf1ff;--ink:#111827;--title:#1f2937;--body:#4b5563;--line:#e5e7eb;--surface:#f8fafc}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0f172a;font-family:'Plus Jakarta Sans',system-ui,sans-serif;color:var(--ink)}
#stage{position:fixed;left:50%;top:50%;width:1440px;height:900px;transform-origin:center;}
.slide{position:absolute;inset:0;background:#fff;padding:56px 72px 70px;display:none;flex-direction:column;overflow:hidden}
.slide.on{display:flex}
.kicker{font-size:15px;font-weight:600;color:var(--p);letter-spacing:.06em;text-transform:uppercase}
h2{font-size:40px;line-height:1.15;margin:8px 0 26px;color:var(--title);font-weight:700}
h2 span,h1 span{color:var(--p)}
.body{flex:1;min-height:0;display:flex;flex-direction:column;gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.card{border:1px solid var(--line);border-radius:14px;padding:20px 22px;background:var(--surface)}
.card b{font-size:19px;color:var(--title)}.card p{margin:8px 0 0;font-size:16.5px;line-height:1.5;color:var(--body)}
table.stack{border-collapse:collapse;width:100%;font-size:16.5px}
table.stack th{text-align:left;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--body);padding:8px 12px;border-bottom:2px solid var(--line)}
table.stack td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.4;color:var(--body)}
table.stack td:first-child{color:var(--p);font-weight:600;white-space:nowrap}
table.stack td b{color:var(--title)}
table.stack.small{font-size:15.5px}
.split{display:grid;grid-template-columns:1.55fr 1fr;gap:34px;flex:1;min-height:0}
.mermaid-box{border:1px solid var(--line);border-radius:14px;background:var(--surface);display:flex;align-items:center;justify-content:center;padding:14px;min-height:0;overflow:hidden}
.mermaid-box svg{max-width:100%;max-height:640px;height:auto}
.mermaid-box.tall svg{max-height:680px}
.wide{display:flex;flex-direction:column;gap:18px;flex:1;min-height:0}
.mermaid-box.w{flex:1;min-height:0}.mermaid-box.w svg{max-height:100%;width:100%}
.dcols{display:grid;gap:14px}.dcols.n4{grid-template-columns:repeat(4,1fr)}.dcols.n5{grid-template-columns:repeat(5,1fr)}
.dcol{font-size:15px;line-height:1.45;color:var(--body);border-top:3px solid var(--p);padding-top:10px}.dcol b{color:var(--title)}
.desc ul{margin:0;padding-left:20px}.desc li,.body>ul li{font-size:17.5px;line-height:1.5;color:var(--body);margin:0 0 12px}
.desc b,.body li b{color:var(--title)}
.body>ul{margin:0;padding-left:22px}
code{font-variant-ligatures:none;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.9em;background:var(--tint);color:#1e3a8a;padding:1px 6px;border-radius:5px}
.code{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#0b1220;min-height:0}
.code pre{margin:0;padding:16px 20px;overflow:hidden}.code pre code{background:none;color:#e5e7eb;padding:0;font-size:14.5px;line-height:1.5;white-space:pre-wrap;font-variant-ligatures:none}
.ctitle{font:600 13px 'JetBrains Mono',monospace;color:#93c5fd;background:#111a2e;padding:8px 18px;border-bottom:1px solid #1e293b}
.two{display:grid;grid-template-columns:1fr;gap:14px;min-height:0}
.note{margin:4px 0 0;font-size:16.5px;line-height:1.55;color:var(--body);border-left:4px solid var(--p);padding:4px 0 4px 16px}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:16px;flex:1;min-height:0}
.shots figure{margin:0;display:flex;flex-direction:column;min-height:0}
.shots img{width:100%;height:290px;object-fit:cover;object-position:top left;border:1px solid var(--line);border-radius:10px}
.shots figcaption{font-size:14.5px;color:var(--body);margin-top:6px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.kpis div{border:1px solid var(--line);border-radius:14px;padding:22px 26px;background:var(--surface)}
.kpis b{display:block;font-size:46px;color:var(--p);font-family:'JetBrains Mono',monospace;font-weight:600}
.kpis span{font-size:17px;color:var(--body)}
.title-slide{padding:0;flex-direction:row}
.title-slide .bar{width:14px;background:var(--p)}
.title-slide .tbody{padding:120px 110px;display:flex;flex-direction:column;justify-content:center;gap:22px}
.pill{align-self:flex-start;background:var(--tint);color:var(--p);font-weight:600;padding:8px 16px;border-radius:999px;font-size:17px}
h1{font-size:76px;line-height:1.05;margin:0;color:var(--title);letter-spacing:-.02em}
.sub{font-size:24px;line-height:1.5;color:var(--body);max-width:1050px;margin:0}
.chips{display:flex;gap:10px;flex-wrap:wrap}.chips span{border:1px solid var(--line);border-radius:999px;padding:8px 16px;font-size:16px;color:var(--title);background:var(--surface)}
.who{font-size:17px;color:var(--body);margin-top:20px}
#zoom{position:absolute;inset:0;background:#fff;display:none;padding:36px;z-index:5;cursor:zoom-out}#zoom.on{display:block}
#zoom svg{width:100%;height:100%;max-width:none!important}
.zhint{position:absolute;right:24px;top:16px;font-size:13px;color:#9ca3af}
.mermaid-box{cursor:zoom-in}
#hud{position:fixed;right:18px;bottom:12px;font:600 13px 'JetBrains Mono',monospace;color:#94a3b8}
#prog{position:fixed;left:0;bottom:0;height:4px;background:var(--p);transition:width .3s}
.slide .pageno{position:absolute;right:72px;bottom:28px;font:500 13px 'JetBrains Mono',monospace;color:#9ca3af}
.slide .brand{position:absolute;left:72px;bottom:28px;font-size:13px;color:#9ca3af}
"""

JS = """
const S=[...document.querySelectorAll('.slide')];let cur=0;const done=new Set();
mermaid.initialize({startOnLoad:false,theme:'base',securityLevel:'strict',themeVariables:{primaryColor:'#eaf1ff',primaryBorderColor:'#1d5ff0',primaryTextColor:'#1f2937',lineColor:'#64748b',fontFamily:'Plus Jakarta Sans, sans-serif',fontSize:'15px'}});
async function render(i){if(done.has(i))return;done.add(i);const boxes=S[i].querySelectorAll('.mermaid-box');let k=0;for(const b of boxes){const src=b.querySelector('.mmd').textContent;const {svg}=await mermaid.render('m'+i+'_'+(k++),src);b.innerHTML=svg;}}
function fit(){const s=Math.min(innerWidth/1440,innerHeight/900);document.getElementById('stage').style.transform=`translate(-50%,-50%) scale(${s})`;}
async function show(i){if(typeof closeZoom==='function')closeZoom();S.forEach(x=>x.querySelectorAll('.mermaid-box svg').forEach(v=>{v.style.transform='none'}));cur=Math.max(0,Math.min(S.length-1,i));S.forEach((s,n)=>s.classList.toggle('on',n===cur));await render(cur);document.getElementById('hud').textContent=(cur+1)+' / '+S.length;document.getElementById('prog').style.width=((cur+1)/S.length*100)+'%';history.replaceState(null,'','#'+(cur+1));window.__ready=true;}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(cur+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(cur-1)}if(e.key==='Home')show(0);if(e.key==='End')show(S.length-1)});
// Zoom: click a diagram or press Z for a full-screen view; Esc or click closes it.
// zoomTo(fx, fy, k) smoothly magnifies the current diagram around a point (fractions 0-1); zoomTo() resets.
const Z=document.getElementById('zoom');
function openZoom(){const svg=S[cur].querySelector('.mermaid-box svg');if(!svg)return;Z.innerHTML='';const c=svg.cloneNode(true);c.removeAttribute('style');c.setAttribute('width','100%');c.setAttribute('height','100%');Z.appendChild(c);Z.insertAdjacentHTML('beforeend','<div class="zhint">Esc or click to close</div>');Z.classList.add('on')}
function closeZoom(){Z.classList.remove('on')}
function zoomTo(fx,fy,k){const svg=S[cur].querySelector('.mermaid-box svg');if(!svg)return;svg.style.transition='transform 1.4s cubic-bezier(.2,.8,.2,1)';svg.style.transformOrigin=(fx*100)+'% '+(fy*100)+'%';svg.style.transform=k?'scale('+k+')':'none'}
window.zoomTo=zoomTo;window.openZoom=openZoom;window.closeZoom=closeZoom;
addEventListener('keydown',e=>{if(e.key==='z'||e.key==='Z')Z.classList.contains('on')?closeZoom():openZoom();if(e.key==='Escape')closeZoom()});
addEventListener('click',e=>{if(e.target.closest('a'))return;if(Z.classList.contains('on')){closeZoom();return}if(e.target.closest('.mermaid-box')){openZoom();return}show(cur+(e.clientX<innerWidth/3?-1:1))});
addEventListener('resize',fit);
S.forEach((s,n)=>{if(!s.classList.contains('title-slide')){s.insertAdjacentHTML('beforeend',`<div class="brand">Document Intelligence System · Ariful Hoque</div>`)}});
window.goto=i=>show(i);
fit();hljs.highlightAll();show((parseInt(location.hash.slice(1))||1)-1);
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Document Intelligence System</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<style>{CSS}</style></head>
<body><div id="stage">{''.join(slides)}<div id="zoom"></div></div><div id="hud"></div><div id="prog"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
<script>{JS}</script>
<!-- Arrow keys, space or click to move between slides. Home/End jump. #N in the URL opens slide N. -->
</body></html>"""
out = ROOT / "docs" / "presentation.html"
out.write_text(page)
print(len(slides), "slides ->", out, len(page), "bytes")
