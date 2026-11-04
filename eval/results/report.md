# Evaluation report

Run: 2026-11-04T05:57:10+00:00 | LLM: `ollama/qwen2.5-coder:7b` | Embeddings: `ollama/nomic-embed-text` | Datasets: synthetic, public

All numbers below were measured by `eval/run_eval.py` against the running stack through its public API.

## Summary

| Metric | Value |
|---|---|
| Documents | 74 |
| Document success rate (valid files) | 98.6% |
| Document failure rate (valid files) | 0.0% |
| Corrupted/blank files correctly rejected | 4/4 |
| Field-level extraction accuracy | 96.3% |
| Invoices with every field correct | 91.0% |
| Invoice detection recall / precision | 99.0% / 99.0% |
| Line items precision / recall / F1 | 99.1% / 96.9% / 98.0% |
| Correct invoices wrongly sent to review | 10.6% |
| Processing time per document (p50 / p95 / max) | 95780 / 305649 / 445654 ms |
| Wall clock for the whole set | 2251.2 s |
| Throughput | 2.3 pages/min |

## Field accuracy

| Field | Accuracy | n |
|---|---|---|
| invoice_number | 94.9% | 78 |
| invoice_date | 95.9% | 98 |
| supplier_name | 92.9% | 98 |
| customer_name | 96.2% | 78 |
| subtotal | 100.0% | 78 |
| tax | 98.7% | 78 |
| total | 93.9% | 98 |
| currency | 100.0% | 78 |

## Accuracy by document kind

| Kind | invoice_number | invoice_date | supplier_name | customer_name | subtotal | tax | total | currency |
|---|---|---|---|---|---|---|---|---|
| csv | 100.0 | 100.0 | 100.0 | 88.9 | 100.0 | 88.9 | 100.0 | 100.0 |
| image_jpg | 75.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| image_png | 75.0 | 100.0 | 100.0 | 75.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| pdf_bundle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| pdf_digital | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| pdf_multipage | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| pdf_scanned | 75.0 | 100.0 | 100.0 | 87.5 | 100.0 | 100.0 | 100.0 | 100.0 |
| public_receipt |  | 80.0 | 65.0 |  |  |  | 70.0 |  |
| tiff | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| xls | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| xlsx | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Processing time by kind (ms)

| Kind | n | p50 | p95 |
|---|---|---|---|
| csv | 3 | 736 | 1515 |
| image_jpg | 4 | 101212 | 115496 |
| image_png | 4 | 97147 | 106560 |
| pdf_bundle | 2 | 230561 | 445654 |
| pdf_digital | 15 | 123918 | 228976 |
| pdf_multipage | 3 | 216522 | 323638 |
| pdf_scanned | 8 | 105511 | 239861 |
| public_receipt | 20 | 91243 | 108543 |
| tiff | 3 | 244435 | 316114 |
| xls | 3 | 458 | 487 |
| xlsx | 5 | 1223 | 2929 |

## Validation and cross-verification checks

| File | Check | Result |
|---|---|---|
| wrong_total.pdf | TOTAL_MISMATCH | pass |
| xcheck_match.pdf + xcheck_match.xlsx | cross-document match | pass |
| xcheck_mismatch.pdf + xcheck_mismatch.xlsx | cross-document mismatch | pass |

## Documents that did not succeed

| File | Kind | Status | Error |
|---|---|---|---|
| sroie_X51005288570.jpg | public_receipt | needs_review | No invoice found in this document |

## Scoring rules

- A field is correct when it equals the label after normalisation: amounts as decimals, dates as ISO, invoice numbers compared on letters and digits only, party names with a similarity of at least 0.9 after lower-casing and removing punctuation.
- When a field is not printed on the document (label is null), it is correct only if the system also returns null: invented values count as errors.
- Public receipts (SROIE) are labeled only for supplier, date and total; other fields are not scored there.
- Line items match on equal amount and description similarity of at least 0.8.
- A valid document succeeds when it finishes (completed or needs review) with at least one invoice; a corrupted or blank file succeeds when it is rejected.
