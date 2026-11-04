"use client";

import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/Alert";
import { Empty } from "@/components/Empty";
import { EmptyState } from "@/components/EmptyState";
import { Highlight } from "@/components/Highlight";
import { IssueCounts } from "@/components/invoices/IssueCounts";
import { PageHeader } from "@/components/PageHeader";
import { ListSkeleton } from "@/components/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError, errorMessage, withQuery } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { SearchMode, SearchResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const MODES: { value: SearchMode; label: string; help: string }[] = [
  { value: "keyword", label: "Keyword", help: "Exact words in invoice numbers, parties and document text." },
  { value: "semantic", label: "Semantic", help: "Matches by meaning using embeddings. Needs an embedding provider." },
  { value: "hybrid", label: "Hybrid", help: "Keyword and semantic results combined." },
];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(m: SearchMode, e?: FormEvent) {
    e?.preventDefault();
    const term = q.trim();
    if (!term) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api<SearchResult>(withQuery("/api/search", { q: term, mode: m, limit: 50 })));
    } catch (err) {
      setResult(null);
      setError({ status: err instanceof ApiError ? err.status : 0, message: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  function changeMode(m: SearchMode) {
    setMode(m);
    if (result || error) void run(m);
  }

  return (
    <>
      <PageHeader title="Search" description="Find invoices across every processed document." />
      <section className="rounded-lg border border-border bg-card p-4">
        <form onSubmit={(e) => run(mode, e)} role="search" className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground" />
            <Input type="search" aria-label="Search query" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Office chairs from Contoso, INV-2025-0937, 483.46" maxLength={500} className="pl-9" />
          </div>
          <div role="radiogroup" aria-label="Search mode" className="inline-flex gap-1 rounded-lg bg-muted p-1">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={mode === m.value}
                onClick={() => changeMode(m.value)}
                className={cn(
                  "rounded-md px-3.5 py-1.5 text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                  mode === m.value ? "bg-background font-medium shadow-xs" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
          <Button type="submit" loading={busy} disabled={!q.trim()}>
            Search
          </Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">{MODES.find((m) => m.value === mode)?.help}</p>
      </section>

      <div className="mt-4">
        {error ? (
          <Alert
            tone={error.status === 503 ? "warning" : "error"}
            title={error.status === 503 ? "Semantic search is not available" : "Search failed"}
            action={error.status === 503 && mode !== "keyword" && <Button size="compact" variant="outline" onClick={() => changeMode("keyword")}>Use keyword search</Button>}
          >
            {error.message}
          </Alert>
        ) : busy && !result ? (
          <section className="rounded-lg border border-border bg-card"><ListSkeleton rows={4} label="Searching" /></section>
        ) : !result ? (
          <section className="rounded-lg border border-border bg-card"><EmptyState icon={Search} title="Search your invoices" description="Type a supplier, an invoice number, an amount or a description." /></section>
        ) : !result.items.length ? (
          <section className="rounded-lg border border-border bg-card"><EmptyState icon={Search} title="No results" description="Try other words, or switch the search mode." /></section>
        ) : (
          <section className="rounded-lg border border-border bg-card">
            <header className="flex items-baseline justify-between gap-3 border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Results</h2>
              <span className="font-mono text-xs text-muted-foreground">{result.items.length} found, {result.mode}</span>
            </header>
            <ul className="divide-y divide-border">
              {result.items.map((hit) => (
                <li key={hit.id}>
                  <Link href={`/invoices/${hit.id}`} className="flex gap-4 px-4 py-3 transition-colors hover:bg-muted/40">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-mono text-sm font-medium">{hit.invoice_number ?? <Empty text="No number" />}</span>
                        <span className="text-sm">{hit.supplier_name ?? <Empty text="Supplier not found" />}</span>
                        <span className="font-mono text-sm tabular-nums">{hit.total !== null ? formatMoney(hit.total, hit.currency) : <Empty text="Total not found" />}</span>
                        <StatusBadge status={hit.status} />
                        <IssueCounts issues={hit.issues} />
                      </div>
                      {hit.snippet && (
                        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                          <Highlight text={hit.snippet} />
                        </p>
                      )}
                      <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{hit.filename}</p>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-muted-foreground tabular-nums" title="Relevance score">{hit.score.toFixed(3)}</span>
                    <ArrowUpRight size={14} aria-hidden className="mt-0.5 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}
