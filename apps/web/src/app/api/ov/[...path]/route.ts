import { type NextRequest, NextResponse } from "next/server";
import { bridgePath } from "@/lib/bridge-path";
import { API_URL, SESSION_COOKIE } from "@/lib/config";
import { isRequestId, upstreamMetaHeaders } from "@/lib/request-meta";

/**
 * Same-origin bridge from client components to the API's /v1 routes.
 * The session token stays in an HttpOnly cookie and is attached here, on the server.
 *
 * Only the areas listed in `lib/bridge-path.ts` are forwarded; everything else is a 404 from
 * this handler and the API is not called. The decision is made on the decoded path and the
 * same string is what gets fetched, so an encoded slash, dot or backslash cannot name one
 * path to the check and another to the API. `/v1/admin` and `/v1/auth` are not on the list.
 *
 * The visitor's address and a request id are forwarded exactly as `api()` does (see
 * `lib/request-meta.ts`: the API honours the address only with `ODDVEX_TRUST_PROXY=true`).
 * The request id comes back as `X-Request-ID` so a failed call can be matched to the API log.
 *
 * When the API says the session is over, the cookie is cleared on the answer. A suspended
 * account gets the API's 401 as it is. A token the API no longer accepts (logged out or
 * password changed on another device) is dropped and the call is made once more without it:
 * a route that works signed out, such as the assistant, then answers normally, and a route
 * that needs an account answers 401 `not_authenticated`.
 */

function errorResponse(status: number, code: string, message: string, requestId?: string) {
  return NextResponse.json({ error: { code, message } }, { status, headers: requestId ? { "x-request-id": requestId } : undefined });
}

/** The `error.code` of an API error body, or "" when the body is not one. */
function errorCode(text: string): string {
  try {
    const code = (JSON.parse(text) as { error?: { code?: unknown } } | null)?.error?.code;
    return typeof code === "string" ? code : "";
  } catch {
    return "";
  }
}

/** Whether an `Origin` header names this host. An origin that is not a URL (`null`) does not. */
function sameHost(origin: string, host: string | null): boolean {
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const meta = upstreamMetaHeaders(request.headers);
  const path = bridgePath((await context.params).path);
  if (!path) return errorResponse(404, "not_found", "Unknown route.", meta.requestId);

  if (request.method !== "GET") {
    // Cookies are SameSite=Lax; this is a second check against cross-site writes.
    const origin = request.headers.get("origin");
    if (origin && !sameHost(origin, request.headers.get("host"))) {
      return errorResponse(403, "cross_origin", "Cross-origin requests are not allowed.", meta.requestId);
    }
  }

  const headers: Record<string, string> = { accept: "application/json", ...meta.headers };
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    body = await request.text();
    headers["content-type"] = "application/json";
  }

  const send = async (withToken: boolean) => {
    const upstream = await fetch(`${API_URL}${path}${request.nextUrl.search}`, {
      method: request.method,
      headers: withToken && token ? { ...headers, authorization: `Bearer ${token}` } : headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    return { upstream, text: upstream.status === 204 ? "" : await upstream.text() };
  };

  let sessionEnded = false;
  const finish = (response: NextResponse) => {
    // The next page load is then signed out, and no later call carries the dead token.
    if (sessionEnded) response.cookies.delete(SESSION_COOKIE);
    return response;
  };

  let answer: Awaited<ReturnType<typeof send>>;
  try {
    answer = await send(true);
    if (token && answer.upstream.status === 401) {
      const code = errorCode(answer.text);
      sessionEnded = code === "account_suspended" || code === "invalid_token";
      // The API refused the token before it looked at the request, so nothing ran yet.
      if (code === "invalid_token") answer = await send(false);
    }
  } catch {
    return finish(errorResponse(503, "api_unavailable", "OddVex can't reach its data service right now. Try again in a moment.", meta.requestId));
  }

  const { upstream, text } = answer;
  const upstreamId = upstream.headers.get("x-request-id");
  const requestId = isRequestId(upstreamId) ? upstreamId : meta.requestId;
  if (upstream.status === 204) return finish(new NextResponse(null, { status: 204, headers: { "x-request-id": requestId } }));
  return finish(
    new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
        "x-request-id": requestId,
      },
    }),
  );
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
