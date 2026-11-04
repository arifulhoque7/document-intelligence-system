"use client";

import { GitCompareArrows } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/Badge";
import { DataTable, TBody, Td, Th, THead, Tr } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { ListSkeleton } from "@/components/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useApi } from "@/hooks/useApi";
import { labelize } from "@/lib/format";
import type { CrossCheck, CrossCheckSide } from "@/lib/types";

function Side({ side, label }: { side: CrossCheckSide; label: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted/40 px-3 py-2">
      <p className="text-[12px] text-muted-foreground uppercase">{label}</p>
      <Link href={`/invoices/${side.invoice_id}`} className="block truncate text-sm font-medium hover:text-primary hover:underline" title={side.filename}>
        {side.filename}
      </Link>
      <Link href={`/documents/${side.document_id}`} className="text-xs text-muted-foreground hover:text-primary hover:underline">
        Open document
      </Link>
    </div>
  );
}

export default function CrossChecksPage() {
  const [onlyMismatches, setOnlyMismatches] = useState(false);
  const { data, error, loading, reload } = useApi<CrossCheck[]>(`/api/cross-checks?only_mismatches=${onlyMismatches}`);
  const mismatches = data?.filter((c) => c.status === "mismatch").length ?? 0;

  return (
    <>
      <PageHeader
        title="Cross-checks"
        description={data ? `${data.length} pair(s) of the same invoice found in different documents, ${mismatches} with differences.` : "The same invoice found in different documents, compared field by field."}
        actions={
          <div className="flex items-center gap-2">
            <Checkbox id="only-mismatches" checked={onlyMismatches} onCheckedChange={(v) => setOnlyMismatches(v === true)} />
            <Label htmlFor="only-mismatches">Only show mismatches</Label>
          </div>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <section className="rounded-lg border border-border bg-card"><ListSkeleton label="Loading cross-checks" /></section>
      ) : !data?.length ? (
        <section className="rounded-lg border border-border bg-card">
          <EmptyState
            icon={GitCompareArrows}
            title={onlyMismatches ? "No mismatches found" : "No cross-document pairs yet"}
            description="A pair appears when the same invoice number is found in two different documents, for example a PDF and a spreadsheet export."
          />
        </section>
      ) : (
        <div className="space-y-3">
          {data.map((c, i) => {
            const diffs = Object.entries(c.differences);
            return (
              <section key={`${c.a.invoice_id}-${c.b.invoice_id}-${i}`} className="rounded-lg border border-border bg-card">
                <header className="flex flex-wrap items-center gap-2 px-4 pt-4">
                  <span className="font-mono text-sm font-semibold">{c.invoice_number}</span>
                  <Badge tone="violet" className="font-mono">{c.kind}</Badge>
                  <StatusBadge status={c.status} />
                </header>
                <div className="grid gap-3 p-4 sm:grid-cols-2">
                  <Side side={c.a} label="Record A" />
                  <Side side={c.b} label="Record B" />
                </div>
                {diffs.length > 0 ? (
                  <div className="border-t border-border">
                    <DataTable label={`Differences for ${c.invoice_number}`}>
                      <THead>
                        <Th edge="start">Field</Th>
                        <Th>Record A</Th>
                        <Th edge="end">Record B</Th>
                      </THead>
                      <TBody>
                        {diffs.map(([field, [a, b]]) => (
                          <Tr key={field} dense>
                            <Td edge="start" className="text-muted-foreground">{labelize(field)}</Td>
                            <Td className="font-mono text-rose-700 dark:text-rose-400">{a}</Td>
                            <Td edge="end" className="font-mono text-rose-700 dark:text-rose-400">{b}</Td>
                          </Tr>
                        ))}
                      </TBody>
                    </DataTable>
                  </div>
                ) : (
                  <p className="px-4 pb-4 text-sm text-emerald-700 dark:text-emerald-400">All compared fields agree.</p>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
