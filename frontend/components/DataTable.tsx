import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * Table metrics shared by every list: 40px header row, 72px body rows (56px dense),
 * 12px uppercase muted headers, edge cells at px-4 and the middle at px-2.
 */
export function DataTable({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div className="overflow-x-auto bg-card">
      <table className={cn("w-full text-left", className)} aria-label={label}>
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-border bg-card">
      <tr className="h-10">{children}</tr>
    </thead>
  );
}

export type SortState = { active: boolean; direction: "asc" | "desc"; onSort: () => void };

export function Th({ children, align, edge, sort, className, ...props }: ThHTMLAttributes<HTMLTableCellElement> & { align?: "right"; edge?: "start" | "end"; sort?: SortState }) {
  const ariaSort = sort ? (sort.active ? (sort.direction === "asc" ? "ascending" : "descending") : "none") : undefined;
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={cn(
        "px-2 text-[12px] leading-[1.4] font-normal whitespace-nowrap text-muted-foreground uppercase",
        edge === "start" && "px-4",
        edge === "end" && "pr-4",
        align === "right" && "text-right",
        className,
      )}
      {...props}
    >
      {sort ? (
        <button type="button" onClick={sort.onSort} className="inline-flex cursor-pointer items-center gap-1 uppercase hover:text-foreground focus-visible:text-foreground focus-visible:outline-none">
          {children}
          {!sort.active ? <ArrowUpDown size={12} aria-hidden /> : sort.direction === "asc" ? <ArrowUp size={12} aria-hidden /> : <ArrowDown size={12} aria-hidden />}
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function Tr({ children, className, dense }: { children: ReactNode; className?: string; dense?: boolean }) {
  return <tr className={cn("group border-b border-border bg-card last:border-b-0 hover:bg-muted/40", dense ? "h-14" : "h-18", className)}>{children}</tr>;
}

export function Td({ children, align, edge, className, ...props }: TdHTMLAttributes<HTMLTableCellElement> & { align?: "right"; edge?: "start" | "end" }) {
  return (
    <td className={cn("px-2 align-middle text-sm text-foreground", edge === "start" && "px-4", edge === "end" && "pr-4 pl-2", align === "right" && "text-right", className)} {...props}>
      {children}
    </td>
  );
}
