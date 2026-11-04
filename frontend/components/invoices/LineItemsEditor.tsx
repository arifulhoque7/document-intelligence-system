import { Plus, Trash2 } from "lucide-react";
import { DataTable, TBody, Td, Th, THead, Tr } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { emptyRow, type LineRow } from "@/lib/invoiceForm";
import { cn } from "@/lib/utils";

const COLS: { key: keyof LineRow; label: string; numeric?: boolean }[] = [
  { key: "description", label: "Description" },
  { key: "quantity", label: "Qty", numeric: true },
  { key: "unit_price", label: "Unit price", numeric: true },
  { key: "amount", label: "Amount", numeric: true },
];

export function LineItemsEditor({ rows, onChange, disabled, highlight }: { rows: LineRow[]; onChange: (rows: LineRow[]) => void; disabled?: boolean; highlight?: boolean }) {
  const set = (i: number, key: keyof LineRow, value: string) => onChange(rows.map((r, n) => (n === i ? { ...r, [key]: value } : r)));

  return (
    <div className={cn(highlight && "ring-2 ring-amber-400/60 ring-inset")}>
      {rows.length ? (
        <DataTable label="Line items">
          <THead>
            {COLS.map((c, i) => (
              <Th key={c.key} edge={i === 0 ? "start" : undefined} align={c.numeric ? "right" : undefined} className={c.numeric ? "w-32" : ""}>{c.label}</Th>
            ))}
            <Th edge="end" className="w-12"><span className="sr-only">Remove</span></Th>
          </THead>
          <TBody>
            {rows.map((r, i) => (
              <Tr key={i} dense>
                {COLS.map((c, n) => (
                  <Td key={c.key} edge={n === 0 ? "start" : undefined}>
                    <Input
                      aria-label={`${c.label}, line ${i + 1}`}
                      className={cn("h-9", c.numeric && "text-right font-mono tabular-nums")}
                      inputMode={c.numeric ? "decimal" : undefined}
                      value={r[c.key]}
                      placeholder={c.numeric ? "empty" : "No description"}
                      disabled={disabled}
                      onChange={(e) => set(i, c.key, e.target.value)}
                    />
                  </Td>
                ))}
                <Td edge="end">
                  <Button variant="ghost" size="icon" disabled={disabled} onClick={() => onChange(rows.filter((_, n) => n !== i))} aria-label={`Remove line ${i + 1}`}>
                    <Trash2 aria-hidden />
                  </Button>
                </Td>
              </Tr>
            ))}
          </TBody>
        </DataTable>
      ) : (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">No line items found.</p>
      )}
      <div className="border-t border-border px-4 py-2">
        <Button variant="ghost" size="compact" disabled={disabled} onClick={() => onChange([...rows, emptyRow()])}>
          <Plus aria-hidden /> Add line
        </Button>
      </div>
    </div>
  );
}
