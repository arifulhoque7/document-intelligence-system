import type { ReactNode } from "react";
import { Label } from "./ui/label";
import { SelectContent, SelectItem, SelectTrigger, SelectValue, Select as SelectRoot } from "./ui/select";

export function Field({ label, htmlFor, hint, error, children, extra }: { label: ReactNode; htmlFor: string; hint?: ReactNode; error?: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={htmlFor}>{label}</Label>
        {extra}
      </div>
      {children}
      {error ? <p className="text-xs text-destructive-foreground">{error}</p> : hint ? <div className="text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

// Radix Select cannot hold an empty value, so "" (meaning "any") is mapped to a sentinel.
const ANY = "__any";

/** shadcn Select with a plain value/onChange API; "" is a valid "all" option. */
export function SimpleSelect({ id, value, onChange, options, placeholder, disabled, className }: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string; disabled?: boolean }[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    // An empty value with no "any" option shows the placeholder.
    <SelectRoot value={value === "" && options.some((o) => o.value === "") ? ANY : value} onValueChange={(v) => onChange(v === ANY ? "" : v)} disabled={disabled}>
      <SelectTrigger id={id} className={className ?? "w-full"}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value || ANY} value={o.value === "" ? ANY : o.value} disabled={o.disabled}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </SelectRoot>
  );
}
