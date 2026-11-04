"use client";

import { ArrowUpRight, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Empty } from "@/components/Empty";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { ListSkeleton } from "@/components/Spinner";
import { useApi } from "@/hooks/useApi";
import { withQuery } from "@/lib/api";
import { formatMoney, timeAgo } from "@/lib/format";
import type { Invoice, Paged } from "@/lib/types";

const PAGE_SIZE = 25;

/** Most severe first: errors before warnings; ties keep the API order, which is oldest first. */
function priority(inv: Invoice) {
  return inv.issues.filter((i) => i.severity === "error").length * 100 + inv.issues.length;
}

export default function ReviewPage() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi<Paged<Invoice>>(withQuery("/api/invoices", { needs_review: true, sort: "created_at", page, page_size: PAGE_SIZE }));
  // shortcut: priority sort applies within the current page only; fine while the queue fits in a page or two.
  const items = data ? [...data.items].sort((a, b) => priority(b) - priority(a)) : [];

  return (
    <>
      <PageHeader title="Review queue" description="Invoices flagged by validation, most severe first. Open one to correct values and approve it." />
      <section className="rounded-lg border border-border bg-card">
        {error ? (
          <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>
        ) : loading && !data ? (
          <ListSkeleton label="Loading review queue" />
        ) : !items.length ? (
          <EmptyState icon={ClipboardCheck} title="Nothing to review" description="Every extracted invoice has passed validation or been approved." />
        ) : (
          <>
            <ul className="divide-y divide-border">
              {items.map((inv) => (
                <li key={inv.id}>
                  <Link href={`/invoices/${inv.id}`} className="flex gap-4 px-4 py-4 transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-mono text-sm font-medium">{inv.invoice_number ?? <Empty text="No number" />}</span>
                        <span className="text-sm">{inv.supplier_name ?? <Empty text="Supplier not found" />}</span>
                        <span className="font-mono text-sm tabular-nums">{inv.total !== null ? formatMoney(inv.total, inv.currency) : <Empty text="Total not found" />}</span>
                      </div>
                      <ul className="mt-2 space-y-1">
                        {inv.issues.slice(0, 3).map((i, n) => (
                          <li key={n} className="flex items-start gap-2 text-sm">
                            <Badge tone={i.severity === "error" ? "rose" : "amber"}>{i.severity}</Badge>
                            <span className="text-muted-foreground">{i.message}</span>
                          </li>
                        ))}
                        {!inv.issues.length && <li className="text-sm text-muted-foreground">Flagged for review, no specific issue recorded.</li>}
                        {inv.issues.length > 3 && <li className="text-xs text-muted-foreground">and {inv.issues.length - 3} more</li>}
                      </ul>
                    </div>
                    <div className="hidden shrink-0 flex-col items-end gap-1 text-right sm:flex">
                      <span className="max-w-56 truncate text-xs text-muted-foreground">{inv.filename}</span>
                      <span className="font-mono text-xs text-muted-foreground">{timeAgo(inv.updated_at)}</span>
                    </div>
                    <ArrowUpRight size={14} aria-hidden className="mt-1 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}
