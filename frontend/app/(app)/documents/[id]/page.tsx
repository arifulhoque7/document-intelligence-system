"use client";

import { Download, RotateCcw } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Alert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { DataTable, TBody, Td, Th, THead, Tr } from "@/components/DataTable";
import { isActiveDoc } from "@/components/documents/DocumentTable";
import { TextViewer } from "@/components/documents/TextViewer";
import { Empty } from "@/components/Empty";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { InvoiceTable } from "@/components/invoices/InvoiceTable";
import { PageHeader } from "@/components/PageHeader";
import { ProgressBar } from "@/components/ProgressBar";
import { PageSkeleton } from "@/components/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { usePoll } from "@/hooks/usePoll";
import { usePageCrumb } from "@/hooks/useSession";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, formatDateTime, formatDuration, labelize } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";

const DOT = { ok: "success", started: "primary", warning: "warning", failed: "danger" } as const;

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc, error, loading, reload } = useApi<DocumentDetail>(`/api/documents/${id}`);
  const [busy, setBusy] = useState(false);
  const active = !!doc && isActiveDoc(doc);
  usePoll(reload, active);
  usePageCrumb(doc?.filename);

  async function reprocess() {
    setBusy(true);
    try {
      await api(`/api/documents/${id}/reprocess`, { method: "POST" });
      toast.success("Document queued for reprocessing");
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !doc) return <PageSkeleton label="Loading document" />;

  return (
    <>
      <PageHeader
        title={doc.filename}
        description={
          <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <StatusBadge status={doc.status} />
            <span className="font-mono text-xs uppercase">{doc.file_type}</span>
            <span className="font-mono text-xs">{formatBytes(doc.size_bytes)}</span>
            <span className="font-mono text-xs">{formatDateTime(doc.created_at)}</span>
            {doc.processing_ms !== null && <span className="font-mono text-xs">{formatDuration(doc.processing_ms)}</span>}
            <span className="font-mono text-xs">attempts {doc.attempts}</span>
          </span>
        }
        actions={
          <>
            {/* A plain link: the API serves the file as an attachment, never inline. */}
            <Button asChild variant="outline">
              <a href={`/api/documents/${doc.id}/file`} download>
                <Download aria-hidden /> Download original
              </a>
            </Button>
            <Button onClick={reprocess} loading={busy} disabled={active || doc.file_type === "unknown"} title={doc.file_type === "unknown" ? "Unsupported file type" : undefined}>
              {!busy && <RotateCcw aria-hidden />} Reprocess
            </Button>
          </>
        }
      />

      <div className="space-y-4">
        {doc.error && <Alert tone="error" title="Processing failed">{doc.error}</Alert>}
        {active && (
          <section className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-sm text-muted-foreground">Processing. This page updates automatically.</p>
            <ProgressBar value={doc.progress} status={doc.status} label="Processing progress" />
          </section>
        )}

        <div className="grid gap-4 xl:grid-cols-3">
          <div className="space-y-4 xl:col-span-2">
            <Card flush title="Invoices found" caption={`${doc.invoices.length} extracted`}>
              {doc.invoices.length ? (
                <InvoiceTable invoices={doc.invoices} showDocument={false} dense />
              ) : (
                <EmptyState compact title={active ? "Invoices appear when processing finishes." : "No invoices were extracted from this document."} />
              )}
            </Card>
            <Card flush title="Pages" caption={`${doc.pages.length} read`}>
              {doc.pages.length ? (
                <DataTable label="Pages">
                  <THead>
                    <Th edge="start">Page</Th>
                    <Th>Method</Th>
                    <Th align="right">OCR confidence</Th>
                    <Th edge="end" align="right">Characters</Th>
                  </THead>
                  <TBody>
                    {doc.pages.map((p) => (
                      <Tr key={`${p.page_no}-${p.sheet_name}`} dense>
                        <Td edge="start">{p.sheet_name ? `Sheet ${p.sheet_name}` : <span className="font-mono">{p.page_no}</span>}</Td>
                        <Td className="font-mono text-xs uppercase">{p.method}</Td>
                        <Td align="right" className="font-mono tabular-nums">{p.ocr_confidence !== null ? `${Math.round(p.ocr_confidence * 100)}%` : <Empty text="n/a" />}</Td>
                        <Td edge="end" align="right" className="font-mono tabular-nums">{p.chars.toLocaleString()}</Td>
                      </Tr>
                    ))}
                  </TBody>
                </DataTable>
              ) : (
                <EmptyState compact title="No pages read yet." />
              )}
            </Card>
            <Card title="Extracted text">
              <TextViewer documentId={doc.id} version={active ? null : doc.updated_at} />
            </Card>
          </div>
          <Card title="Processing timeline">
            {doc.events.length ? (
              <Timeline
                items={doc.events.map((e, i) => ({
                  key: `${e.at}-${i}`,
                  dot: DOT[e.status] ?? "muted",
                  title: (
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{labelize(e.stage)}</span>
                      <StatusBadge status={e.status} />
                    </span>
                  ),
                  meta: `${formatDateTime(e.at)}${e.duration_ms !== null ? `, ${formatDuration(e.duration_ms)}` : ""}`,
                  body: e.message ? <p className="text-sm break-words text-muted-foreground">{e.message}</p> : undefined,
                }))}
              />
            ) : (
              <EmptyState compact title="No events yet." />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
