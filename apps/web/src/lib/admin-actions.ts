"use server";

import { revalidatePath } from "next/cache";
import type { Schemas } from "@oddvex/types";
import { api, ApiError, ApiUnavailableError } from "@/lib/api";
import { currentUser } from "@/lib/session";

/**
 * Admin changes. They run on the server only: the browser bridge (`/api/ov`) does not expose
 * `/v1/admin`. The API checks the role on every call and writes the audit entry; the check
 * here just avoids a pointless round trip. Each action refreshes the views it changed.
 */
export type AdminActionState = { ok?: string; error?: string };

const ID = /^[A-Za-z0-9_-]{1,64}$/;

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Nothing was changed.";
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return "Your session no longer has admin access. Nothing was changed.";
    if (error.code === "cannot_suspend_self") return "You can't suspend your own account.";
    if (error.code === "cannot_suspend_admin") return "An administrator can't be suspended.";
    if (error.status === 404) return "That item no longer exists. Nothing was changed.";
    if (error.status === 422) return "The API rejected the request. Check the fields and try again.";
    return error.message || fallback;
  }
  return fallback;
}

async function isAdmin(): Promise<boolean> {
  return (await currentUser())?.role === "admin";
}

const NOT_ADMIN: AdminActionState = { error: "Your session no longer has admin access. Nothing was changed." };

export async function adminUserAction(_: AdminActionState, form: FormData): Promise<AdminActionState> {
  const userId = String(form.get("user_id") ?? "");
  const intent = String(form.get("intent") ?? "");
  if (!ID.test(userId)) return { error: "Unknown account." };
  if (!(await isAdmin())) return NOT_ADMIN;
  const base = `/v1/admin/users/${encodeURIComponent(userId)}`;
  let result: AdminActionState;
  try {
    if (intent === "suspend") {
      const reason = String(form.get("reason") ?? "").trim();
      if (reason.length < 3) return { error: "Enter a reason of at least 3 characters. It is saved in the audit log." };
      if (reason.length > 500) return { error: "Keep the reason to 500 characters or fewer." };
      await api<Schemas["AdminUserOut"]>(`${base}/suspend`, { method: "POST", auth: true, body: { reason } });
      result = { ok: "Account suspended. Its sessions stop working on their next request. The data is kept." };
    } else if (intent === "unsuspend") {
      await api<Schemas["AdminUserOut"]>(`${base}/unsuspend`, { method: "POST", auth: true });
      result = { ok: "Account unsuspended. The person can log in again." };
    } else if (intent === "plan") {
      const plan = String(form.get("plan") ?? "");
      if (plan !== "free" && plan !== "premium") return { error: "Choose free or premium." };
      await api<Schemas["AdminUserOut"]>(`${base}/plan`, { method: "PUT", auth: true, body: { plan } });
      result = { ok: `Plan set to ${plan}. Nothing was charged: OddVex has no billing.` };
    } else {
      return { error: "Unknown action." };
    }
  } catch (error) {
    return { error: describe(error, "The change was not saved.") };
  }
  revalidatePath("/app/admin/users");
  revalidatePath("/app/admin/audit");
  revalidatePath("/app/admin");
  return result;
}

export async function adminFlagAction(_: AdminActionState, form: FormData): Promise<AdminActionState> {
  const key = String(form.get("key") ?? "");
  const enabled = String(form.get("enabled") ?? "");
  if (!ID.test(key) || (enabled !== "true" && enabled !== "false")) return { error: "Unknown flag." };
  if (!(await isAdmin())) return NOT_ADMIN;
  try {
    await api<Schemas["AdminFlagOut"]>(`/v1/admin/flags/${encodeURIComponent(key)}`, { method: "PUT", auth: true, body: { enabled: enabled === "true" } });
  } catch (error) {
    return { error: describe(error, "The flag was not changed.") };
  }
  // Flags decide which navigation entries and pages exist, so the whole app shell is refreshed.
  revalidatePath("/app", "layout");
  return { ok: `Flag turned ${enabled === "true" ? "on" : "off"}. It applies to everyone from their next page load.` };
}
