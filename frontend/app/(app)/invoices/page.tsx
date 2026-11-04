"use client";

import { Receipt, SlidersHorizontal } from "lucide-react";
import { useState, type FormEvent } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Field } from "@/components/Field";
import { InvoiceTable, type SortKey } from "@/components/invoices/InvoiceTable";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { ListSkeleton } from "@/components/Spinner";
import { TableToolbar } from "@/components/TableToolbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/useApi";
import { withQuery } from "@/lib/api";
import type { Invoice, Paged } from "@/lib/types";

const PAGE_SIZE = 25;
const ADVANCED = { supplier: "", customer: "", invoice_number: "", currency: "", date_from: "", date_to: "", min_total: "", max_total: "" };
type Advanced = typeof ADVANCED;

const FIELDS: { key: keyof Advanced; label: string; type?: string; placeholder?: string }[] = [
  { key: "supplier", label: "Supplier" },
  { key: "customer", label: "Customer" },
  { key: "invoice_number", label: "Invoice number" },
  { key: "currency", label: "Currency", placeholder: "USD" },
  { key: "date_from", label: "Date from", type: "date" },
  { key: "date_to", label: "Date to", type: "date" },
  { key: "min_total", label: "Min total", type: "number" },
  { key: "max_total", label: "Max total", type: "number" },
];

// The review flag and the status overlap, so "Needs review" filters on the flag the validator sets.
const TABS = [
  { value: null, label: "All" },
  { value: "review", label: "Needs review" },
  { value: "extracted", label: "Extracted" },
  { value: "approved", label: "Approved" },
];

export default function InvoicesPage() {
  const [tab, setTab] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Advanced>(ADVANCED);
  const [applied, setApplied] = useState<Advanced>(ADVANCED);
  const [page, setPage] = useState(1);

  const filters = { ...applied, q: query, sort, needs_review: tab === "review" ? true : undefined, status: tab && tab !== "review" ? tab : undefined };
  const { data, error, loading, reload } = useApi<Paged<Invoice>>(withQuery("/api/invoices", { ...filters, page, page_size: PAGE_SIZE }));
  const activeAdvanced = Object.values(applied).filter(Boolean).length;
  const filtered = !!(tab || query || activeAdvanced);

  function onSort(key: SortKey) {
    setSort((s) => (s === `-${key}` ? key : `-${key}`));
    setPage(1);
  }
  function apply(e: FormEvent) {
    e.preventDefault();
    setApplied(Object.fromEntries(Object.entries(draft).map(([k, v]) => [k, v.trim()])) as Advanced);
    setPage(1);
  }
  function clear() {
    setTab(null);
    setQ("");
    setQuery("");
    setDraft(ADVANCED);
    setApplied(ADVANCED);
    setPage(1);
  }

  return (
    <>
      <PageHeader title="Invoices" description="Every extracted invoice. Filter by party, number, date or amount, and sort by column." />
      <section className="rounded-lg border border-border bg-card">
        <TableToolbar
          tabs={TABS}
          activeTab={tab}
          tabsLabel="Invoice status"
          onSelectTab={(v) => { setTab(v); setPage(1); }}
          search={q}
          onSearch={setQ}
          onSubmit={() => { setQuery(q.trim()); setPage(1); }}
          searchLabel="Keyword search"
          searchPlaceholder="Keywords"
        >
          <Button type="button" variant="outline" size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls="invoice-filters">
            <SlidersHorizontal aria-hidden /> Filters{activeAdvanced > 0 && <span className="font-mono text-muted-foreground">({activeAdvanced})</span>}
          </Button>
        </TableToolbar>
        {open && (
          <form id="invoice-filters" onSubmit={apply} className="grid gap-3 border-b border-border p-4 sm:grid-cols-2 lg:grid-cols-4">
            {FIELDS.map(({ key, label, type, placeholder }) => (
              <Field key={key} label={label} htmlFor={`f-${key}`}>
                <Input id={`f-${key}`} type={type ?? "text"} step={type === "number" ? "0.01" : undefined} placeholder={placeholder} className="h-9" value={draft[key]} onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))} />
              </Field>
            ))}
            <div className="flex justify-end gap-2 sm:col-span-2 lg:col-span-4">
              <Button type="button" variant="ghost" onClick={clear}>Clear all</Button>
              <Button type="submit">Apply filters</Button>
            </div>
          </form>
        )}
        {error ? (
          <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>
        ) : loading && !data ? (
          <ListSkeleton label="Loading invoices" />
        ) : !data?.items.length ? (
          <EmptyState
            icon={Receipt}
            title={filtered ? "No invoices match your filters" : "No invoices yet"}
            description={filtered ? "Try a different search term or clear the active filters." : "Invoices appear here once uploaded documents are processed."}
            action={filtered && <Button variant="outline" onClick={clear}>Clear filters</Button>}
          />
        ) : (
          <>
            <InvoiceTable invoices={data.items} sort={sort} onSort={onSort} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}
