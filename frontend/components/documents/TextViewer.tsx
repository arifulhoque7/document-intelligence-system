"use client";

import { ChevronRight } from "lucide-react";
import { Empty } from "@/components/Empty";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ListSkeleton } from "@/components/Spinner";
import { useApi } from "@/hooks/useApi";
import type { PageText } from "@/lib/types";

/** Extracted text per page or sheet, each collapsible. Rendered as plain text, never HTML. */
export function TextViewer({ documentId, version }: { documentId: string; version: string | null }) {
  // `version` changes when the document is reprocessed, which refetches the text.
  const { data, error, loading, reload } = useApi<PageText[]>(`/api/documents/${documentId}/text${version ? `?v=${encodeURIComponent(version)}` : ""}`);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <ListSkeleton rows={3} label="Loading text" />;
  if (!data?.length) return <EmptyState compact title="No text extracted yet." />;
  return (
    <div className="space-y-2">
      {data.map((p, i) => (
        <details key={`${p.page_no}-${p.sheet_name}`} open={i === 0} className="group rounded-md border border-border">
          <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-muted/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
            <ChevronRight className="size-4 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
            <span>{p.sheet_name ? `Sheet ${p.sheet_name}` : `Page ${p.page_no}`}</span>
            <span className="font-mono text-xs font-normal text-muted-foreground uppercase">
              {p.method}
              {p.ocr_confidence !== null && `, ocr ${Math.round(p.ocr_confidence * 100)}%`}
            </span>
          </summary>
          {p.text ? (
            <pre className="max-h-96 overflow-auto border-t border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">{p.text}</pre>
          ) : (
            <p className="border-t border-border p-3 text-sm"><Empty text="This page has no text" /></p>
          )}
        </details>
      ))}
    </div>
  );
}
