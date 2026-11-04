/**
 * Renders a search snippet where the API marks matches as <<term>>.
 * Builds React text nodes only, so API text can never be interpreted as HTML.
 */
export function Highlight({ text }: { text: string }) {
  const parts = text.split(/(<<.*?>>)/g);
  return (
    <>
      {parts.map((p, i) => (p.startsWith("<<") && p.endsWith(">>") ? <mark key={i}>{p.slice(2, -2)}</mark> : <span key={i}>{p}</span>))}
    </>
  );
}
