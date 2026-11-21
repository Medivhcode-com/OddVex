"use server";

import { revalidatePath } from "next/cache";
import type { Schemas } from "@oddvex/types";
import { api, ApiError, ApiUnavailableError } from "@/lib/api";
import { tryAgainText } from "@/lib/retry";
import { currentUser } from "@/lib/session";

/**
 * Admin changes, and the admin export of an account's data. They run on the server only: the browser bridge (`/api/ov`) does not expose
 * `/v1/admin`. The API checks the role on every call and writes the audit entry; the check
 * here just avoids a pointless round trip. Each action refreshes the views it changed.
 */
export type AdminActionState = { ok?: string; error?: string };

const ID = /^[A-Za-z0-9_-]{1,64}$/;

/** The API's own sentences for refusing to export or delete an administrator's account or the caller's own. */
const DATA_RIGHTS_CONFLICTS = new Set(["cannot_export_self", "cannot_export_admin", "cannot_delete_self", "cannot_delete_admin"]);

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Nothing was changed.";
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return "Your session no longer has admin access. Nothing was changed.";
    if (error.code === "cannot_suspend_self") return "You can't suspend your own account.";
    if (error.code === "cannot_suspend_admin") return "An administrator can't be suspended.";
    if (DATA_RIGHTS_CONFLICTS.has(error.code)) return error.message || fallback;
    if (error.code === "confirm_email_mismatch") return "The address you typed is not this account's email address. Nothing was deleted.";
    if (error.code === "reason_contains_email") {
      return "Leave the email address out of the reason: the reason stays in the audit log after the account is gone. Use the reference of the request instead.";
    }
    if (error.status === 404) return "That item no longer exists. Nothing was changed.";
    if (error.status === 422) return "The API rejected the request. Check the fields and try again.";
    return error.message || fallback;
  }
  return fallback;
}

/** Null when the reason can be sent; the API stores it in the audit log. */
function reasonProblem(reason: string, label = "reason"): string | null {
  if (reason.length < 3) return `Enter a ${label} of at least 3 characters. It is saved in the audit log.`;
  if (reason.length > 500) return `Keep the ${label} to 500 characters or fewer.`;
  return null;
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
      const problem = reasonProblem(reason);
      if (problem) return { error: problem };
      await api<Schemas["AdminUserOut"]>(`${base}/suspend`, { method: "POST", auth: true, body: { reason } });
      result = { ok: "Account suspended. Its sessions stop working on their next request. The data is kept." };
    } else if (intent === "delete") {
      const reason = String(form.get("reason") ?? "").trim();
      const confirmEmail = String(form.get("confirm_email") ?? "").trim();
      const problem = reasonProblem(reason);
      if (problem) return { error: problem };
      if (!confirmEmail) return { error: "Type the account's email address to confirm. Nothing was deleted." };
      await api<void>(`${base}/delete`, { method: "POST", auth: true, body: { reason, confirm_email: confirmEmail } });
      result = {
        ok: "Account deleted. Its bets, watchlist, alerts, notifications, sync connections and community data were deleted with it. This cannot be undone. The audit log keeps the account's entries and your reason, without the email address.",
      };
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

export type AdminExportResult = { document?: string; filename?: string; error?: string };

/**
 * An account's data for its owner, who cannot sign in (suspended, closed, lost password). The
 * API returns the same document as the owner's own export and records the reason in the audit
 * log. The document comes back to the browser as text and is saved there as a file; nothing
 * is kept on the web server.
 */
export async function adminExportUserAction(userId: string, rawReason: string): Promise<AdminExportResult> {
  const reason = String(rawReason ?? "").trim();
  if (!ID.test(String(userId ?? ""))) return { error: "Unknown account." };
  const problem = reasonProblem(reason);
  if (problem) return { error: problem };
  if (!(await isAdmin())) return { error: NOT_ADMIN.error };
  let document: unknown;
  try {
    // A whole account can take longer to stream than a page read.
    document = await api<unknown>(`/v1/admin/users/${encodeURIComponent(userId)}/export`, { method: "POST", auth: true, body: { reason }, timeoutMs: 60_000 });
  } catch (error) {
    if (error instanceof ApiError && error.status === 429) return { error: `Another export is still running. ${tryAgainText(error.details)}` };
    return { error: describe(error, "The export failed. Nothing was changed.") };
  }
  revalidatePath("/app/admin/audit");
  return { document: JSON.stringify(document, null, 2), filename: `oddvex-export-${userId}-${new Date().toISOString().slice(0, 10)}.json` };
}

const TARGET_TYPES = new Set(["pick", "comment", "profile"]);

/** Makes hidden or removed community content visible again, and closes the open reports on it. */
export async function adminRestoreAction(_: AdminActionState, form: FormData): Promise<AdminActionState> {
  const targetType = String(form.get("target_type") ?? "");
  const targetId = String(form.get("target_id") ?? "");
  const note = String(form.get("note") ?? "").trim();
  if (!TARGET_TYPES.has(targetType) || !ID.test(targetId)) return { error: "Unknown content." };
  const problem = reasonProblem(note, "note");
  if (problem) return { error: problem };
  if (!(await isAdmin())) return NOT_ADMIN;
  let restored: Schemas["RestoredContentOut"];
  try {
    restored = await api<Schemas["RestoredContentOut"]>("/v1/admin/community/restore", { method: "POST", auth: true, body: { target_type: targetType, target_id: targetId, note } });
  } catch (error) {
    if (error instanceof ApiError && error.code === "content_not_moderated") return { error: "This content is visible already. Nothing was changed." };
    return { error: describe(error, "The content was not restored.") };
  }
  revalidatePath("/app/admin/community");
  revalidatePath("/app/admin/audit");
  revalidatePath("/app/admin");
  revalidatePath("/app/community", "layout");
  const closed = restored.reports_closed;
  return {
    ok:
      "Content restored. It is visible again to everyone who could see it before." +
      (closed > 0 ? ` ${closed} open ${closed === 1 ? "report on it was" : "reports on it were"} closed.` : ""),
  };
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
  const problem = reasonProblem(note, "note");
  if (problem) return { error: problem };
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
