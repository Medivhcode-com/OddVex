import { type NextRequest, NextResponse } from "next/server";
import { API_TIMEOUT_MS, API_URL, SESSION_COOKIE } from "@/lib/config";
import { upstreamMetaHeaders } from "@/lib/request-meta";
import { safePath } from "@/lib/safe-next";

/**
 * Where a page sends a visitor whose session the API has ended: a suspended account, or a
 * token the API no longer accepts (logged out or password changed on another device).
 *
 * It asks the API again instead of trusting the link, so opening this URL cannot sign anyone
 * out of a working session: the cookie is cleared only when the API rejects the token. The
 * suspended message is shown only when the API says the account is suspended.
 *
 * `?next=` is the page the visitor was on. Only a same-site path is accepted
 * (`lib/safe-next.ts`); anything else is ignored. The visitor goes back to that page only
 * after a definite answer from the API: the token was rejected and the cookie is now cleared,
 * or the token is good. Without `?next=` they go to the login page, or to the app home with a
 * good token.
 *
 * When the API cannot be asked, or answers anything else (a timeout, a 5xx, a 429), the
 * cookie is left alone and the visitor goes to the login page, never back to `?next=`. That
 * page sent them here because its own call was answered "invalid token"; with the cookie
 * still set it would send them here again, and the two addresses would redirect to each
 * other until the browser gave up. The login page asks the API nothing, so the chain ends
 * there. For the same reason this route waits for the API as long as a page does
 * (`API_TIMEOUT_MS`).
 *
 * When a page redirects here during a move between screens inside the app, the Next.js
 * router first asks for this address with `fetch`, as page data. Following the redirect
 * inside that request would end on the page the visitor is already moving to, the server
 * would send no new content for it, and the screen would stay empty. So a `fetch` (the
 * browser marks it `Sec-Fetch-Dest: empty`; Next.js hides its own data-request headers from
 * route handlers) is answered with plain text. The router treats anything that is not page
 * data as a reason to load the address as a document, and that second request does the work.
 */
export async function GET(request: NextRequest) {
  if (request.headers.get("sec-fetch-dest") === "empty") {
    return new Response("Open this address as a page.", { headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store", vary: "sec-fetch-dest" } });
  }
  const back = safePath(request.nextUrl.searchParams.get("next"));
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  // No cookie: the page named in ?next= has no token to send, so it cannot send anyone here.
  if (!token) return go(back ?? "/login");
  let status = 0;
  let code = "";
  try {
    const response = await fetch(`${API_URL}/v1/me`, {
      headers: { accept: "application/json", authorization: `Bearer ${token}`, ...upstreamMetaHeaders(request.headers).headers },
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
    status = response.status;
    if (!response.ok) code = ((await response.json().catch(() => null)) as { error?: { code?: string } } | null)?.error?.code ?? "";
  } catch {
    // The API is unreachable: leave the session alone, and do not go back to ?next=.
    return go("/login");
  }
  if (status >= 200 && status < 300) return go(back ?? "/app");
  if (status === 401 || status === 403) return go(code === "account_suspended" ? "/login?suspended=1" : (back ?? "/login"), true);
  // No definite answer about the token: leave the session alone, and do not go back to ?next=.
  return go("/login");
}

/** A redirect to a path on this site. `clearSession` also deletes the session cookie. */
function go(location: string, clearSession = false): NextResponse {
  const response = new NextResponse(null, { status: 307, headers: { location } });
  if (clearSession) response.cookies.delete(SESSION_COOKIE);
  return response;
}
