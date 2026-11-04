import { Badge, type Tone } from "./Badge";

/** emerald >= 0.8, amber >= 0.6, rose below; neutral when there is no value to be confident about. */
export function confidenceTone(confidence: number | undefined, empty: boolean): Tone {
  if (empty || confidence === undefined) return "neutral";
  if (confidence >= 0.8) return "emerald";
  if (confidence >= 0.6) return "amber";
  return "rose";
}

export function ConfidenceBadge({ confidence, empty = false }: { confidence: number | undefined; empty?: boolean }) {
  const text = empty ? "Not found" : confidence === undefined ? "n/a" : `${Math.round(confidence * 100)}%`;
  return (
    <Badge tone={confidenceTone(confidence, empty)} title={empty ? "No value was extracted" : "Extraction confidence"} className="font-mono">
      {text}
    </Badge>
  );
}
