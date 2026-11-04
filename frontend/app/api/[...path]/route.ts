import type { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

export const dynamic = "force-dynamic";

function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return ctx.params.then(({ path }) => proxy(req, `/api/${path.map(encodeURIComponent).join("/")}`));
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
