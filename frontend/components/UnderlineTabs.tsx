import { cn } from "@/lib/utils";

export type TabItem = { value: string | null; label: string; count?: number };

/** Underline tabs for filter rows, so they read as navigation rather than competing with the search field. */
export function UnderlineTabs({ items, active, label, onSelect }: { items: TabItem[]; active: string | null; label: string; onSelect: (value: string | null) => void }) {
  return (
    <div role="tablist" aria-label={label} className="-mb-2 flex max-w-full min-w-0 flex-1 items-stretch overflow-x-auto pb-2 [scrollbar-width:none]">
      {items.map((item) => {
        const selected = item.value === active;
        return (
          <button
            key={item.value ?? "all"}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onSelect(item.value)}
            className={cn(
              "relative inline-flex h-11 shrink-0 cursor-pointer items-center gap-1.5 px-4 text-sm font-medium whitespace-nowrap transition-colors outline-none focus-visible:text-primary",
              selected ? "text-primary" : "text-foreground hover:text-primary",
            )}
          >
            <span>{item.label}</span>
            {item.count !== undefined && <span className="font-mono font-normal text-muted-foreground">({item.count})</span>}
            <span aria-hidden className={cn("absolute inset-x-0 -bottom-2 h-0.5", selected ? "bg-primary" : "bg-transparent")} />
          </button>
        );
      })}
    </div>
  );
}
