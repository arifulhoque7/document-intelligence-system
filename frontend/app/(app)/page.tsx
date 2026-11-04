"use client";

import { AlertTriangle, ArrowUpRight, FileStack, Gauge, Receipt } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card } from "@/components/Card";
import { isActiveDoc } from "@/components/documents/DocumentTable";
import { UploadZone } from "@/components/documents/UploadZone";
import { Empty } from "@/components/Empty";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { ProgressBar } from "@/components/ProgressBar";
import { ListSkeleton } from "@/components/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { usePoll } from "@/hooks/usePoll";
import { useSession } from "@/hooks/useSession";
import { formatDuration, formatMoney, labelize, timeAgo } from "@/lib/format";
import type { DocumentStatus, DocumentSummary, Invoice, Paged, Stats } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_ORDER: DocumentStatus[] = ["queued", "processing", "completed", "needs_review", "failed"];
const BAR: Record<DocumentStatus, string> = { queued: "bg-muted-foreground/40", processing: "bg-amber-500", completed: "bg-emerald-500", needs_review: "bg-indigo-500", failed: "bg-rose-500" };

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function Metric({ icon: Icon, label, value, meta }: { icon: LucideIcon; label: string; value: ReactNode; meta: ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Icon size={16} aria-hidden />
      </span>
      <div className="min-w-0">
        <dt className="text-xs text-muted-foreground">{label}</dt>
        <dd className="font-mono text-xl font-semibold text-foreground tabular-nums">{value}</dd>
        <p className="truncate text-[11px] text-muted-foreground">{meta}</p>
      </div>
    </div>
  );
}

function ListCard({ title, caption, children }: { title: string; caption: string; children: ReactNode }) {
  return (
    <Card flush title={title} caption={caption}>
      {children}
    </Card>
  );
}

export default function DashboardPage() {
  const user = useSession();
  const stats = useApi<Stats>("/api/stats");
  const recent = useApi<Paged<DocumentSummary>>("/api/documents?page_size=6");
  const attention = useApi<Paged<Invoice>>("/api/invoices?needs_review=true&sort=created_at&page_size=6");
  const active = !!recent.data?.items.some(isActiveDoc);

  const refresh = () => Promise.all([stats.reload(), recent.reload(), attention.reload()]);
  usePoll(refresh, active);

  const s = stats.data;
  const by = s?.documents_by_status ?? {};
  const inFlight = (by.queued ?? 0) + (by.processing ?? 0);
  const name = user.email.split("@")[0];

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${name}`}
        description={s ? `${s.invoices_needing_review} invoice${s.invoices_needing_review === 1 ? "" : "s"} need${s.invoices_needing_review === 1 ? "s" : ""} review${inFlight ? `, ${inFlight} document${inFlight === 1 ? "" : "s"} processing` : ""}.` : "Loading your workspace."}
        actions={
          <>
            <Button asChild variant="outline"><Link href="/documents">View all documents</Link></Button>
            <Button asChild><Link href="/review">Open review queue</Link></Button>
          </>
        }
      />

      {stats.error ? (
        <div className="mb-4"><ErrorState error={stats.error} onRetry={stats.reload} /></div>
      ) : !s ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[86px]" />)}
        </div>
      ) : (
        <dl className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric icon={FileStack} label="Documents" value={s.documents.toLocaleString()} meta={inFlight ? `${inFlight} queued or processing` : "None in progress"} />
          <Metric icon={Receipt} label="Invoices extracted" value={s.invoices.toLocaleString()} meta="Across all documents" />
          <Metric icon={AlertTriangle} label="Needs review" value={s.invoices_needing_review.toLocaleString()} meta="Flagged by validation" />
          <Metric
            icon={Gauge}
            label="Failure rate"
            value={s.failure_rate === null ? "n/a" : `${(s.failure_rate * 100).toFixed(1)}%`}
            meta={s.avg_processing_ms === null ? "No timings yet" : `${formatDuration(s.avg_processing_ms)} average processing`}
          />
        </dl>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card title="Upload documents" caption="PDF, images and spreadsheets">
            <UploadZone onUploaded={refresh} />
          </Card>

          <ListCard title="Needs attention" caption="Oldest flagged invoices first">
            {attention.error ? (
              <div className="p-4"><ErrorState error={attention.error} onRetry={attention.reload} /></div>
            ) : !attention.data ? (
              <ListSkeleton rows={3} />
            ) : !attention.data.items.length ? (
              <EmptyState compact title="Nothing is waiting. The review queue is clear." />
            ) : (
              <ul className="divide-y divide-border">
                {attention.data.items.map((inv) => (
                  <li key={inv.id}>
                    <Link href={`/invoices/${inv.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40">
                      <span className="w-32 shrink-0 truncate font-mono text-sm font-medium">{inv.invoice_number ?? <Empty text="No number" />}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm">{inv.issues[0]?.message ?? "Flagged for review"}</span>
                        <span className="block truncate font-mono text-xs text-muted-foreground">{inv.filename}</span>
                      </span>
                      <StatusBadge status={inv.status} />
                      <span className="hidden w-28 shrink-0 text-right font-mono text-sm tabular-nums sm:block">{inv.total !== null ? formatMoney(inv.total, inv.currency) : <Empty />}</span>
                      <ArrowUpRight size={14} aria-hidden className="shrink-0 text-muted-foreground" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </ListCard>

          <ListCard title="Recent documents" caption={active ? "Updating live" : "Newest first"}>
            {recent.error ? (
              <div className="p-4"><ErrorState error={recent.error} onRetry={recent.reload} /></div>
            ) : !recent.data ? (
              <ListSkeleton rows={4} />
            ) : !recent.data.items.length ? (
              <EmptyState compact title="No documents yet. Upload a file to get started." />
            ) : (
              <ul className="divide-y divide-border">
                {recent.data.items.map((d) => (
                  <li key={d.id}>
                    <Link href={`/documents/${d.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{d.filename}</span>
                        <span className="block font-mono text-xs text-muted-foreground">{timeAgo(d.created_at)}</span>
                      </span>
                      <span className="hidden w-36 sm:block"><ProgressBar value={d.progress} status={d.status} label={`Progress for ${d.filename}`} /></span>
                      <StatusBadge status={d.status} />
                      <ArrowUpRight size={14} aria-hidden className="shrink-0 text-muted-foreground" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </ListCard>
        </div>

        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground">Processing status</h2>
            {!s ? (
              <div className="mt-4 space-y-3">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-6" />)}</div>
            ) : (
              <ul className="mt-4 space-y-3">
                {STATUS_ORDER.map((st) => {
                  const count = by[st] ?? 0;
                  const share = s.documents ? (count / s.documents) * 100 : 0;
                  return (
                    <li key={st}>
                      <Link href={`/documents?status=${st}`} className="flex items-center justify-between gap-3 text-sm hover:text-primary">
                        <span>{labelize(st)}</span>
                        <span className="font-mono text-xs text-muted-foreground tabular-nums">
                          {count}, {share.toFixed(0)}%
                        </span>
                      </Link>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                        <div className={cn("h-full rounded-full", BAR[st])} style={{ width: `${share}%` }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground">How it works</h2>
            <ol className="mt-3 list-decimal space-y-1.5 pl-4 text-sm text-muted-foreground">
              <li>Upload files. Each one is checked by content and queued.</li>
              <li>Text is read directly, by OCR, or from the sheet.</li>
              <li>Invoices are extracted, validated and cross-checked.</li>
              <li>Review flagged invoices, correct values and approve.</li>
            </ol>
          </section>
        </div>
      </div>
    </>
  );
}
