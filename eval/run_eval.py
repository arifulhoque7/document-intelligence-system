"""End-to-end evaluation through the public API of a running stack.

Uploads the labeled datasets, waits for processing, then scores extraction against ground truth and
writes eval/results/results.json and eval/results/report.md. Every number in the report is measured.

    backend/.venv/bin/python eval/run_eval.py --email admin@example.com --password ...
"""

import argparse
import json
import re
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

import httpx

HERE = Path(__file__).parent
FIELDS = ["invoice_number", "invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency"]
TERMINAL = {"completed", "needs_review", "failed"}
NAME_SIMILARITY = 0.9


# ---------- comparison rules ----------

def squash(s) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def norm_text(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def dec(v):
    try:
        return Decimal(str(v)).quantize(Decimal("0.01")) if v not in (None, "") else None
    except InvalidOperation:
        return None


def field_correct(field: str, truth, pred) -> bool:
    if truth in (None, ""):
        return pred in (None, "")  # nothing printed: the system must not invent a value
    if pred in (None, ""):
        return False
    if field in ("subtotal", "tax", "total"):
        return dec(truth) == dec(pred)
    if field == "invoice_number":
        return squash(truth) == squash(pred)
    if field in ("supplier_name", "customer_name"):
        return SequenceMatcher(None, norm_text(truth), norm_text(pred)).ratio() >= NAME_SIMILARITY
    return str(truth).strip().upper() == str(pred).strip().upper()


def line_item_f1(truth_items: list, pred_items: list) -> tuple[int, int, int]:
    """(true positives, predicted, expected). An item matches on equal amount and similar description."""
    unused = list(pred_items)
    tp = 0
    for t in truth_items:
        for p in unused:
            if dec(t.get("amount")) == dec(p.get("amount")) and SequenceMatcher(
                None, norm_text(t.get("description")), norm_text(p.get("description"))
            ).ratio() >= 0.8:
                tp += 1
                unused.remove(p)
                break
    return tp, len(pred_items), len(truth_items)


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


# ---------- API driver ----------

class Api:
    def __init__(self, base: str, email: str, password: str):
        self.c = httpx.Client(base_url=base, timeout=120)
        r = self.c.post("/api/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        self.c.headers["Authorization"] = f"Bearer {r.json()['token']}"

    def get(self, path, **params):
        r = self.c.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def upload(self, paths: list[Path]) -> dict:
        files = [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in paths]
        r = self.c.post("/api/documents", files=files)
        r.raise_for_status()
        return r.json()


def run(api: Api, cases: list[dict], dataset_dir: dict[str, Path], timeout_s: int) -> dict:
    by_file = {}
    t0 = time.monotonic()
    for i in range(0, len(cases), 20):
        batch = cases[i : i + 20]
        res = api.upload([dataset_dir[c["_set"]] / c["file"] for c in batch])
        for item in res["accepted"] + res["rejected"]:
            by_file[item["filename"]] = item.get("id")
    pending = {fid for fid in by_file.values() if fid}
    docs = {}
    while pending and time.monotonic() - t0 < timeout_s:
        for fid in list(pending):
            d = api.get(f"/api/documents/{fid}")
            if d["status"] in TERMINAL:
                docs[fid] = d
                pending.discard(fid)
        if pending:
            time.sleep(2)
    wall = time.monotonic() - t0
    for fid in pending:  # timed out
        docs[fid] = {**api.get(f"/api/documents/{fid}"), "status": "timeout"}
    return {"by_file": by_file, "docs": docs, "wall_s": wall}


# ---------- scoring ----------

def score(cases: list[dict], run_out: dict) -> dict:
    field_hits = defaultdict(lambda: [0, 0])  # field -> [correct, total]
    field_by_kind = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    li = [0, 0, 0]
    detect = {"expected": 0, "found": 0, "matched": 0}
    exact_invoices = [0, 0]
    doc_rows, times = [], defaultdict(list)
    validation_checks, false_review = [], [0, 0]
    invoices_by_file = {}

    for c in cases:
        fid = run_out["by_file"].get(c["file"])
        d = run_out["docs"].get(fid) if fid else None
        status = d["status"] if d else "rejected"
        preds = d.get("invoices", []) if d else []
        invoices_by_file[c["file"]] = preds
        expect_fail = c.get("expect_fail", False)
        ok = (status in ("failed", "rejected")) if expect_fail else (status in ("completed", "needs_review") and len(preds) > 0)
        doc_rows.append({"file": c["file"], "kind": c["kind"], "status": status, "ok": ok, "expect_fail": expect_fail,
                         "invoices_expected": len(c["invoices"]), "invoices_found": len(preds),
                         "processing_ms": d.get("processing_ms") if d else None, "pages": d.get("page_count") if d else None,
                         "error": d.get("error") if d else None})
        if d and d.get("processing_ms") and not expect_fail:
            times[c["kind"]].append(d["processing_ms"])
        if expect_fail:
            continue

        labeled = c.get("labeled_fields", FIELDS)
        pool = list(preds)
        detect["expected"] += len(c["invoices"])
        detect["found"] += len(preds)
        for truth in c["invoices"]:
            match = None
            if "invoice_number" in labeled:
                match = next((p for p in pool if squash(p["invoice_number"]) == squash(truth["invoice_number"])), None)
            if match is None and len(c["invoices"]) == 1 and len(pool) == 1:
                # One invoice expected and one found: pair them even if the number was misread, so an OCR slip
                # in the number costs that field only, not every field of the invoice.
                match = pool[0]
            if match:
                pool.remove(match)
                detect["matched"] += 1
            all_ok = True
            for f in labeled:
                good = bool(match) and field_correct(f, truth.get(f), match.get(f))
                all_ok &= good
                for bucket in (field_hits[f], field_by_kind[c["kind"]][f]):
                    bucket[0] += good
                    bucket[1] += 1
            if "invoice_number" in labeled:
                exact_invoices[0] += all_ok
                exact_invoices[1] += 1
                if match and all_ok and not c.get("expect_issue") and not c.get("cross_check"):
                    false_review[0] += bool(match["needs_review"])
                    false_review[1] += 1
            if "line_items" in truth:
                tp, np_, nt = line_item_f1(truth["line_items"], match["line_items"] if match else [])
                li[0] += tp
                li[1] += np_
                li[2] += nt
        if c.get("expect_issue"):
            codes = {i["code"] for p in preds for i in p["issues"]}
            validation_checks.append({"file": c["file"], "check": c["expect_issue"], "passed": c["expect_issue"] in codes})

    # Cross-document verification checks.
    for kind in ("match", "mismatch"):
        files = [c["file"] for c in cases if c.get("cross_check") == kind]
        codes = {i["code"] for f in files for p in invoices_by_file.get(f, []) for i in p["issues"]}
        flagged = "CROSS_DOC_MISMATCH" in codes
        if files:
            validation_checks.append({"file": " + ".join(files), "check": f"cross-document {kind}",
                                      "passed": flagged if kind == "mismatch" else not flagged})

    valid_docs = [r for r in doc_rows if not r["expect_fail"]]
    bad_docs = [r for r in doc_rows if r["expect_fail"]]
    total_correct = sum(v[0] for v in field_hits.values())
    total_fields = sum(v[1] for v in field_hits.values())
    precision = li[0] / li[1] if li[1] else 0
    recall = li[0] / li[2] if li[2] else 0
    all_times = [t for ts in times.values() for t in ts]
    pages = sum(r["pages"] or 0 for r in valid_docs)
    return {
        "documents": len(doc_rows),
        "document_success_rate": pct(sum(r["ok"] for r in valid_docs), len(valid_docs)),
        "document_failure_rate": pct(sum(r["status"] in ("failed", "timeout", "rejected") for r in valid_docs), len(valid_docs)),
        "corrupt_files_rejected": f"{sum(r['ok'] for r in bad_docs)}/{len(bad_docs)}",
        "field_accuracy_overall": pct(total_correct, total_fields),
        "field_accuracy": {f: {"accuracy": pct(*v), "n": v[1]} for f, v in field_hits.items()},
        "field_accuracy_by_kind": {k: {f: pct(*v) for f, v in fs.items()} for k, fs in field_by_kind.items()},
        "invoice_exact_match_rate": pct(*exact_invoices),
        "invoice_detection": {**detect, "recall": pct(detect["matched"], detect["expected"]), "precision": pct(detect["matched"], detect["found"])},
        "line_items": {"precision": round(100 * precision, 1), "recall": round(100 * recall, 1),
                       "f1": round(200 * precision * recall / (precision + recall), 1) if precision + recall else 0.0},
        "false_review_rate": pct(*false_review),
        "validation_checks": validation_checks,
        "processing_ms": {"mean": round(statistics.mean(all_times)) if all_times else None,
                          "p50": percentile(all_times, 0.5), "p95": percentile(all_times, 0.95), "max": max(all_times, default=None)},
        "processing_ms_by_kind": {k: {"n": len(v), "p50": percentile(v, 0.5), "p95": percentile(v, 0.95)} for k, v in sorted(times.items())},
        "wall_clock_s": round(run_out["wall_s"], 1),
        "throughput_pages_per_min": round(pages / (run_out["wall_s"] / 60), 1) if run_out["wall_s"] else None,
        "docs": doc_rows,
    }


# ---------- report ----------

def report(results: dict, meta: dict) -> str:
    s = results
    lines = [
        "# Evaluation report",
        "",
        f"Run: {meta['started']} | LLM: `{meta['llm']}` | Embeddings: `{meta['embedding']}` | Datasets: {', '.join(meta['datasets'])}",
        "",
        "All numbers below were measured by `eval/run_eval.py` against the running stack through its public API.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Documents | {s['documents']} |",
        f"| Document success rate (valid files) | {s['document_success_rate']}% |",
        f"| Document failure rate (valid files) | {s['document_failure_rate']}% |",
        f"| Corrupted/blank files correctly rejected | {s['corrupt_files_rejected']} |",
        f"| Field-level extraction accuracy | {s['field_accuracy_overall']}% |",
        f"| Invoices with every field correct | {s['invoice_exact_match_rate']}% |",
        f"| Invoice detection recall / precision | {s['invoice_detection']['recall']}% / {s['invoice_detection']['precision']}% |",
        f"| Line items precision / recall / F1 | {s['line_items']['precision']}% / {s['line_items']['recall']}% / {s['line_items']['f1']}% |",
        f"| Correct invoices wrongly sent to review | {s['false_review_rate']}% |",
        f"| Processing time per document (p50 / p95 / max) | {s['processing_ms']['p50']} / {s['processing_ms']['p95']} / {s['processing_ms']['max']} ms |",
        f"| Wall clock for the whole set | {s['wall_clock_s']} s |",
        f"| Throughput | {s['throughput_pages_per_min']} pages/min |",
        "",
        "## Field accuracy",
        "",
        "| Field | Accuracy | n |",
        "|---|---|---|",
        *[f"| {f} | {v['accuracy']}% | {v['n']} |" for f, v in s["field_accuracy"].items()],
        "",
        "## Accuracy by document kind",
        "",
        "| Kind | " + " | ".join(FIELDS) + " |",
        "|---|" + "---|" * len(FIELDS),
        *[f"| {k} | " + " | ".join(str(v.get(f, "")) for f in FIELDS) + " |" for k, v in sorted(s["field_accuracy_by_kind"].items())],
        "",
        "## Processing time by kind (ms)",
        "",
        "| Kind | n | p50 | p95 |",
        "|---|---|---|---|",
        *[f"| {k} | {v['n']} | {v['p50']} | {v['p95']} |" for k, v in s["processing_ms_by_kind"].items()],
        "",
        "## Validation and cross-verification checks",
        "",
        "| File | Check | Result |",
        "|---|---|---|",
        *[f"| {c['file']} | {c['check']} | {'pass' if c['passed'] else 'FAIL'} |" for c in s["validation_checks"]],
        "",
        "## Documents that did not succeed",
        "",
        "| File | Kind | Status | Error |",
        "|---|---|---|---|",
        *[f"| {r['file']} | {r['kind']} | {r['status']} | {r['error'] or ''} |" for r in s["docs"] if not r["ok"]],
        "",
        "## Scoring rules",
        "",
        "- A field is correct when it equals the label after normalisation: amounts as decimals, dates as ISO, invoice numbers"
        " compared on letters and digits only, party names with a similarity of at least 0.9 after lower-casing and removing punctuation.",
        "- When a field is not printed on the document (label is null), it is correct only if the system also returns null: invented values count as errors.",
        "- Public receipts (SROIE) are labeled only for supplier, date and total; other fields are not scored there.",
        "- Line items match on equal amount and description similarity of at least 0.8.",
        "- A valid document succeeds when it finishes (completed or needs review) with at least one invoice; a corrupted or blank file succeeds when it is rejected.",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password", required=True)
    ap.add_argument("--datasets", nargs="+", default=["synthetic", "public"])
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--rescore", action="store_true", help="score eval/results/raw_run.json again, no uploads")
    ap.add_argument("--recover-since", help="rebuild raw_run.json from documents uploaded since this ISO time")
    args = ap.parse_args()

    api = Api(args.api, args.email, args.password)
    providers = api.get("/api/settings/providers")
    active = lambda key, attr: next((f"{p['provider']}/{p[attr]}" for p in providers if p[key]), "none")  # noqa: E731
    meta = {"started": datetime.now(UTC).isoformat(timespec="seconds"), "llm": active("active_llm", "model"),
            "embedding": active("active_embedding", "embedding_model"), "datasets": args.datasets}

    cases, dirs = [], {}
    for name in args.datasets:
        dirs[name] = HERE / "dataset" / name
        for c in json.loads((dirs[name] / "labels.json").read_text()):
            cases.append({**c, "_set": name})

    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    raw_path = results_dir / "raw_run.json"
    if args.recover_since:
        prev = json.loads((results_dir / "results.json").read_text())
        meta = prev["meta"]
        wanted = {c["file"] for c in cases}
        by_file, docs = {}, {}
        page = 1
        while True:
            items = api.get("/api/documents", page=page, page_size=200)["items"]
            for d in items:
                if d["created_at"] >= args.recover_since and d["filename"] in wanted and d["filename"] not in by_file:
                    by_file[d["filename"]] = d["id"]
            if len(items) < 200:
                break
            page += 1
        for fid in by_file.values():
            docs[fid] = api.get(f"/api/documents/{fid}")
        out = {"by_file": by_file, "docs": docs, "wall_s": prev["wall_clock_s"]}
        raw_path.write_text(json.dumps({"meta": meta, "run": out}, default=str))
    elif args.rescore:
        # Score a saved run again (e.g. after changing scoring rules) without re-running the LLM.
        saved = json.loads(raw_path.read_text())
        out, meta = saved["run"], saved["meta"]
    else:
        print(f"Uploading {len(cases)} documents; LLM {meta['llm']}")
        out = run(api, cases, dirs, args.timeout)
        raw_path.write_text(json.dumps({"meta": meta, "run": out}, default=str))
    results = score(cases, out)
    (results_dir / "results.json").write_text(json.dumps({"meta": meta, **results}, indent=2, default=str))
    (results_dir / "report.md").write_text(report(results, meta))
    print(report(results, meta))


if __name__ == "__main__":
    main()
