import type { DocumentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const COLOR: Record<DocumentStatus, string> = {
  queued: "bg-muted-foreground/40",
  processing: "bg-amber-500",
  completed: "bg-emerald-500",
  needs_review: "bg-indigo-500",
  failed: "bg-rose-500",
};

export function ProgressBar({ value, status, label }: { value: number; status?: DocumentStatus; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="flex items-center gap-2">
      <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label ?? "Progress"} className="h-1.5 w-full min-w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-[width] duration-500", status ? COLOR[status] : "bg-primary", status === "processing" && "animate-pulse")} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 text-right font-mono text-xs text-muted-foreground tabular-nums">{pct}%</span>
    </div>
  );
}
