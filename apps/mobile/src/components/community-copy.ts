import { ApiError, describeError } from '@/api/client';
import type { CommunityPick, ReportReason } from '@/api/types';

/** The one line every list of picks carries. */
export const PICKS_EXPLAINED = 'Every pick is timestamped before the game and graded automatically from the final score.';

export const PICK_LOCKED = "Picks can't be deleted after the game starts, so records stay honest.";

/** Shown next to every field that takes text other people will read. */
export const TEXT_RULES = 'Plain text only. No links, no contact details, no selling, and no promises about a result.';

export const PROFILE_VISIBILITY =
  'A public profile shows your handle, your bio, your picks and your graded record. It never shows your email, your name, your bets or your plan.';

export const PRIVATE_PROFILE = 'Your profile is private. You can browse, but only a public profile can post picks and comments or follow people.';

export const NEEDS_PUBLIC_PROFILE = 'You need a public community profile to do this.';

/**
 * Shown to the owner of a profile moderators hid or removed. Editing it does not bring it back: the API keeps it
 * hidden and puts it back in the moderators' queue, and only a moderator can make it visible again.
 */
export const PROFILE_HIDDEN_EXPLAINED =
  'Other people cannot see it, and you cannot post. If you change the handle or the bio, the profile stays hidden and goes back to the moderators for review. Only a moderator can make it visible again.';

export const REPORT_SENT = 'Report sent. A moderator will review it. The person you reported is not told who sent it.';

export const RANKING_EXPLAINED =
  'Ranking uses the lower end of each win-rate interval, not the win rate itself, so a short run of results cannot rank first.';

export const BLOCK_EFFECTS =
  "You will stop following each other, and neither of you will see the other's profile, picks or comments anywhere. They are not told.";

export const UNBLOCK_EFFECTS = 'You will see each other again. Follows removed by the block are not restored.';

export const HANDLE_RULE = '3 to 20 characters: lowercase letters, numbers and underscores.';
export const BIO_MAX = 280;
export const ANALYSIS_MAX = 1000;
export const COMMENT_MAX = 500;
export const REPORT_DETAILS_MAX = 500;

export const REPORT_REASONS: readonly { value: ReportReason; label: string }[] = [
  { value: 'spam', label: 'Spam' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'inducement_to_bet', label: 'Encouraging betting' },
  { value: 'misleading_claims', label: 'Misleading claims' },
  { value: 'personal_information', label: 'Personal information' },
  { value: 'other', label: 'Other' },
];

/** The pick's state in words. Never carried by color alone: the badge always shows this text. */
export function pickStatusLabel(pick: { status: CommunityPick['status']; result?: CommunityPick['result'] }): 'Upcoming' | 'Won' | 'Lost' | 'Push' | 'Void' {
  if (pick.status === 'void') return 'Void';
  if (pick.status === 'graded') return pick.result === 'won' ? 'Won' : pick.result === 'lost' ? 'Lost' : 'Push';
  return 'Upcoming';
}

/** What each content rule the API can name means, in the words shown to the author. */
const CONTENT_RULES: Record<string, string> = {
  guaranteed_outcome: 'This reads as a promise about a result, and no result is certain. Reword it and try again.',
  inducement_to_bet: 'This reads as pressure to bet, to bet more or to win money back. Reword it and try again.',
  selling_or_promotion: "Selling picks, promotions and payment details aren't allowed here. Remove them and try again.",
  contact_solicitation: "Asking people to contact you somewhere else isn't allowed here. Remove that and try again.",
  contact_details: "Phone numbers, email addresses and other contact details aren't allowed here. Remove them and try again.",
};

function ruleOf(error: ApiError): string | null {
  const details = error.details;
  if (typeof details !== 'object' || details === null || !('rule' in details)) return null;
  return typeof details.rule === 'string' ? details.rule : null;
}

type Action = 'profile' | 'pick' | 'comment' | 'report' | 'follow' | 'other';

const LIMITS: Partial<Record<Action, string>> = {
  pick: 'You have reached the daily limit for picks. Try again tomorrow.',
  comment: 'You have reached the hourly limit for comments. Try again later.',
  report: 'You have reached the hourly limit for reports. Try again later.',
};

/**
 * One sentence for an API rejection in the community, in OddVex's words. Codes without their own sentence
 * fall back to the shared wording (unreachable service, switched-off feature, the API's own message).
 */
export function communityError(error: unknown, fallback: string, action: Action = 'other'): string {
  if (!(error instanceof ApiError)) return describeError(error, fallback);
  if (error.status === 429) return LIMITS[action] ?? describeError(error, fallback);
  switch (error.code) {
    case 'handle_taken':
      return 'That handle is already taken. Try another one.';
    case 'handle_reserved':
      return "That handle is reserved and can't be used. Try another one.";
    case 'invalid_handle':
      return `A handle is ${HANDLE_RULE}`;
    case 'links_not_allowed':
      return "Links aren't allowed here. Remove the link and try again.";
    case 'content_not_allowed': {
      const rule = ruleOf(error);
      return (rule && CONTENT_RULES[rule]) || `This text breaks a community rule. ${error.message}`;
    }
    case 'event_not_open':
      return 'This game has already started, so picks on it are closed.';
    case 'pick_exists':
      return 'You already have a pick on this market for this game. One pick per game and market.';
    case 'price_not_available':
      return "No sportsbook has an open price for this selection right now, so it can't be posted. Try again in a moment.";
    case 'pick_locked':
      return PICK_LOCKED;
    case 'profile_required':
      return NEEDS_PUBLIC_PROFILE;
    case 'profile_blocked':
      return 'Unblock this profile before following it.';
    case 'cannot_report_own_content':
      return "You can't report your own content.";
    default:
      return describeError(error, fallback);
  }
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "2026-11" becomes "November 2026". Anything else is shown as sent. */
export function joinedText(joined: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(joined);
  const month = match ? MONTHS[Number(match[2]) - 1] : undefined;
  return month && match ? `${month} ${match[1]}` : joined;
}

/** "1 like", "3 likes". */
export function countText(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}
