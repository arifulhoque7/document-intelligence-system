"use client";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ListSkeleton } from "@/components/Spinner";
import { Timeline } from "@/components/Timeline";
import { formatDateTime } from "@/lib/format";
import type { Revision } from "@/lib/types";
import { DiffList } from "./DiffList";

const SOURCE: Record<string, { label: string; dot: "muted" | "primary" | "success" }> = {
  extraction: { label: "Extracted", dot: "muted" },
  manual: { label: "Edited", dot: "primary" },
  approval: { label: "Approved", dot: "success" },
};

export function HistoryPanel({ revisions, error, onRetry }: { revisions: Revision[] | null; error: unknown; onRetry: () => void }) {
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!revisions) return <ListSkeleton rows={2} label="Loading history" />;
  if (!revisions.length) return <EmptyState compact title="No revisions yet." />;
  return (
    <Timeline
      items={[...revisions].reverse().map((r) => ({
        key: String(r.version),
        dot: SOURCE[r.source]?.dot ?? "muted",
        title: (
          <span>
            <span className="font-mono font-medium">v{r.version}</span> {SOURCE[r.source]?.label ?? r.source}
          </span>
        ),
        meta: `${formatDateTime(r.at)}, ${r.user_id !== null ? `user #${r.user_id}` : "system"}`,
        body: r.changes && Object.keys(r.changes).length > 0 ? <DiffList diff={r.changes} /> : undefined,
      }))}
    />
  );
}
