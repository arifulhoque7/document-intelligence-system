import { Badge } from "@/components/Badge";
import type { Issue } from "@/lib/types";

export function IssueCounts({ issues }: { issues: Issue[] }) {
  const errors = issues.filter((i) => i.severity === "error").length;
  const warnings = issues.length - errors;
  if (!issues.length) return <span className="text-xs text-muted-foreground">None</span>;
  return (
    <span className="inline-flex gap-1">
      {errors > 0 && <Badge tone="rose"><span className="font-mono">{errors}</span> error{errors > 1 ? "s" : ""}</Badge>}
      {warnings > 0 && <Badge tone="amber"><span className="font-mono">{warnings}</span> warning{warnings > 1 ? "s" : ""}</Badge>}
    </span>
  );
}
