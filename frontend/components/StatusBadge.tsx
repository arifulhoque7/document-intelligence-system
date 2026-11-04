import { labelize } from "@/lib/format";
import { Badge, type Tone } from "./Badge";

const TONE: Record<string, Tone> = {
  queued: "neutral",
  processing: "amber",
  completed: "emerald",
  needs_review: "indigo",
  failed: "rose",
  extracted: "sky",
  approved: "emerald",
  started: "amber",
  ok: "emerald",
  warning: "amber",
  match: "emerald",
  mismatch: "rose",
};

/** Document, invoice, event and cross-check statuses share one colour language. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={TONE[status] ?? "neutral"}>
      {status === "processing" && <span className="size-1.5 animate-pulse rounded-full bg-current" aria-hidden />}
      {labelize(status)}
    </Badge>
  );
}
