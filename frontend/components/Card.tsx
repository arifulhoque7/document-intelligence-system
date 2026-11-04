import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The section container used on every page: bordered card, small semibold heading, optional caption and actions. */
export function Card({ title, caption, actions, children, className, flush = false }: { title?: ReactNode; caption?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  const header = title || caption || actions;
  return (
    <section className={cn("rounded-lg border border-border bg-card", !flush && !header && "p-4", className)}>
      {header && (
        <header className={cn("flex flex-wrap items-center justify-between gap-3", flush ? "border-b border-border px-4 py-3" : "px-4 pt-4")}>
          <div className="flex min-w-0 items-baseline gap-3">
            {title && <h2 className="text-sm font-semibold text-foreground">{title}</h2>}
            {caption && <span className="text-xs text-muted-foreground">{caption}</span>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {header && !flush ? <div className="p-4">{children}</div> : children}
    </section>
  );
}
