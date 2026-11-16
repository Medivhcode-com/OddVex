import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { BLOCK_EFFECTS, PRIVATE_PROFILE, REPORT_SENT, UNBLOCK_EFFECTS } from '@/components/community-copy';
import { intervalText, sampleText } from '@/components/community-record';
import { CommunityProfileScreen } from '@/screens/community-profile';
import { errorResponse, jsonResponse } from '@/test/api';
import { BANNED_COPY } from '@/test/banned-copy';
import { showCommunity } from '@/test/community';
import { flagsAllOn, fullRecord, myProfile, myUpcomingPick, otherProfile, privateProfile, smallRecord, upcomingPick, wonPick } from '@/test/fixtures';
import { screenStrings } from '@/test/strings';

const MINE = 'GET /v1/community/profile';
const FOX = 'GET /v1/community/profiles/fictional_fox';
const FOX_PICKS = 'GET /v1/community/picks?handle=fictional_fox&limit=20';
const MY_PICKS = 'GET /v1/community/picks?handle=sam_reads_lines&limit=20';
const BLOCKS = 'GET /v1/community/blocks';
const page = (items: unknown[], next_before: string | null = null) => ({ items, next_before });
const noContent = () => ({ ok: true, status: 204, json: async () => null });
const base = { [MINE]: myProfile, [FOX]: otherProfile, [FOX_PICKS]: page([upcomingPick, wonPick]) };
const showFox = (routes: Record<string, unknown> = {}, options?: Parameters<typeof showCommunity>[2]) =>
  showCommunity(<CommunityProfileScreen handle="fictional_fox" />, { ...base, ...routes }, options);

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('record helpers', () => {
  it('writes the interval and the sample from the API’s numbers', () => {
    expect(intervalText(fullRecord)).toBe('95% interval 34.5% to 65.5%');
    expect(intervalText({ win_rate_interval: null })).toBeNull();
    expect(sampleText(fullRecord)).toBe('36 graded picks');
    expect(sampleText({ picks: 1 })).toBe('1 graded pick');
  });
});

describe('CommunityProfileScreen', () => {
  it('shows "not available" and asks for nothing while the flag is off', async () => {
    const { fetchMock } = await showFox({}, { flags: flagsAllOn });
    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows the handle, the bio as plain text, the month joined and the counts', async () => {
    await showFox();

    expect(await screen.findByRole('header', { name: '@fictional_fox' })).toBeOnTheScreen();
    expect(screen.getByText('Fictional profile. <b>Not markup</b> https://example.test')).toBeOnTheScreen();
    expect(screen.getByText('Joined October 2026 · 1 follower · 4 following')).toBeOnTheScreen();
    expect(screen.queryByRole('link', { name: /example/ })).toBeNull();
    // Nothing that identifies the person beyond the handle.
    expect(screen.queryByText(/@example\.test|Email|Plan/)).toBeNull();
  });

  it('shows the graded record with its interval, sample size, average price and flat-stake ROI', async () => {
    await showFox();

    expect(await screen.findByLabelText('Graded picks, 36')).toBeOnTheScreen();
    expect(screen.getByLabelText('Won-lost-push, 18-18-0, 18 won, 18 lost, 0 push')).toBeOnTheScreen();
    expect(screen.getByLabelText('Win rate, 50.0%, 95% interval 34.5% to 65.5%, from 36 graded picks')).toBeOnTheScreen();
    expect(screen.getByLabelText('Average price, +119')).toBeOnTheScreen();
    expect(screen.getByLabelText('Flat-stake ROI, +4.3%, See how it is calculated below')).toBeOnTheScreen();
    expect(screen.getByText('How this record is calculated')).toBeOnTheScreen();
    expect(screen.getByText(fullRecord.method)).toBeOnTheScreen();
    expect(screen.getByText(fullRecord.caveat)).toBeOnTheScreen();
    expect(screen.queryByText('Small sample')).toBeNull();

    const strings = screenStrings();
    for (const text of strings) for (const banned of BANNED_COPY) expect(text).not.toMatch(banned);
  });

  it('shows the API’s sample note as a caution when there is one', async () => {
    await showFox({ [FOX]: { ...otherProfile, record: smallRecord } });

    expect(await screen.findByText('Small sample')).toBeOnTheScreen();
    expect(screen.getByText('Small sample: 6 graded picks. Fewer than 30 is too few to tell skill from luck.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Win rate, 40.0%, 95% interval 11.8% to 76.9%, from 6 graded picks')).toBeOnTheScreen();
    expect(screen.getByLabelText('Flat-stake ROI, −8.3%, See how it is calculated below')).toBeOnTheScreen();
  });

  it('handles a profile with nothing graded yet', async () => {
    const empty = { ...smallRecord, picks: 0, wins: 0, losses: 0, pushes: 0, win_rate: null, win_rate_interval: null, average_price: null, flat_stake_roi: null, sample_note: null };
    await showFox({ [FOX]: { ...otherProfile, record: empty } });

    expect(await screen.findByLabelText('Win rate, n/a, From 0 graded picks')).toBeOnTheScreen();
    expect(screen.getByLabelText('Average price, n/a')).toBeOnTheScreen();
    expect(screen.getByLabelText('Flat-stake ROI, n/a, See how it is calculated below')).toBeOnTheScreen();
  });

  it('lists the profile’s picks and pages them', async () => {
    const { sent } = await showFox({
      [FOX_PICKS]: page([upcomingPick], 'p-1'),
      'GET /v1/community/picks?handle=fictional_fox&before=p-1&limit=20': page([wonPick]),
    });

    expect(await screen.findByText('Harbor City Gulls -3.5 spread')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Harbor City Gulls moneyline')).toBeOnTheScreen();
    expect(sent().at(-1)?.path).toBe('/v1/community/picks?handle=fictional_fox&before=p-1&limit=20');
  });

  it('answers a hidden, private or blocking profile with "nothing found"', async () => {
    await showFox({ [FOX]: () => errorResponse(404, 'not_found', 'Profile not found') });
    expect(await screen.findByText('Nothing found here')).toBeOnTheScreen();
  });
});

describe('follow', () => {
  it('follows with POST and shows Following', async () => {
    const { sent, session } = await showFox({ 'POST /v1/community/follows/fictional_fox': { handle: 'fictional_fox', is_following: true } });

    const follow = await screen.findByRole('button', { name: 'Follow @fictional_fox' });
    expect(follow).not.toBeSelected();
    await fireEvent.press(follow);

    expect(await screen.findByRole('button', { name: 'Following @fictional_fox' })).toBeSelected();
    expect(screen.getByText('★ Following')).toBeOnTheScreen();
    const request = sent().find((item) => item.method === 'POST');
    expect(request?.path).toBe('/v1/community/follows/fictional_fox');
    expect(request?.body).toBeUndefined();
    expect(session.changed).toHaveBeenCalledWith('community');
  });

  it('unfollows with DELETE', async () => {
    const { sent } = await showFox({ [FOX]: { ...otherProfile, is_following: true }, 'DELETE /v1/community/follows/fictional_fox': noContent });

    await fireEvent.press(await screen.findByRole('button', { name: 'Following @fictional_fox' }));
    expect(await screen.findByRole('button', { name: 'Follow @fictional_fox' })).not.toBeSelected();
    expect(sent().find((item) => item.method === 'DELETE')?.path).toBe('/v1/community/follows/fictional_fox');
  });

  it('explains that following needs a public profile', async () => {
    await showFox({
      [MINE]: privateProfile,
      'POST /v1/community/follows/fictional_fox': () => errorResponse(403, 'profile_required', 'A public community profile is required for this', { reason: 'not_public' }),
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Follow @fictional_fox' }));
    expect(await screen.findByText('You need a public community profile to do this.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Follow @fictional_fox' })).not.toBeSelected();
  });
});

describe('block', () => {
  it('says what blocking does before it does it', async () => {
    const { sent, session } = await showFox({ 'PUT /v1/community/blocks/fictional_fox': { handle: 'fictional_fox', is_blocked: true } });

    await fireEvent.press(await screen.findByRole('button', { name: 'Block @fictional_fox' }));
    expect(screen.getByText(`Block @fictional_fox? ${BLOCK_EFFECTS}`)).toBeOnTheScreen();
    expect(BLOCK_EFFECTS).toBe(
      "You will stop following each other, and neither of you will see the other's profile, picks or comments anywhere. They are not told.",
    );
    expect(sent().some((item) => item.method === 'PUT')).toBe(false);

    await fireEvent.press(screen.getByRole('button', { name: 'Block @fictional_fox' }));
    expect(await screen.findByText('You have blocked this profile.')).toBeOnTheScreen();
    const request = sent().find((item) => item.method === 'PUT');
    expect(request?.path).toBe('/v1/community/blocks/fictional_fox');
    expect(request?.body).toBeUndefined();
    expect(session.changed).toHaveBeenCalledWith('community');
    // A blocked profile cannot be followed from here; the way back is Unblock.
    expect(screen.queryByRole('button', { name: /^Follow/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Unblock @fictional_fox' })).toBeOnTheScreen();
  });

  it('changes nothing when the confirmation is cancelled', async () => {
    const { sent } = await showFox();

    await fireEvent.press(await screen.findByRole('button', { name: 'Block @fictional_fox' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Follow @fictional_fox' })).toBeOnTheScreen();
    expect(sent().some((item) => item.method === 'PUT')).toBe(false);
  });

  it('unblocks with DELETE after saying that follows are not restored', async () => {
    const { sent } = await showFox({ [FOX]: { ...otherProfile, is_blocked: true }, 'DELETE /v1/community/blocks/fictional_fox': noContent });

    expect(await screen.findByText('You have blocked this profile.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Unblock @fictional_fox' }));
    expect(screen.getByText(`Unblock @fictional_fox? ${UNBLOCK_EFFECTS}`)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Unblock @fictional_fox' }));

    expect(await screen.findByRole('button', { name: 'Follow @fictional_fox' })).toBeOnTheScreen();
    expect(sent().find((item) => item.method === 'DELETE')?.path).toBe('/v1/community/blocks/fictional_fox');
  });
});

describe('report profile', () => {
  it('reports the profile by its handle', async () => {
    const { sent } = await showFox({ 'POST /v1/community/reports': () => jsonResponse({ id: 'rep_3', status: 'open' }, 201) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Report the profile @fictional_fox' }));
    await fireEvent.press(screen.getByRole('radio', { name: /: Misleading claims$/ }));
    await fireEvent.press(screen.getByRole('button', { name: 'Send report' }));

    expect(await screen.findByText(REPORT_SENT)).toBeOnTheScreen();
    expect(sent().find((item) => item.path === '/v1/community/reports')?.body).toEqual({ target_type: 'profile', target_id: 'fictional_fox', reason: 'misleading_claims' });
  });
});

describe('your own profile', () => {
  const own = { [MINE]: myProfile, [MY_PICKS]: page([myUpcomingPick]), [BLOCKS]: { items: [{ handle: 'notreal_nia', since: '2026-11-10T00:00:00Z' }] } };

  it('offers Edit profile and the blocked list, and none of Follow, Block or Report', async () => {
    const { sent } = await showCommunity(<CommunityProfileScreen handle="sam_reads_lines" />, own);

    expect(await screen.findByRole('header', { name: '@sam_reads_lines' })).toBeOnTheScreen();
    expect(screen.getByText('This is your profile. It is public.')).toBeOnTheScreen();
    expect(screen.getByText('Joined November 2026 · 2 followers · 3 following')).toBeOnTheScreen();
    expect(screen.getByLabelText('Graded picks, 6')).toBeOnTheScreen();
    expect(await screen.findByText('@notreal_nia')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: /^Follow|^Block|^Report the profile/ })).toBeNull();
    // Your own profile is read from your own route, which also answers while it is private.
    expect(sent().some((item) => item.path.startsWith('/v1/community/profiles/'))).toBe(false);

    await fireEvent.press(screen.getByRole('button', { name: 'Edit profile' }));
    expect(router.push).toHaveBeenCalledWith('/community/profile');
  });

  it('unblocks from the list', async () => {
    const { sent, session } = await showCommunity(<CommunityProfileScreen handle="sam_reads_lines" />, { ...own, 'DELETE /v1/community/blocks/notreal_nia': noContent });

    await fireEvent.press(await screen.findByRole('button', { name: 'Unblock @notreal_nia' }));
    await waitFor(() => expect(session.changed).toHaveBeenCalledWith('community'));
    expect(sent().find((item) => item.method === 'DELETE')?.path).toBe('/v1/community/blocks/notreal_nia');
  });

  it('says so when nobody is blocked, and that a private profile cannot post', async () => {
    await showCommunity(<CommunityProfileScreen handle="sam_reads_lines" />, { ...own, [MINE]: privateProfile, [BLOCKS]: { items: [] } });

    expect(await screen.findByText('You have not blocked anyone.')).toBeOnTheScreen();
    expect(screen.getByText(PRIVATE_PROFILE)).toBeOnTheScreen();
  });
});
