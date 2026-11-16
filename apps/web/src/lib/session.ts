import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError, SESSION_COOKIE, sessionToken } from "@/lib/api";
import { servedOverHttps } from "@/lib/config";
import type { OddsFormat } from "@/lib/format";
import type { User } from "@/lib/types";

/** Clears the cookie of a session the API has ended, then shows the login page. See `app/api/session/ended`. */
export const SESSION_ENDED_PATH = "/api/session/ended";

/**
 * The signed-in user, or null. An expired or invalid token reads as signed out.
 *
 * A suspended account (`401 account_suspended`) is sent to a route handler that clears the
 * session cookie and lands on the login page with a neutral explanation; a server component
 * cannot delete a cookie itself. Callers that catch errors from this function must let the
 * redirect through (`unstable_rethrow`).
 */
export async function currentUser(): Promise<User | null> {
  if (!(await sessionToken())) return null;
  try {
    return await api<User>("/v1/me", { auth: true });
  } catch (error) {
    if (error instanceof ApiError && error.code === "account_suspended") redirect(SESSION_ENDED_PATH);
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

/** Only same-site relative paths are accepted as post-login destinations. */
export function safeNext(next: string | undefined | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : "/app";
}
