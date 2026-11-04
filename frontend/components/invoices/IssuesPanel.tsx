import { AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react";
import { labelize } from "@/lib/format";
import type { Issue } from "@/lib/types";

export function IssuesPanel({ issues }: { issues: Issue[] }) {
  if (!issues.length) {
    return (
      <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-4" aria-hidden /> All validation checks passed.
      </p>
    );
  }
  const groups = [
    { label: "Errors", tone: "text-rose-700 dark:text-rose-400", Icon: AlertCircle, items: issues.filter((i) => i.severity === "error") },
    { label: "Warnings", tone: "text-amber-700 dark:text-amber-400", Icon: AlertTriangle, items: issues.filter((i) => i.severity !== "error") },
  ].filter((g) => g.items.length);
  return (
    <div className="space-y-4">
      {groups.map(({ label, tone, Icon, items }) => (
        <div key={label}>
          <h3 className={`mb-2 text-[12px] uppercase ${tone}`}>
            {label} <span className="font-mono">({items.length})</span>
          </h3>
          <ul className="space-y-2.5">
            {items.map((i, n) => (
              <li key={`${i.code}-${n}`} className="flex gap-2 text-sm">
                <Icon className={`mt-0.5 size-4 shrink-0 ${tone}`} aria-hidden />
                <div className="min-w-0">
                  <p className="break-words">{i.message}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {i.code}
                    {i.field && `, ${labelize(i.field)}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
