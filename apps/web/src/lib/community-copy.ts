/**
 * Words for the community screens: API error codes as sentences, statuses and report reasons.
 * Pure, so it is unit-tested and shared by server and client components. The community rules
 * themselves are never written here: they come from `GET /v1/community/guidelines`.
 */
import type { Schemas } from "@oddvex/types";

export type Pick = Schemas["PickOut"];
export type Comment = Schemas["CommentOut"];
export type MyProfile = Schemas["MyProfileOut"];
export type Profile = Schemas["ProfileOut"];
export type CommunityRecord = Schemas["CommunityRecordOut"];
export type ReportReason = Schemas["ReportCreate"]["reason"];
export type ReportTarget = Schemas["ReportCreate"]["target_type"];

export const HANDLE_MIN = 3;
export const HANDLE_MAX = 20;
export const BIO_MAX = 280;
export const ANALYSIS_MAX = 1000;
export const COMMENT_MAX = 500;
export const REPORT_DETAILS_MAX = 500;

/** Shown next to every text box. The full rules are the API's guidelines. */
export const RULES_REMINDER = "Plain text only. No guarantees, no links and no selling picks.";

export const DELETE_LOCK_NOTE = "Picks can't be deleted after the game starts, so records stay honest.";

export const VERIFIED_NOTE = "Verified: every pick is timestamped before the game and graded automatically from the final score.";

/** The handle rule the API enforces, checked while typing. Null when the handle is acceptable. */
export function handleProblem(handle: string): string | null {
  if (handle.length === 0) return "Choose a handle.";
  if (!/^[a-z0-9_]*$/.test(handle)) return "Use lowercase letters, numbers and underscores only.";
  if (handle.length < HANDLE_MIN) return `Use at least ${HANDLE_MIN} characters.`;
  if (handle.length > HANDLE_MAX) return `Use ${HANDLE_MAX} characters or fewer.`;
  return null;
}

const RULE_LABEL: Record<string, string> = {
  guaranteed_outcome: "no results presented as certain",
  inducement_to_bet: "no pressure to bet",
  selling_or_promotion: "no selling or promotion",
  contact_solicitation: "no asking people to contact you elsewhere",
  contact_details: "no contact details",
};

const PROFILE_REQUIRED: Record<string, string> = {
  no_profile: "Create a community profile first.",
  profile_not_public: "Your profile is private. Make it public in the community settings to post, comment or follow.",
  profile_moderated: "Your profile was hidden by moderators, so you can't post. Editing it does not make it visible again: a changed handle or bio goes back to a moderator for review.",
};

type ErrorLike = { status: number; code: string; message: string; details?: unknown };

function detail(details: unknown, key: string): string | undefined {
  if (details && typeof details === "object" && key in details) {
    const value = (details as Record<string, unknown>)[key];
    return typeof value === "string" ? value : undefined;
  }
  return undefined;
}

/** One sentence a person can act on for an error the community API returned. */
export function communityError(error: ErrorLike, fallback = "That didn't work. Try again."): string {
  switch (error.code) {
    case "invalid_handle":
      return `Handles are ${HANDLE_MIN} to ${HANDLE_MAX} characters: lowercase letters, numbers and underscores.`;
    case "handle_taken":
      return "That handle is already in use. Choose another.";
    case "handle_reserved":
      return "That handle is reserved. Choose another.";
    case "links_not_allowed":
      return "Links aren't allowed. Remove the web address and try again.";
    case "content_not_allowed": {
      const rule = detail(error.details, "rule");
      const label = rule ? (RULE_LABEL[rule] ?? rule.replace(/_/g, " ")) : null;
      return `This text breaks a community rule${label ? ` (${label})` : ""}. ${error.message}`;
    }
    case "invalid_text":
      return "Write something first.";
    case "event_not_open":
      return "This game has started or finished, so picks on it are closed.";
    case "pick_exists":
      return "You already have a pick on this market for this game. It is one pick per game and market, and picks can't be edited.";
    case "price_not_available":
      return "No sportsbook has an open price on this selection right now, so the pick can't be recorded. Try again in a moment.";
    case "pick_locked":
      return DELETE_LOCK_NOTE;
    case "profile_required":
      return PROFILE_REQUIRED[detail(error.details, "reason") ?? ""] ?? "A public community profile is needed for this.";
    case "profile_blocked":
      return "Unblock this profile before following it.";
    case "cannot_follow_self":
      return "You can't follow your own profile.";
    case "cannot_report_own_content":
      return "You can't report your own content.";
    case "feature_disabled":
      return "The community is not available right now.";
    case "network":
    case "api_unavailable":
      return error.message;
  }
  if (error.status === 401) return "Log in to do this.";
  if (error.status === 404) return "This is no longer available. It may have been deleted.";
  if (error.status === 429) return "You've reached the limit for now. Try again later.";
  if (error.status === 422) return "The API rejected this. Check the text and try again.";
  return error.message || fallback;
}

/** `429` on posting a pick is the daily cap; everywhere else it is an hourly one. */
export function pickLimitMessage(error: ErrorLike): string | null {
  return error.status === 429 ? "You've reached today's limit for picks. Try again tomorrow." : null;
}

export type StatusTone = "neutral" | "accent" | "error" | "second";

/** A pick's state in one word. Colour is only ever a second cue next to this text. */
export function pickStatus(pick: { status: string; result?: string | null }): { label: string; tone: StatusTone } {
  if (pick.status === "void") return { label: "Void", tone: "neutral" };
  if (pick.status === "graded") {
    if (pick.result === "won") return { label: "Won", tone: "accent" };
    if (pick.result === "lost") return { label: "Lost", tone: "error" };
    return { label: "Push", tone: "neutral" };
  }
  return { label: "Upcoming", tone: "second" };
}

export const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: "spam", label: "Spam" },
  { value: "harassment", label: "Harassment" },
  { value: "inducement_to_bet", label: "Encouraging betting" },
  { value: "misleading_claims", label: "Misleading claims" },
  { value: "personal_information", label: "Personal information" },
  { value: "other", label: "Other" },
];

export function reasonLabel(reason: string): string {
  return REPORT_REASONS.find((entry) => entry.value === reason)?.label ?? reason.replace(/_/g, " ");
}

/** "2026-11" or an ISO date as "November 2026". Anything else is shown as sent. */
export function formatJoined(joined: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(joined);
  if (!match) return joined;
  const month = Number(match[2]);
  const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return month >= 1 && month <= 12 ? `${names[month - 1]} ${match[1]}` : joined;
}

export function countLabel(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

type ProfileText = { handle: string; bio: string | null };

/**
 * What the edit form says after a save. A profile moderators hid or removed stays that way when
 * edited. The API puts it back in the review queue only when the handle or the bio changed
 * (handle compared trimmed and in lower case, a blank bio as none), so only then is a review
 * mentioned.
 */
export function profileSavedText(before: ProfileText | undefined, sent: ProfileText, moderationStatus: string | undefined): string {
  if (moderationStatus === undefined || moderationStatus === "visible") return "Profile saved.";
  const handleChanged = before?.handle !== sent.handle.trim().toLowerCase();
  const bioChanged = (before?.bio?.trim() ? before.bio : null) !== (sent.bio?.trim() ? sent.bio : null);
  if (handleChanged || bioChanged) return "Profile saved. It stays hidden, and the change goes to a moderator for review.";
  return "Profile saved. It stays hidden: only a moderator can make it visible again.";
}
