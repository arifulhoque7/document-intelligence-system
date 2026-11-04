/** Explicit marker for a missing value, so null never reads as 0 or blank. */
export function Empty({ text = "Not found" }: { text?: string }) {
  return <span className="text-muted-foreground italic">{text}</span>;
}
