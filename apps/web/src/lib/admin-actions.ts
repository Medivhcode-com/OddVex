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

const REPORT_ACTIONS: Record<string, string> = {
  dismiss: "Report dismissed. The content was left as it is.",
  hide_content: "Content hidden. It no longer appears in any public view, and every open report on it was closed.",
  remove_content: "Content removed. It no longer appears in any public view, and every open report on it was closed.",
  suspend_author: "Author suspended. Their sessions stop working on their next request.",
};

/** Decides one community report. The note is required and is saved in the audit log. */
export async function adminReportAction(_: AdminActionState, form: FormData): Promise<AdminActionState> {
  const reportId = String(form.get("report_id") ?? "");
  const action = String(form.get("action") ?? "");
  const note = String(form.get("note") ?? "").trim();
  if (!ID.test(reportId)) return { error: "Unknown report." };
  if (!(action in REPORT_ACTIONS)) return { error: "Unknown action." };
  if (note.length < 3) return { error: "Enter a note of at least 3 characters. It is saved in the audit log." };
  if (note.length > 500) return { error: "Keep the note to 500 characters or fewer." };
  if (!(await isAdmin())) return NOT_ADMIN;
  try {
    await api<Schemas["AdminReportOut"]>(`/v1/admin/community/reports/${encodeURIComponent(reportId)}/resolve`, { method: "POST", auth: true, body: { action, note } });
  } catch (error) {
    if (error instanceof ApiError && error.code === "report_already_resolved") return { error: "This report was already resolved. Nothing was changed." };
    return { error: describe(error, "The report was not resolved.") };
  }
  revalidatePath("/app/admin/community");
  revalidatePath("/app/admin/audit");
  revalidatePath("/app/admin");
  revalidatePath("/app/community", "layout");
  return { ok: REPORT_ACTIONS[action] };
}

/**
 * A moderator deleting someone else's comment. The API route is the member one
 * (`DELETE /v1/community/comments/{id}`, which accepts the author or an administrator), but
 * the moderator's call is made here, on the server, like every other admin change.
 */
export async function adminDeleteCommentAction(_: AdminActionState, form: FormData): Promise<AdminActionState> {
  const commentId = String(form.get("comment_id") ?? "");
  const pickId = String(form.get("pick_id") ?? "");
  if (!ID.test(commentId)) return { error: "Unknown comment." };
  if (!(await isAdmin())) return NOT_ADMIN;
  try {
    await api<void>(`/v1/community/comments/${encodeURIComponent(commentId)}`, { method: "DELETE", auth: true });
  } catch (error) {
    return { error: describe(error, "The comment was not deleted.") };
  }
  if (ID.test(pickId)) revalidatePath(`/app/community/picks/${pickId}`);
  revalidatePath("/app/admin/audit");
  return { ok: "Comment deleted." };
}
