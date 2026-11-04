import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type TimelineItem = { key: string; title: ReactNode; meta: ReactNode; body?: ReactNode; dot?: "primary" | "muted" | "success" | "warning" | "danger" };

const DOT = { primary: "bg-primary", muted: "bg-muted-foreground/40", success: "bg-emerald-500", warning: "bg-amber-500", danger: "bg-rose-500" };

/** Vertical line with dots and mono timestamps, used for processing events and revisions. */
export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="relative pl-6">
      <span aria-hidden className="absolute top-2 bottom-2 left-2 w-px bg-border" />
      {items.map((it) => (
        <li key={it.key} className="relative py-3">
          <span aria-hidden className={cn("absolute top-4.5 -left-[1.125rem] size-2 rounded-full", DOT[it.dot ?? "muted"])} />
          <div className="text-sm text-foreground">{it.title}</div>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">{it.meta}</p>
          {it.body && <div className="mt-2">{it.body}</div>}
        </li>
      ))}
    </ol>
  );
}
