import { ApiError, ApiUnavailableError } from '@/api/client';
import { communityError, joinedText, PICK_LOCKED, pickStatusLabel, REPORT_REASONS } from '@/components/community-copy';
import { BANNED_COPY } from '@/test/banned-copy';

// The source files are read from disk. This package has no Node type definitions, so the three functions
// used are described here rather than adding a dependency for one test.
type Fs = { readdirSync(path: string): string[]; readFileSync(path: string, encoding: 'utf8'): string; statSync(path: string): { isDirectory(): boolean } };
const { readdirSync, readFileSync, statSync } = jest.requireActual<Fs>('fs');
const { join } = jest.requireActual<{ join(...parts: string[]): string }>('path');
declare const __dirname: string;

/** Decorations a ranking must not carry. */
const BANNED_DECORATION = [/trophy|trophies/i, /medal/i, /flame/i, /\bhot\b/i, /🏆|🥇|🥈|🥉|🔥|👑/u];

const SRC = join(__dirname, '..');
const COMMUNITY_FILE = /(community|pick-card|share-pick|report-form|profile-form|guidelines|limited-text)[^/]*\.tsx?$/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return COMMUNITY_FILE.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
  });
}

/**
 * The file's text without API identifiers. `guaranteed_outcome` and `units_profit` are names the API uses for
 * a content rule and a field, not words shown to anyone, so snake_case tokens are dropped before scanning.
 * Everything else is scanned: string literals, JSX text, labels, hints and comments alike.
 */
function staticText(path: string): string {
  return readFileSync(path, 'utf8').replace(/\b[a-z]+(?:_[a-z0-9]+)+\b/g, ' ');
}

describe('community copy', () => {
  const files = sourceFiles(SRC);

  it('scans every community screen and component', () => {
    const names = files.map((path) => path.replace(`${SRC}/`, ''));
    for (const expected of [
      'components/community-copy.ts',
      'components/community-entry.tsx',
      'components/community-gate.tsx',
      'components/community-record.tsx',
      'components/guidelines.tsx',
      'components/pick-card.tsx',
      'components/profile-form.tsx',
      'components/report-form.tsx',
      'components/share-pick.tsx',
      'screens/community-feed.tsx',
      'screens/community-leaderboard.tsx',
      'screens/community-pick.tsx',
      'screens/community-profile.tsx',
      'screens/community-profile-edit.tsx',
    ]) {
      expect(names).toContain(expected);
    }
  });

  it('never uses a banned phrase in its static strings', () => {
    for (const path of files) {
      const text = staticText(path);
      for (const banned of BANNED_COPY) expect({ path, banned: String(banned), found: banned.test(text) }).toEqual({ path, banned: String(banned), found: false });
    }
  });

  it('the scan does catch each phrase', () => {
    for (const sample of ['A guaranteed winner', 'lock of the week', "can't lose", 'risk-free', 'free money', 'on a hot streak', 'he is on fire', 'best bets today', '3 units']) {
      expect(BANNED_COPY.some((banned) => banned.test(sample))).toBe(true);
    }
    expect(BANNED_COPY.some((banned) => banned.test('community reunites'))).toBe(false);
  });

  it('keeps trophies, medals, flames and "hot" out of the leaderboard', () => {
    const text = staticText(join(SRC, 'screens/community-leaderboard.tsx'));
    for (const banned of BANNED_DECORATION) expect(text).not.toMatch(banned);
  });

  it('never asks for a stake or a confidence rating when sharing a pick', () => {
    const text = staticText(join(SRC, 'components/share-pick.tsx'));
    expect(text).not.toMatch(/label="[^"]*(stake|confidence|amount|wager)/i);
  });
});

describe('pickStatusLabel', () => {
  it('writes the status as one of five words', () => {
    expect(pickStatusLabel({ status: 'pending', result: null })).toBe('Upcoming');
    expect(pickStatusLabel({ status: 'graded', result: 'won' })).toBe('Won');
    expect(pickStatusLabel({ status: 'graded', result: 'lost' })).toBe('Lost');
    expect(pickStatusLabel({ status: 'graded', result: 'push' })).toBe('Push');
    expect(pickStatusLabel({ status: 'void', result: null })).toBe('Void');
  });
});

describe('communityError', () => {
  const rejected = (status: number, code: string, details?: unknown) => new ApiError(status, code, 'API wording', details);

  it('maps each code to plain words', () => {
    expect(communityError(rejected(409, 'handle_taken'), 'x')).toBe('That handle is already taken. Try another one.');
    expect(communityError(rejected(422, 'handle_reserved'), 'x')).toBe("That handle is reserved and can't be used. Try another one.");
    expect(communityError(rejected(422, 'invalid_handle'), 'x')).toBe('A handle is 3 to 20 characters: lowercase letters, numbers and underscores.');
    expect(communityError(rejected(422, 'links_not_allowed', { rule: 'links' }), 'x')).toBe("Links aren't allowed here. Remove the link and try again.");
    expect(communityError(rejected(422, 'event_not_open'), 'x')).toBe('This game has already started, so picks on it are closed.');
    expect(communityError(rejected(409, 'pick_exists'), 'x')).toBe('You already have a pick on this market for this game. One pick per game and market.');
    expect(communityError(rejected(409, 'pick_locked'), 'x')).toBe(PICK_LOCKED);
    expect(communityError(rejected(403, 'profile_required'), 'x')).toBe('You need a public community profile to do this.');
    expect(communityError(rejected(422, 'cannot_report_own_content'), 'x')).toBe("You can't report your own content.");
    expect(communityError(rejected(409, 'profile_blocked'), 'x')).toBe('Unblock this profile before following it.');
  });

  it('names the content rule the API named', () => {
    const text = (rule: string) => communityError(rejected(422, 'content_not_allowed', { field: 'body', rule }), 'x');
    expect(text('guaranteed_outcome')).toBe('This reads as a promise about a result, and no result is certain. Reword it and try again.');
    expect(text('inducement_to_bet')).toBe('This reads as pressure to bet, to bet more or to win money back. Reword it and try again.');
    expect(text('selling_or_promotion')).toBe("Selling picks, promotions and payment details aren't allowed here. Remove them and try again.");
    expect(text('contact_solicitation')).toBe("Asking people to contact you somewhere else isn't allowed here. Remove that and try again.");
    expect(text('contact_details')).toBe("Phone numbers, email addresses and other contact details aren't allowed here. Remove them and try again.");
    // A rule added to the API later still gets the API's own sentence.
    expect(text('a_new_rule')).toBe('This text breaks a community rule. API wording');
    expect(communityError(rejected(422, 'content_not_allowed'), 'x')).toBe('This text breaks a community rule. API wording');
  });

  it('says which limit was reached', () => {
    expect(communityError(rejected(429, 'rate_limited'), 'x', 'pick')).toBe('You have reached the daily limit for picks. Try again tomorrow.');
    expect(communityError(rejected(429, 'rate_limited'), 'x', 'comment')).toBe('You have reached the hourly limit for comments. Try again later.');
    expect(communityError(rejected(429, 'rate_limited'), 'x', 'report')).toBe('You have reached the hourly limit for reports. Try again later.');
    expect(communityError(rejected(429, 'rate_limited'), 'x')).toBe('Too many attempts. Wait a minute, then try again.');
  });

  it('falls back to the shared wording', () => {
    expect(communityError(new ApiUnavailableError(), 'x')).toBe("OddVex can't reach its data service right now. Try again in a moment.");
    expect(communityError(rejected(404, 'feature_disabled'), 'x')).toBe("This feature isn't available right now.");
    expect(communityError(new Error('boom'), 'The fallback.')).toBe('The fallback.');
  });
});

describe('display helpers', () => {
  it('writes the month a profile was created', () => {
    expect(joinedText('2026-11')).toBe('November 2026');
    expect(joinedText('2026-01')).toBe('January 2026');
    expect(joinedText('recently')).toBe('recently');
  });

  it('offers the six report reasons the API accepts', () => {
    expect(REPORT_REASONS.map((reason) => reason.label)).toEqual(['Spam', 'Harassment', 'Encouraging betting', 'Misleading claims', 'Personal information', 'Other']);
    expect(REPORT_REASONS.map((reason) => reason.value)).toEqual(['spam', 'harassment', 'inducement_to_bet', 'misleading_claims', 'personal_information', 'other']);
  });
});
