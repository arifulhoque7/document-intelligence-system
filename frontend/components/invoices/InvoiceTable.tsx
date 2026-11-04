import Link from "next/link";
import type { ReactNode } from "react";
import { DataTable, TBody, Td, Th, THead, Tr, type SortState } from "@/components/DataTable";
import { Empty } from "@/components/Empty";
import { StatusBadge } from "@/components/StatusBadge";
import { formatMoney } from "@/lib/format";
import type { Invoice } from "@/lib/types";
import { IssueCounts } from "./IssueCounts";

export type SortKey = "invoice_date" | "total" | "supplier_name" | "created_at";

export function InvoiceTable({ invoices, showDocument = true, dense = false, sort, onSort }: {
  invoices: Invoice[];
  showDocument?: boolean;
  dense?: boolean;
  /** Current API sort string, for example "-total". */
  sort?: string;
  onSort?: (key: SortKey) => void;
}) {
  const sortFor = (key: SortKey): SortState | undefined =>
    onSort && sort !== undefined ? { active: sort.replace("-", "") === key, direction: sort.startsWith("-") ? "desc" : "asc", onSort: () => onSort(key) } : undefined;
  const cell = (v: string | null, empty?: ReactNode) => v ?? empty ?? <Empty />;

  return (
    <DataTable label="Invoices">
      <THead>
        <Th edge="start">Invoice</Th>
        <Th sort={sortFor("invoice_date")}>Date</Th>
        <Th sort={sortFor("supplier_name")}>Supplier</Th>
        <Th>Customer</Th>
        <Th align="right" sort={sortFor("total")}>Total</Th>
        <Th>Status</Th>
        <Th edge={showDocument ? undefined : "end"}>Issues</Th>
        {showDocument && <Th edge="end">Source</Th>}
      </THead>
      <TBody>
        {invoices.map((inv) => (
          <Tr key={inv.id} dense={dense}>
            <Td edge="start">
              <Link href={`/invoices/${inv.id}`} className="font-mono font-medium hover:text-primary hover:underline">
                {cell(inv.invoice_number, <Empty text="No number" />)}
              </Link>
            </Td>
            <Td className="font-mono text-xs whitespace-nowrap">{cell(inv.invoice_date)}</Td>
            <Td className="max-w-48 truncate" title={inv.supplier_name ?? undefined}>{cell(inv.supplier_name)}</Td>
            <Td className="max-w-48 truncate" title={inv.customer_name ?? undefined}>{cell(inv.customer_name)}</Td>
            <Td align="right" className="font-mono whitespace-nowrap tabular-nums">{inv.total !== null ? formatMoney(inv.total, inv.currency) : <Empty />}</Td>
            <Td><StatusBadge status={inv.status} /></Td>
            <Td edge={showDocument ? undefined : "end"}><IssueCounts issues={inv.issues} /></Td>
            {showDocument && (
              <Td edge="end" className="max-w-48">
                <Link href={`/documents/${inv.document_id}`} className="block truncate text-sm hover:text-primary hover:underline" title={inv.filename ?? undefined}>
                  {inv.filename ?? "Document"}
                </Link>
                {inv.source_ref && <span className="block truncate font-mono text-xs text-muted-foreground">{inv.source_ref}</span>}
              </Td>
            )}
          </Tr>
        ))}
      </TBody>
    </DataTable>
  );
}
