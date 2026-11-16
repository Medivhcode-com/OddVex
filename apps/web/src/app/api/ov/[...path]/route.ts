import { type NextRequest, NextResponse } from "next/server";
import { API_URL, SESSION_COOKIE } from "@/lib/api";

/**
 * Same-origin bridge from client components to the API's /v1 routes.
 * The session token stays in an HttpOnly cookie and is attached here, on the server.
 */
const ALLOWED = /^v1\/(quant|bets|sync|assistant|events|players|props|me|watchlist|alerts|notifications)(\/|$)/;

function errorResponse(status: number, code: string, message: string) {
  return NextResponse.json({ error: { code, message } }, { status });
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!ALLOWED.test(path)) return errorResponse(404, "not_found", "Unknown route.");

  if (request.method !== "GET") {
    // Cookies are SameSite=Lax; this is a second check against cross-site writes.
    const origin = request.headers.get("origin");
    if (origin && new URL(origin).host !== request.headers.get("host")) {
      return errorResponse(403, "cross_origin", "Cross-origin requests are not allowed.");
    }
  }

  const headers: Record<string, string> = { accept: "application/json" };
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token) headers.authorization = `Bearer ${token}`;
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers["x-forwarded-for"] = forwardedFor;

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    body = await request.text();
    headers["content-type"] = "application/json";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/${path}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
  } catch {
    return errorResponse(503, "api_unavailable", "OddVex can't reach its data service right now. Try again in a moment.");
  }

  if (upstream.status === 204) return new NextResponse(null, { status: 204 });
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json", "cache-control": "no-store" },
  });
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
