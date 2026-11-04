import type { NextRequest } from "next/server";

// Runtime proxy so the browser talks to the API same-origin and the httpOnly session cookie just works.
// API_URL is read per request (not baked in at build time), so one image runs anywhere.
const FORWARD_REQUEST = ["cookie", "content-type", "content-length", "accept", "user-agent"];
// content-length is not passed back: fetch may have decoded the body, so the length can differ.
const FORWARD_RESPONSE = ["content-type", "content-disposition", "cache-control"];

export async function proxy(req: NextRequest, path: string): Promise<Response> {
  const base = process.env.API_URL ?? "http://localhost:8000";
  const target = `${base}${path}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const v = req.headers.get(name);
    if (v) headers.set(name, v);
  }

  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      redirect: "manual",
      cache: "no-store",
      // Required by Node fetch when streaming a request body (large multipart uploads).
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch {
    return Response.json({ detail: "The API is unreachable. Check that the backend is running." }, { status: 502 });
  }

  const out = new Headers();
  for (const name of FORWARD_RESPONSE) {
    const v = upstream.headers.get(name);
    if (v) out.set(name, v);
  }
  for (const c of upstream.headers.getSetCookie()) out.append("set-cookie", c);

  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}
