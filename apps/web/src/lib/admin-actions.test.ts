import { beforeEach, describe, expect, it, vi } from "vitest";

// `lib/api.ts` is server code; the marker package only exists to keep it out of the browser bundle.
vi.mock("server-only", () => ({}));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/session", () => ({ currentUser: vi.fn(async () => ({ id: "admin1", role: "admin" })) }));
const api = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: (...args: unknown[]) => api(...args) };
});

const { ApiError } = await import("@/lib/api");
const { adminExportUserAction, adminRestoreAction, adminUserAction } = await import("@/lib/admin-actions");

const form = (fields: Record<string, string>) => {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
};

beforeEach(() => api.mockReset());

describe("exporting an account's data for its owner", () => {
  it("posts the reason and hands back the API's JSON document to download", async () => {
    api.mockResolvedValueOnce({ format_version: 1, user: { id: "user1" }, bets: [] });
    const result = await adminExportUserAction("user1", "Request REF-1042 from the owner");
    expect(api).toHaveBeenCalledWith("/v1/admin/users/user1/export", expect.objectContaining({ method: "POST", auth: true, body: { reason: "Request REF-1042 from the owner" } }));
    expect(result.error).toBeUndefined();
    expect(JSON.parse(result.document!)).toEqual({ format_version: 1, user: { id: "user1" }, bets: [] });
    expect(result.filename).toMatch(/^oddvex-export-user1-\d{4}-\d{2}-\d{2}\.json$/);
  });

  it("needs a reason of 3 to 500 characters and sends nothing without one", async () => {
    expect((await adminExportUserAction("user1", " ab ")).error).toMatch(/at least 3 characters/);
    expect((await adminExportUserAction("user1", "x".repeat(501))).error).toMatch(/500 characters/);
    expect(api).not.toHaveBeenCalled();
  });

  it("shows the API's 409 for an administrator's or the caller's own account", async () => {
    api.mockRejectedValueOnce(new ApiError(409, "cannot_export_admin", "An administrator's account cannot be exported by another administrator"));
    expect((await adminExportUserAction("user2", "Request REF-1")).error).toBe("An administrator's account cannot be exported by another administrator");
    api.mockRejectedValueOnce(new ApiError(409, "cannot_export_self", "You cannot export your own account here. Use your account settings."));
    expect((await adminExportUserAction("admin1", "Request REF-1")).error).toBe("You cannot export your own account here. Use your account settings.");
  });

  it("explains a reason that names the account, and a 429 with its wait", async () => {
    api.mockRejectedValueOnce(new ApiError(422, "reason_contains_email", "The reason must not contain the account's email address"));
    expect((await adminExportUserAction("user1", "for someone@example.test")).error).toMatch(/Leave the email address out of the reason/);
    api.mockRejectedValueOnce(new ApiError(429, "rate_limited", "Too many requests. Try again in 30 seconds.", { retry_after_seconds: 30 }));
    expect((await adminExportUserAction("user1", "Request REF-1")).error).toBe("Another export is still running. Try again in 30 seconds.");
  });

  it("refuses an id that is not one", async () => {
    expect((await adminExportUserAction("../me", "Request REF-1")).error).toBe("Unknown account.");
    expect(api).not.toHaveBeenCalled();
  });
});

describe("deleting an account for its owner", () => {
  const remove = (fields: Record<string, string>) => adminUserAction({}, form({ user_id: "user1", intent: "delete", ...fields }));

  it("posts the reason and the typed email address", async () => {
    api.mockResolvedValueOnce(undefined);
    const result = await remove({ reason: "Request REF-1042 from the owner", confirm_email: " Owner@Example.test " });
    expect(api).toHaveBeenCalledWith("/v1/admin/users/user1/delete", expect.objectContaining({ method: "POST", auth: true, body: { reason: "Request REF-1042 from the owner", confirm_email: "Owner@Example.test" } }));
    expect(result.ok).toMatch(/^Account deleted\./);
    expect(result.ok).toMatch(/cannot be undone/);
  });

  it("needs a reason and the typed email address before anything is sent", async () => {
    expect((await remove({ reason: "ab", confirm_email: "owner@example.test" })).error).toMatch(/at least 3 characters/);
    expect((await remove({ reason: "Request REF-1", confirm_email: " " })).error).toMatch(/Type the account's email address/);
    expect(api).not.toHaveBeenCalled();
  });

  it("shows the API's 409 errors and explains a mismatched address", async () => {
    api.mockRejectedValueOnce(new ApiError(409, "cannot_delete_admin", "An administrator's account cannot be deleted by another administrator"));
    expect((await remove({ reason: "Request REF-1", confirm_email: "a@b.test" })).error).toBe("An administrator's account cannot be deleted by another administrator");
    api.mockRejectedValueOnce(new ApiError(409, "cannot_delete_self", "You cannot delete your own account here. Use your account settings."));
    expect((await remove({ reason: "Request REF-1", confirm_email: "a@b.test" })).error).toBe("You cannot delete your own account here. Use your account settings.");
    api.mockRejectedValueOnce(new ApiError(422, "confirm_email_mismatch", "confirm_email is not this account's email address. Nothing was deleted."));
    expect((await remove({ reason: "Request REF-1", confirm_email: "a@b.test" })).error).toBe("The address you typed is not this account's email address. Nothing was deleted.");
  });
});

describe("restoring moderated content", () => {
  const restore = (fields: Record<string, string>) => adminRestoreAction({}, form({ target_type: "pick", target_id: "pick1", note: "Reviewed again, within the rules", ...fields }));

  it("posts the target and the note, and says how many reports it closed", async () => {
    api.mockResolvedValueOnce({ target_type: "pick", target_id: "pick1", moderation_status: "visible", reports_closed: 2 });
    const result = await restore({});
    expect(api).toHaveBeenCalledWith("/v1/admin/community/restore", expect.objectContaining({ method: "POST", auth: true, body: { target_type: "pick", target_id: "pick1", note: "Reviewed again, within the rules" } }));
    expect(result.ok).toBe("Content restored. It is visible again to everyone who could see it before. 2 open reports on it were closed.");
  });

  it("needs a note and a known target type", async () => {
    expect((await restore({ note: "ab" })).error).toMatch(/at least 3 characters/);
    expect((await restore({ target_type: "user" })).error).toBe("Unknown content.");
    expect(api).not.toHaveBeenCalled();
  });

  it("says when the content is visible already", async () => {
    api.mockRejectedValueOnce(new ApiError(409, "content_not_moderated", "This content was not hidden or removed by moderators"));
    expect((await restore({})).error).toBe("This content is visible already. Nothing was changed.");
  });
});
