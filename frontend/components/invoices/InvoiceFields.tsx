import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { Field } from "@/components/Field";
import { Input } from "@/components/ui/input";
import type { FormValues } from "@/lib/invoiceForm";
import type { Invoice, InvoiceField, Issue } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELDS: { key: InvoiceField; label: string; type?: string; mono?: boolean }[] = [
  { key: "invoice_number", label: "Invoice number", mono: true },
  { key: "invoice_date", label: "Invoice date", type: "date", mono: true },
  { key: "supplier_name", label: "Supplier" },
  { key: "customer_name", label: "Customer" },
  { key: "subtotal", label: "Subtotal", mono: true },
  { key: "tax", label: "Tax", mono: true },
  { key: "total", label: "Total", mono: true },
  { key: "currency", label: "Currency", mono: true },
];
const MONEY = new Set(["subtotal", "tax", "total"]);

export function InvoiceFields({ invoice, values, onChange, issues, errors, disabled }: {
  invoice: Invoice;
  values: FormValues;
  onChange: (key: InvoiceField, value: string) => void;
  issues: Issue[];
  errors: Record<string, string>;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {FIELDS.map(({ key, label, type, mono }) => {
        const fieldIssues = issues.filter((i) => i.field === key);
        const severity = errors[key] || fieldIssues.some((i) => i.severity === "error") ? "error" : fieldIssues.length ? "warning" : null;
        const id = `inv-${key}`;
        return (
          <Field
            key={key}
            label={label}
            htmlFor={id}
            error={errors[key]}
            hint={fieldIssues.length ? <span className={severity === "error" ? "text-rose-700 dark:text-rose-400" : "text-amber-700 dark:text-amber-400"}>{fieldIssues.map((i) => i.message).join(" ")}</span> : undefined}
            extra={<ConfidenceBadge confidence={invoice.confidence[key]} empty={invoice[key] === null} />}
          >
            <Input
              id={id}
              type={type ?? "text"}
              inputMode={MONEY.has(key) ? "decimal" : undefined}
              maxLength={key === "currency" ? 3 : undefined}
              className={cn(
                mono && "font-mono tabular-nums",
                key === "currency" && "uppercase",
                severity === "error" && "border-rose-400 bg-rose-50/50 dark:border-rose-500/60 dark:bg-rose-500/10",
                severity === "warning" && "border-amber-400 bg-amber-50/50 dark:border-amber-500/60 dark:bg-amber-500/10",
              )}
              value={values[key]}
              placeholder="Not found"
              aria-invalid={severity === "error" || undefined}
              disabled={disabled}
              onChange={(e) => onChange(key, e.target.value)}
            />
          </Field>
        );
      })}
    </div>
  );
}
