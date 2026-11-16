import "server-only";
import { notFound } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { currentUser } from "@/lib/session";
import type { User } from "@/lib/types";

/**
 * Every admin page calls this first. Anyone who is not an administrator gets the standard
 * not-found page, so the section's existence is not advertised. The proxy already answered
 * such requests with a real 404; this is the second check, and the API is the third.
 */
export async function requireAdmin(): Promise<User> {
  const user = await currentUser();
  if (!user || user.role !== "admin") notFound();
  return user;
}

/** An admin read. A role the API no longer accepts reads as not found, like everywhere else in the section. */
export async function adminGet<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T> {
  try {
    return await api<T>(path, { auth: true, query });
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) notFound();
    throw error;
  }
}

/** Flags that must not be switched on without a review, and what to say before someone does. */
export function flagWarning(key: string): string | null {
  if (key === "community" || key.startsWith("community_")) {
    return "The roadmap requires a legal review and a responsible-gambling review before any community feature is switched on. Do not turn this on until both are complete and the Founder has approved it.";
  }
  if (key === "premium_gating") {
    return "Enforcing plans is a pricing decision. It needs Founder approval before it is switched on.";
  }
  return null;
}
