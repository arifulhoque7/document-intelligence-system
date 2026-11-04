import { FileText } from "lucide-react";
import Link from "next/link";
import { DataTable, TBody, Td, Th, THead, Tr } from "@/components/DataTable";
import { Empty } from "@/components/Empty";
import { ProgressBar } from "@/components/ProgressBar";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime, formatDuration } from "@/lib/format";
import type { DocumentSummary } from "@/lib/types";

export function isActiveDoc(d: { status: string }) {
  return d.status === "queued" || d.status === "processing";
}

export function DocumentTable({ docs }: { docs: DocumentSummary[] }) {
  return (
    <DataTable label="Documents">
      <THead>
        <Th edge="start">File</Th>
        <Th>Status</Th>
        <Th className="w-44">Progress</Th>
        <Th align="right">Pages</Th>
        <Th align="right">Invoices</Th>
        <Th align="right">To review</Th>
        <Th align="right">Time</Th>
        <Th edge="end">Uploaded</Th>
      </THead>
      <TBody>
        {docs.map((d) => (
          <Tr key={d.id}>
            <Td edge="start" className="max-w-xs">
              <div className="flex items-center gap-3">
                <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <FileText size={16} aria-hidden />
                </span>
                <div className="min-w-0">
                  <Link href={`/documents/${d.id}`} className="block truncate font-medium hover:text-primary hover:underline" title={d.filename}>
                    {d.filename}
                  </Link>
                  {d.error ? (
                    <p className="truncate text-xs text-rose-600 dark:text-rose-400" title={d.error}>{d.error}</p>
                  ) : (
                    <p className="font-mono text-xs text-muted-foreground uppercase">{d.file_type}</p>
                  )}
                </div>
              </div>
            </Td>
            <Td><StatusBadge status={d.status} /></Td>
            <Td><ProgressBar value={d.progress} status={d.status} label={`Progress for ${d.filename}`} /></Td>
            <Td align="right" className="font-mono tabular-nums">{d.page_count ?? <Empty text="n/a" />}</Td>
            <Td align="right" className="font-mono tabular-nums">{d.invoice_count}</Td>
            <Td align="right" className={d.review_count ? "font-mono font-semibold text-indigo-700 tabular-nums dark:text-indigo-300" : "font-mono tabular-nums"}>{d.review_count}</Td>
            <Td align="right" className="font-mono text-xs text-muted-foreground tabular-nums">{formatDuration(d.processing_ms) || "n/a"}</Td>
            <Td edge="end" className="font-mono text-xs whitespace-nowrap text-muted-foreground">{formatDateTime(d.created_at)}</Td>
          </Tr>
        ))}
      </TBody>
    </DataTable>
  );
}
