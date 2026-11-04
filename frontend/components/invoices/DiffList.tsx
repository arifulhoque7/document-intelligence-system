import { Empty } from "@/components/Empty";
import { labelize } from "@/lib/format";
import type { FieldDiff } from "@/lib/types";

function show(v: unknown) {
  if (v === null || v === undefined || v === "") return <Empty text="empty" />;
  if (Array.isArray(v)) return `${v.length} line item${v.length === 1 ? "" : "s"}`;
  return String(v);
}

/** Before and after values for each changed field. */
export function DiffList({ diff }: { diff: FieldDiff }) {
  return (
    <dl className="space-y-1 text-sm">
      {Object.entries(diff).map(([field, [before, after]]) => (
        <div key={field} className="flex flex-wrap items-baseline gap-x-2">
          <dt className="text-muted-foreground">{labelize(field)}</dt>
          <dd className="flex flex-wrap items-baseline gap-x-2 font-mono text-xs">
            <span className="text-muted-foreground line-through">{show(before)}</span>
            <span aria-hidden className="text-muted-foreground">to</span>
            <span className="font-medium text-foreground">{show(after)}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}
