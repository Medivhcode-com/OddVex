import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError, SESSION_COOKIE, sessionToken } from "@/lib/api";
import { servedOverHttps } from "@/lib/config";
import type { OddsFormat } from "@/lib/format";
import type { User } from "@/lib/types";

/** The signed-in user, or null. An expired or invalid token reads as signed out. */
export async function currentUser(): Promise<User | null> {
  if (!(await sessionToken())) return null;
  try {
    return await api<User>("/v1/me", { auth: true });
  } catch (error) {
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
