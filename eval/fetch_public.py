"""Download real scanned receipts with labels from the ICDAR 2019 SROIE test set (via the Hugging Face
datasets server) into dataset/public/. Labels: company (supplier), date, total."""

import ast
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

API = "https://datasets-server.huggingface.co/rows"
DATASET = "jsdnrs/ICDAR2019-SROIE"


def iso(d: str) -> str | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%d %b %Y", "%d %b %y"):
        try:
            return datetime.strptime(d.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def main(n: int = 20) -> None:
    out = Path(__file__).parent / "dataset" / "public"
    out.mkdir(parents=True, exist_ok=True)
    rows = httpx.get(API, params={"dataset": DATASET, "config": "default", "split": "test", "offset": 0, "length": n}, timeout=60).json()["rows"]
    cases = []
    for item in rows:
        row = item["row"]
        image = row["image"] if isinstance(row["image"], dict) else ast.literal_eval(row["image"])
        ents = row["entities"] if isinstance(row["entities"], dict) else ast.literal_eval(row["entities"])
        name = f"sroie_{row['key']}.jpg"
        (out / name).write_bytes(httpx.get(image["src"], timeout=60).content)
        cases.append({
            "file": name,
            "kind": "public_receipt",
            # Only these fields are labeled in SROIE; the others are not scored.
            "labeled_fields": ["supplier_name", "invoice_date", "total"],
            "invoices": [{"supplier_name": ents.get("company"), "invoice_date": iso(ents.get("date", "")), "total": ents.get("total")}],
        })
    (out / "labels.json").write_text(json.dumps(cases, indent=2))
    print(f"{len(cases)} receipts written to {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
