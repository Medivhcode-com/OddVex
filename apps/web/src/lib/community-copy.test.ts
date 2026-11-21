import { describe, expect, it } from "vitest";
import { communityError, formatJoined, handleProblem, pickLimitMessage, pickStatus, profileSavedText, reasonLabel, REPORT_REASONS, RULES_REMINDER, VERIFIED_NOTE, DELETE_LOCK_NOTE } from "./community-copy";

describe("handleProblem", () => {
  it("accepts 3 to 20 characters of a-z, 0-9 and underscore", () => {
    expect(handleProblem("abc")).toBeNull();
    expect(handleProblem("a_1".padEnd(20, "x"))).toBeNull();
  });
  it("names what is wrong", () => {
    expect(handleProblem("")).toMatch(/Choose a handle/);
    expect(handleProblem("ab")).toMatch(/at least 3/);
    expect(handleProblem("x".repeat(21))).toMatch(/20 characters or fewer/);
    expect(handleProblem("Bad Handle")).toMatch(/lowercase letters, numbers and underscores/);
    expect(handleProblem("a-b")).toMatch(/lowercase/);
  });
});

describe("communityError", () => {
  const error = (status: number, code: string, message = "api message", details?: unknown) => ({ status, code, message, details });
  it("maps the profile codes", () => {
    expect(communityError(error(409, "handle_taken"))).toMatch(/already in use/);
    expect(communityError(error(422, "handle_reserved"))).toMatch(/reserved/);
    expect(communityError(error(422, "invalid_handle"))).toMatch(/3 to 20 characters/);
  });
  it("names the rule the API matched and keeps the API's sentence", () => {
    const text = communityError(error(422, "content_not_allowed", "Do not push other people to bet.", { field: "body", rule: "inducement_to_bet" }));
    expect(text).toBe("This text breaks a community rule (no pressure to bet). Do not push other people to bet.");
    expect(communityError(error(422, "content_not_allowed", "Nope.", { rule: "some_new_rule" }))).toContain("(some new rule)");
    expect(communityError(error(422, "content_not_allowed", "Nope."))).toBe("This text breaks a community rule. Nope.");
  });
  it("maps links, closed games, duplicates and the delete lock", () => {
    expect(communityError(error(422, "links_not_allowed"))).toMatch(/Links aren't allowed/);
    expect(communityError(error(422, "event_not_open"))).toMatch(/picks on it are closed/);
    expect(communityError(error(409, "pick_exists"))).toMatch(/one pick per game and market/);
    expect(communityError(error(409, "pick_locked"))).toBe(DELETE_LOCK_NOTE);
  });
  it("never promises that editing a moderated profile makes it visible again", () => {
    const text = communityError({ status: 403, code: "profile_required", message: "x", details: { reason: "profile_moderated" } });
    expect(text).toMatch(/hidden by moderators/);
    expect(text).toMatch(/goes back to a moderator for review/);
    expect(text).not.toMatch(/to make it visible again/);
  });
  it("explains why a profile cannot post", () => {
    expect(communityError(error(403, "profile_required", "x", { reason: "profile_not_public" }))).toMatch(/private/);
    expect(communityError(error(403, "profile_required", "x", { reason: "no_profile" }))).toMatch(/Create a community profile/);
    expect(communityError(error(403, "profile_required", "x"))).toMatch(/public community profile/);
  });
  it("falls back by status, then to the API message", () => {
    expect(communityError(error(401, "not_authenticated"))).toMatch(/Log in/);
    expect(communityError(error(429, "rate_limited"))).toMatch(/limit/);
    expect(communityError(error(404, "not_found"))).toMatch(/no longer available/);
    expect(communityError(error(500, "boom", "Server said no."))).toBe("Server said no.");
    expect(pickLimitMessage(error(429, "rate_limited"))).toMatch(/today's limit for picks/);
    expect(pickLimitMessage(error(422, "event_not_open"))).toBeNull();
  });
});

describe("labels", () => {
  it("gives every pick state a word", () => {
    expect(pickStatus({ status: "pending" }).label).toBe("Upcoming");
    expect(pickStatus({ status: "graded", result: "won" }).label).toBe("Won");
    expect(pickStatus({ status: "graded", result: "lost" }).label).toBe("Lost");
    expect(pickStatus({ status: "graded", result: "push" }).label).toBe("Push");
    expect(pickStatus({ status: "void" }).label).toBe("Void");
  });
  it("labels the report reasons", () => {
    expect(REPORT_REASONS.map((reason) => reason.label)).toEqual(["Spam", "Harassment", "Encouraging betting", "Misleading claims", "Personal information", "Other"]);
    expect(reasonLabel("inducement_to_bet")).toBe("Encouraging betting");
  });
  it("formats the joined month", () => {
    expect(formatJoined("2026-11")).toBe("November 2026");
    expect(formatJoined("2026-01-05T10:00:00Z")).toBe("January 2026");
    expect(formatJoined("soon")).toBe("soon");
  });
  it("keeps banned phrases out of the fixed copy", () => {
    const copy = [RULES_REMINDER, VERIFIED_NOTE, DELETE_LOCK_NOTE].join(" ").toLowerCase();
    for (const phrase of ["guaranteed", "lock of", "can't lose", "risk-free", "free money", "hot streak", "on fire", "best bets", "units"]) expect(copy).not.toContain(phrase);
  });
});

describe("profileSavedText", () => {
  const before = { handle: "sharp_sam", bio: "Totals only." };
  it("says nothing more for a visible profile", () => {
    expect(profileSavedText(before, { handle: "sharp_sam", bio: "New bio" }, "visible")).toBe("Profile saved.");
  });
  it("says a changed handle or bio of a hidden profile goes to review, and that it stays hidden", () => {
    for (const sent of [{ handle: "sharp_sam2", bio: "Totals only." }, { handle: "sharp_sam", bio: "Sides too." }, { handle: "sharp_sam", bio: null }]) {
      expect(profileSavedText(before, sent, "hidden")).toBe("Profile saved. It stays hidden, and the change goes to a moderator for review.");
    }
  });
  it("promises no review when only the public setting changed or nothing changed (the API queues none)", () => {
    for (const status of ["hidden", "removed"]) {
      expect(profileSavedText(before, { ...before }, status)).toBe("Profile saved. It stays hidden: only a moderator can make it visible again.");
    }
  });
  it("compares the handle the way the API stores it (trimmed, lower case)", () => {
    expect(profileSavedText(before, { handle: " Sharp_Sam ", bio: "Totals only." }, "hidden")).toMatch(/only a moderator can make it visible again/);
  });
});
