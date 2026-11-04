"use client";

import { CheckCircle2, UploadCloud, XCircle } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import { Alert } from "@/components/Alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api, errorMessage } from "@/lib/api";
import type { UploadResult } from "@/lib/types";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.xlsx,.xls,.csv";
const MAX_BYTES = 50 * 1024 * 1024;

/** Multi-file drag-and-drop upload. The server checks content type itself; this only pre-screens size. */
export function UploadZone({ onUploaded }: { onUploaded?: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function upload(list: FileList | File[]) {
    const files = Array.from(list);
    if (!files.length) return;
    const tooBig = files.filter((f) => f.size > MAX_BYTES);
    const ok = files.filter((f) => f.size <= MAX_BYTES);
    const local: UploadResult["rejected"] = tooBig.map((f) => ({ filename: f.name, reason: "File is larger than 50 MB" }));
    setError(null);
    setResult(null);
    if (!ok.length) {
      setResult({ accepted: [], rejected: local });
      return;
    }
    const form = new FormData();
    ok.forEach((f) => form.append("files", f));
    setBusy(true);
    try {
      const res = await api<UploadResult>("/api/documents", { method: "POST", body: form });
      setResult({ accepted: res.accepted, rejected: [...local, ...res.rejected] });
      if (res.accepted.length) toast.success(`${res.accepted.length} file(s) queued for processing`);
      onUploaded?.();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) void upload(e.dataTransfer.files);
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn("flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors", dragging ? "border-primary bg-primary/5" : "border-border bg-muted/30")}
      >
        <span className="inline-flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <UploadCloud className="size-6" aria-hidden />
        </span>
        <p className="mt-3 text-sm font-medium text-foreground">Drop invoices here</p>
        <p className="mt-0.5 text-xs text-muted-foreground">PDF, JPG, PNG, TIFF, XLSX, XLS or CSV, up to 50 MB each</p>
        <input
          ref={input}
          id="upload-input"
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(e) => e.target.files && void upload(e.target.files)}
        />
        <Button className="mt-4" variant="outline" loading={busy} onClick={() => input.current?.click()}>
          {busy ? "Uploading" : "Choose files"}
        </Button>
      </div>

      {error && <Alert tone="error" title="Upload failed">{error}</Alert>}

      {result && (result.accepted.length > 0 || result.rejected.length > 0) && (
        <ul className="divide-y divide-border rounded-lg border border-border text-sm" aria-label="Upload results">
          {result.accepted.map((a) => (
            <li key={a.id} className="flex items-start gap-2 px-3 py-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
              <div className="min-w-0 flex-1">
                <Link href={`/documents/${a.id}`} className="font-medium hover:text-primary hover:underline">
                  {a.filename}
                </Link>
                <span className="ml-2 font-mono text-xs text-muted-foreground uppercase">{a.file_type}</span>
                {a.duplicate_of && (
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    Same content was uploaded before.{" "}
                    <Link href={`/documents/${a.duplicate_of}`} className="underline">
                      View earlier copy
                    </Link>
                  </p>
                )}
              </div>
              <span className="text-xs text-muted-foreground">Queued</span>
            </li>
          ))}
          {result.rejected.map((r, i) => (
            <li key={`${r.filename}-${i}`} className="flex items-start gap-2 px-3 py-2">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" aria-hidden />
              <div className="min-w-0 flex-1">
                <span className="font-medium">{r.filename}</span>
                <p className="text-xs text-rose-700 dark:text-rose-300">{r.reason}</p>
              </div>
              <span className="text-xs text-rose-700 dark:text-rose-300">Rejected</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
