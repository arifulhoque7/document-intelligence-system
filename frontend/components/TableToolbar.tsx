import { Search } from "lucide-react";
import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { UnderlineTabs, type TabItem } from "./UnderlineTabs";

/** The filter row on top of every table card: tabs on the left, search and extra controls on the right. */
export function TableToolbar({ tabs, activeTab, tabsLabel = "Filter", onSelectTab, search, onSearch, onSubmit, searchLabel, searchPlaceholder = "Search", children }: {
  tabs?: TabItem[];
  activeTab?: string | null;
  tabsLabel?: string;
  onSelectTab?: (value: string | null) => void;
  search: string;
  onSearch: (value: string) => void;
  onSubmit?: () => void;
  searchLabel: string;
  searchPlaceholder?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 pt-3 pb-2">
      {tabs && onSelectTab ? <UnderlineTabs items={tabs} active={activeTab ?? null} label={tabsLabel} onSelect={onSelectTab} /> : <span className="h-11" />}
      <form
        role="search"
        className="flex flex-wrap items-center gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit?.();
        }}
      >
        <div className="relative">
          <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground" />
          <Input type="search" aria-label={searchLabel} value={search} onChange={(e) => onSearch(e.target.value)} placeholder={searchPlaceholder} className="h-9 w-60 rounded-md pl-9 text-sm" />
        </div>
        {children}
      </form>
    </div>
  );
}

export function TableFooter({ children }: { children: ReactNode }) {
  return <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-sm text-muted-foreground">{children}</footer>;
}
