import "server-only";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError, SESSION_COOKIE, sessionToken } from "@/lib/api";
import { PAGE_PATH_HEADER, servedOverHttps } from "@/lib/config";
import type { OddsFormat } from "@/lib/format";
import { withNext } from "@/lib/safe-next";
import type { User } from "@/lib/types";

/**
 * Clears the cookie of a session the API has ended. Without `?next=` it then shows the login
 * page; with it, the page the visitor was on. See `app/api/session/ended`.
 */
export const SESSION_ENDED_PATH = "/api/session/ended";

/**
 * The signed-in user, or null. An expired or invalid token reads as signed out.
 *
 * A server component cannot delete a cookie itself, so when the API has ended the session the
 * visitor is sent through a route handler that clears it. Callers that catch errors from
 * this function must let the redirect through (`unstable_rethrow`).
 *
 * - A suspended account (`401 account_suspended`) lands on the login page with a neutral
 *   explanation.
 * - A token the API no longer accepts (`401 invalid_token`: logged out or password changed on
 *   another device) comes straight back to the page it asked for, now signed out, so a
 *   public page keeps working and no later call carries the dead token. In a server action
 *   `api()` has already dropped the cookie and nobody is redirected. If the page's path is
 *   not known (a prefetch) or too long to carry in an address, the answer is simply "signed
 *   out" and the next ordinary request clears the cookie.
 *
 * The route handler sends the visitor back here only once the cookie is cleared or the API
 * has accepted the token. If it cannot get an answer it shows the login page instead, so a
 * slow or failing API cannot make the page and the route redirect to each other in a circle.
 */
export async function currentUser(): Promise<User | null> {
  if (!(await sessionToken())) return null;
  try {
    return await api<User>("/v1/me", { auth: true });
  } catch (error) {
    if (error instanceof ApiError && error.code === "account_suspended") redirect(SESSION_ENDED_PATH);
    if (error instanceof ApiError && error.status === 401 && error.code === "invalid_token" && (await sessionToken())) {
      const ended = withNext(SESSION_ENDED_PATH, (await headers()).get(PAGE_PATH_HEADER));
      if (ended) redirect(ended);
    }
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

export async function requireUser(next: string): Promise<User> {
  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`);
  return user;
}

export async function setSession(token: string, maxAgeSeconds: number) {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: servedOverHttps(),
    path: "/",
    maxAge: maxAgeSeconds,
  });
}

export async function clearSession() {
  (await cookies()).delete(SESSION_COOKIE);
}

export async function oddsFormat(): Promise<OddsFormat> {
  return (await cookies()).get("ov_odds")?.value === "decimal" ? "decimal" : "american";
}
