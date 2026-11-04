import { INVOICE_FIELDS, type Invoice, type InvoiceField, type LineItem } from "./types.ts";

// Form state keeps every value as a string; "" means "no value" and is sent as null.
export type FormValues = Record<InvoiceField, string>;
export type LineRow = Record<keyof LineItem, string>;

export const MONEY_FIELDS: InvoiceField[] = ["subtotal", "tax", "total"];
const LINE_KEYS: (keyof LineItem)[] = ["description", "quantity", "unit_price", "amount"];

export function toForm(inv: Invoice): FormValues {
  return Object.fromEntries(INVOICE_FIELDS.map((f) => [f, inv[f] ?? ""])) as FormValues;
}

export function toRows(items: LineItem[]): LineRow[] {
  return items.map((li) => Object.fromEntries(LINE_KEYS.map((k) => [k, li[k] ?? ""])) as LineRow);
}

export const emptyRow = (): LineRow => ({ description: "", quantity: "", unit_price: "", amount: "" });

const NUMERIC = new Set(["subtotal", "tax", "total", "quantity", "unit_price", "amount"]);

/** Two values are equal if they are the same text, or the same number ("365.2" vs "365.20"). */
function same(key: string, a: string, b: string): boolean {
  const x = a.trim();
  const y = b.trim();
  if (x === y) return true;
  if (NUMERIC.has(key) && x !== "" && y !== "") return Number(x) === Number(y);
  return false;
}

const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

/** Build a PATCH body holding only the fields the reviewer changed. */
export function buildPatch(original: Invoice, values: FormValues, rows: LineRow[]): Record<string, unknown> {
  const before = toForm(original);
  const patch: Record<string, unknown> = {};
  for (const f of INVOICE_FIELDS) {
    if (!same(f, before[f], values[f])) patch[f] = f === "currency" ? orNull(values[f])?.toUpperCase() ?? null : orNull(values[f]);
  }
  const oldRows = toRows(original.line_items);
  const changed = oldRows.length !== rows.length || rows.some((r, i) => LINE_KEYS.some((k) => !same(k, oldRows[i][k], r[k])));
  if (changed) {
    patch.line_items = rows
      .filter((r) => LINE_KEYS.some((k) => r[k].trim() !== ""))
      .map((r) => Object.fromEntries(LINE_KEYS.map((k) => [k, orNull(r[k])])));
  }
  return patch;
}
