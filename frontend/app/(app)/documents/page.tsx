"use client";

import { FileStack, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { DocumentTable, isActiveDoc } from "@/components/documents/DocumentTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SimpleSelect } from "@/components/Field";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { ListSkeleton } from "@/components/Spinner";
import { TableToolbar } from "@/components/TableToolbar";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { usePoll } from "@/hooks/usePoll";
import { api, errorMessage, withQuery } from "@/lib/api";
import type { DocumentStatus, DocumentSummary, Paged, Stats } from "@/lib/types";

const PAGE_SIZE = 25;
const STATUSES: { value: DocumentStatus; label: string }[] = [
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "needs_review", label: "Needs review" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];
const TYPES = [
  { value: "", label: "All types" },
  ...["pdf", "image", "tiff", "xlsx", "xls", "csv", "unknown"].map((t) => ({ value: t, label: t === "unknown" ? "Unsupported" : t.toUpperCase() })),
];

function DocumentsView() {
  const params = useSearchParams();
  const [status, setStatus] = useState<string | null>(params.get("status"));
  const [fileType, setFileType] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [retrying, setRetrying] = useState(false);

  const { data, error, loading, reload } = useApi<Paged<DocumentSummary>>(withQuery("/api/documents", { status, file_type: fileType, q: query, page, page_size: PAGE_SIZE }));
  const stats = useApi<Stats>("/api/stats");
  const refresh = () => Promise.all([reload(), stats.reload()]);
  usePoll(refresh, !!data?.items.some(isActiveDoc));

  const by = stats.data?.documents_by_status;
  const tabs = [{ value: null, label: "All", count: stats.data?.documents }, ...STATUSES.map((s) => ({ ...s, count: by ? (by[s.value] ?? 0) : undefined }))];
  const filtered = !!(status || fileType || query);

  async function retryFailed() {
    setRetrying(true);
    try {
      const res = await api<{ requeued: string[] }>("/api/documents/reprocess-failed", { method: "POST" });
      if (res.requeued.length) toast.success(`${res.requeued.length} document(s) queued for another attempt`);
      else toast.info("No failed or stuck documents to retry");
      await refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setRetrying(false);
    }
  }

  function clear() {
    setStatus(null);
    setFileType("");
    setQ("");
    setQuery("");
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="Documents"
        description="Every uploaded file with its processing status. The list refreshes while jobs run."
        actions={
          <>
            <Button variant="outline" onClick={retryFailed} loading={retrying}>
              {!retrying && <RotateCcw aria-hidden />} Retry failed or stuck
            </Button>
            <Button asChild><Link href="/">Upload</Link></Button>
          </>
        }
      />
      <section className="rounded-lg border border-border bg-card">
        <TableToolbar
          tabs={tabs}
          activeTab={status}
          tabsLabel="Document status"
          onSelectTab={(v) => { setStatus(v); setPage(1); }}
          search={q}
          onSearch={setQ}
          onSubmit={() => { setQuery(q.trim()); setPage(1); }}
          searchLabel="Search filename or text"
          searchPlaceholder="Filename or text"
        >
          <SimpleSelect id="doc-type" value={fileType} onChange={(v) => { setFileType(v); setPage(1); }} options={TYPES} className="h-9 w-36" />
        </TableToolbar>
        {error ? (
          <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>
        ) : loading && !data ? (
          <ListSkeleton label="Loading documents" />
        ) : !data?.items.length ? (
          <EmptyState
            icon={FileStack}
            title={filtered ? "No documents match your filters" : "No documents yet"}
            description={filtered ? "Try another search term or clear the active filters." : "Upload invoices from the dashboard and they appear here."}
            action={filtered && <Button variant="outline" onClick={clear}>Clear filters</Button>}
          />
        ) : (
          <>
            <DocumentTable docs={data.items} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<ListSkeleton />}>
      <DocumentsView />
    </Suspense>
  );
}
