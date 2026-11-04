// Typed fetch wrapper. All calls go same-origin through the Next.js proxy, so the
// httpOnly session cookie is sent automatically and never touched by JavaScript.

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(formatDetail(detail) || `Request failed (${status})`);
    this.name = "ApiError";
  }
}

/** FastAPI sends `detail` as a string, or as a list of validation errors for 422. */
export function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) {
          const loc = Array.isArray(d.loc) ? d.loc.filter((p: unknown) => p !== "body").join(".") : "";
          return loc ? `${loc}: ${String(d.msg)}` : String(d.msg);
        }
        return String(d);
      })
      .join("; ");
  }
  return "";
}

/** Field-level messages from a 422, keyed by top-level field name. */
export function fieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (err instanceof ApiError && Array.isArray(err.detail)) {
    for (const d of err.detail) {
      const loc: unknown[] = Array.isArray(d?.loc) ? d.loc : [];
      const field = loc.find((p) => p !== "body");
      if (typeof field === "string") out[field] = String(d.msg);
    }
  }
  return out;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

function redirectToLogin() {
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.assign(`/login?next=${next}`);
  }
}

export async function api<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const { query, headers, body, ...rest } = init;
  const isJson = body !== undefined && !(body instanceof FormData);
  const res = await fetch(withQuery(path, query), {
    ...rest,
    body,
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(isJson ? { "Content-Type": "application/json" } : {}), ...headers },
  });
  const data: unknown = res.headers.get("content-type")?.includes("application/json")
    ? await res.json().catch(() => null)
    : await res.text();
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/login")) redirectToLogin();
    const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : data;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const json = (value: unknown) => JSON.stringify(value);

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
