import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { type NextRequest } from "next/server";
import { API_URL, SESSION_COOKIE } from "@/lib/config";
import { upstreamMetaHeaders } from "@/lib/request-meta";

/**
 * Where a page sends a visitor whose session the API has ended (a suspended account).
 *
 * It asks the API again instead of trusting the link, so opening this URL cannot sign anyone
 * out of a working session: the cookie is cleared only when the API rejects the token. The
 * suspended message is shown only when the API says the account is suspended.
 */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) redirect("/login");
  let status = 0;
  let code = "";
  try {
    const response = await fetch(`${API_URL}/v1/me`, {
      headers: { accept: "application/json", authorization: `Bearer ${token}`, ...upstreamMetaHeaders(request.headers).headers },
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    status = response.status;
    if (!response.ok) code = ((await response.json().catch(() => null)) as { error?: { code?: string } } | null)?.error?.code ?? "";
  } catch {
    // The API is unreachable: leave the session alone.
    redirect("/login");
  }
  if (status >= 200 && status < 300) redirect("/app");
  if (status === 401 || status === 403) {
    (await cookies()).delete(SESSION_COOKIE);
    redirect(code === "account_suspended" ? "/login?suspended=1" : "/login");
  }
  redirect("/login");
}
