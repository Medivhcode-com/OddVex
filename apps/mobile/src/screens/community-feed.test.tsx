import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { PICKS_EXPLAINED, PRIVATE_PROFILE, PROFILE_VISIBILITY } from '@/components/community-copy';
import { CommunityFeedScreen } from '@/screens/community-feed';
import { CommunityGuidelinesScreen } from '@/screens/community-guidelines';
import { GamesScreen } from '@/screens/games';
import { errorResponse, jsonResponse } from '@/test/api';
import { BANNED_COPY } from '@/test/banned-copy';
import { showCommunity } from '@/test/community';
import { flagsAllOn, flagsCommunityOn, guidelines, lostPick, myProfile, privateProfile, pushPick, upcomingPick, voidPick, wonPick } from '@/test/fixtures';
import { fakeSession } from '@/test/session';
import { screenStrings } from '@/test/strings';

const PROFILE = 'GET /v1/community/profile';
const GUIDELINES = 'GET /v1/community/guidelines';
const FOLLOWING = 'GET /v1/community/feed?scope=following&limit=20';
const EVERYONE = 'GET /v1/community/feed?scope=everyone&limit=20';
const noProfile = () => errorResponse(404, 'not_found', 'You have no community profile yet');
const page = (items: unknown[], next_before: string | null = null) => ({ items, next_before });

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('community entry points', () => {
  const games = { 'GET /v1/events': [], 'GET /v1/leagues': [], 'GET /v1/meta': { data_mode: 'synthetic' } };

  it('has no way in from Games while the flag is off', async () => {
    await showCommunity(<GamesScreen />, games, { flags: flagsAllOn, session: fakeSession({ user: null }) });

    expect(await screen.findByText('No games to show')).toBeOnTheScreen();
    expect(screen.getByRole('link', { name: /^Value screen/ })).toBeOnTheScreen();
    expect(screen.queryByText('Community')).toBeNull();
    expect(screen.queryByRole('link', { name: /^Community/ })).toBeNull();
  });

  it('has a link row on Games while the flag is on', async () => {
    await showCommunity(<GamesScreen />, games, { session: fakeSession({ user: null }) });

    await fireEvent.press(await screen.findByRole('link', { name: 'Community: picks posted before the game and graded from the final score' }));
    expect(router.push).toHaveBeenCalledWith('/community');
  });
});

describe('CommunityFeedScreen behind its flag', () => {
  it('shows "not available" and asks the API for nothing while the flag is off', async () => {
    const { fetchMock } = await showCommunity(<CommunityFeedScreen />, {}, { flags: flagsAllOn });

    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows the same state when the flag was turned off after the app read it', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: () => errorResponse(404, 'feature_disabled', 'This feature is not available') });

    expect(await screen.findByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
  });

  it('keeps the guidelines behind the flag too', async () => {
    const { fetchMock } = await showCommunity(<CommunityGuidelinesScreen />, {}, { flags: flagsAllOn, session: fakeSession({ user: null }) });
    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('asks a signed-out person to log in', async () => {
    const { fetchMock } = await showCommunity(<CommunityFeedScreen />, {}, { session: fakeSession({ user: null }) });

    expect(screen.getByText('Log in to see the community')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));
    expect(router.push).toHaveBeenCalledWith('/login');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('first entry without a profile', () => {
  it("shows the API's guidelines, not rules written in the app, and the profile form", async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: noProfile, [GUIDELINES]: guidelines });

    expect(await screen.findByText(guidelines.intro)).toBeOnTheScreen();
    expect(screen.getByText('1. Fixture rule one')).toBeOnTheScreen();
    expect(screen.getByText('2. Fixture rule two')).toBeOnTheScreen();
    expect(screen.getByText('No paid picks and no links of any kind.')).toBeOnTheScreen();
    expect(screen.getByText(guidelines.enforcement)).toBeOnTheScreen();
    expect(screen.getByText(guidelines.help)).toBeOnTheScreen();

    expect(screen.getByText('Create your profile')).toBeOnTheScreen();
    expect(screen.getByLabelText('Handle')).toBeOnTheScreen();
    expect(screen.getByRole('switch', { name: 'Make my profile public' })).not.toBeChecked();
    expect(screen.getByText(PROFILE_VISIBILITY)).toBeOnTheScreen();
    // No feed is requested before there is a profile.
    expect(screen.queryByRole('radio', { name: 'Everyone' })).toBeNull();
  });

  it('moves on to the feed once the profile is created', async () => {
    const { sent, session, serve } = await showCommunity(<CommunityFeedScreen />, {
      [PROFILE]: noProfile,
      [GUIDELINES]: guidelines,
      'PUT /v1/community/profile': () => jsonResponse(myProfile, 201),
    });

    await fireEvent.changeText(await screen.findByLabelText('Handle'), 'Sam_Reads_Lines');
    await fireEvent.press(screen.getByRole('switch', { name: 'Make my profile public' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Create profile' }));

    await waitFor(() => expect(session.changed).toHaveBeenCalledWith('community'));
    expect(sent().find((request) => request.method === 'PUT')?.body).toEqual({ handle: 'sam_reads_lines', bio: null, is_public: true });
    // The fake session does not bump its revision; the real one reloads the profile and the feed appears.
    serve({ [PROFILE]: myProfile, [FOLLOWING]: page([]) });
  });
});

describe('the feed', () => {
  it('opens on Following, explains picks in one line and shows each card', async () => {
    const { sent } = await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick, wonPick]) });

    expect(await screen.findByText('Harbor City Gulls -3.5 spread')).toBeOnTheScreen();
    expect(screen.getByText(new RegExp(`^${PICKS_EXPLAINED.replace(/\./g, '\\.')}`))).toBeOnTheScreen();
    expect(screen.getByRole('radio', { name: 'Following' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Everyone' })).not.toBeChecked();

    expect(screen.getAllByText('@fictional_fox')).toHaveLength(2);
    expect(screen.getAllByText(/^Iron Valley Forge at Harbor City Gulls · /)).toHaveLength(2);
    expect(screen.getAllByText('Price when posted: −108 at Northstar Sports')).toHaveLength(2);
    expect(screen.getByText('The line moved half a point since open.')).toBeOnTheScreen();
    expect(screen.getAllByText(/^Posted \d+/)).toHaveLength(2);
    expect(screen.getByText('Upcoming')).toBeOnTheScreen();
    expect(screen.getByText('Won')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: '1 comment' })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: '0 comments' })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Like, 2 likes' })).not.toBeSelected();
    expect(screen.getByRole('button', { name: 'Liked, 1 like' })).toBeSelected();
    expect(screen.getByText('Like · 2')).toBeOnTheScreen();
    expect(screen.getByText('Liked · 1')).toBeOnTheScreen();

    const feed = sent().find((request) => request.path.startsWith('/v1/community/feed'));
    expect(feed?.headers.authorization).toBe('Bearer token-1');

    const strings = screenStrings();
    expect(strings.length).toBeGreaterThan(10);
    for (const text of strings) for (const banned of BANNED_COPY) expect(text).not.toMatch(banned);
  });

  it('writes every status as a word', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick, wonPick, lostPick, pushPick, voidPick]) });

    expect(await screen.findByText('Upcoming')).toBeOnTheScreen();
    for (const word of ['Won', 'Lost', 'Push', 'Void']) expect(screen.getByText(word)).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: /Harbor City Gulls moneyline\. Price when posted: −108 at Northstar Sports\. Won\.$/ })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: /Iron Valley Forge moneyline\..* Lost\.$/ })).toBeOnTheScreen();
  });

  it('switches to Everyone and asks the API for that scope', async () => {
    const { sent } = await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([]), [EVERYONE]: page([lostPick]) });

    expect(await screen.findByText('No picks from people you follow')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('radio', { name: 'Everyone' }));

    expect(await screen.findByText('Iron Valley Forge moneyline')).toBeOnTheScreen();
    expect(screen.getByRole('radio', { name: 'Everyone' })).toBeChecked();
    expect(sent().map((request) => request.path)).toEqual(['/v1/community/profile', '/v1/community/feed?scope=following&limit=20', '/v1/community/feed?scope=everyone&limit=20']);
  });

  it('has an empty state for each scope', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([]), [EVERYONE]: page([]) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Show everyone' }));
    expect(await screen.findByText('No picks yet')).toBeOnTheScreen();
  });

  it('loads the next page with the cursor and adds it below', async () => {
    const { sent } = await showCommunity(<CommunityFeedScreen />, {
      [PROFILE]: myProfile,
      [FOLLOWING]: page([upcomingPick], 'cursor-1'),
      'GET /v1/community/feed?scope=following&before=cursor-1&limit=20': page([upcomingPick, wonPick]),
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Load more' }));

    expect(await screen.findByText('Harbor City Gulls moneyline')).toBeOnTheScreen();
    // A pick already on screen is not listed twice.
    expect(screen.getAllByText('Harbor City Gulls -3.5 spread')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
    expect(screen.getByText(/^That is every pick, newest first\./)).toBeOnTheScreen();
    expect(sent().at(-1)?.path).toBe('/v1/community/feed?scope=following&before=cursor-1&limit=20');
  });

  it('keeps the loaded picks and says so when the next page fails', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick], 'cursor-1') });

    await fireEvent.press(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText("OddVex can't reach its data service right now. Try again in a moment.")).toBeOnTheScreen();
    expect(screen.getByText('Harbor City Gulls -3.5 spread')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeOnTheScreen();
  });

  it('likes with PUT and unlikes with DELETE, and shows the count the API answers', async () => {
    const { sent } = await showCommunity(<CommunityFeedScreen />, {
      [PROFILE]: myProfile,
      [FOLLOWING]: page([upcomingPick]),
      'PUT /v1/community/picks/pick_1/like': { pick_id: 'pick_1', liked_by_me: true, like_count: 5 },
      'DELETE /v1/community/picks/pick_1/like': { pick_id: 'pick_1', liked_by_me: false, like_count: 4 },
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Like, 2 likes' }));
    expect(await screen.findByRole('button', { name: 'Liked, 5 likes' })).toBeSelected();
    expect(screen.getByText('Liked · 5')).toBeOnTheScreen();
    expect(sent().at(-1)).toMatchObject({ method: 'PUT', path: '/v1/community/picks/pick_1/like' });
    expect(sent().at(-1)?.body).toBeUndefined();

    await fireEvent.press(screen.getByRole('button', { name: 'Liked, 5 likes' }));
    expect(await screen.findByRole('button', { name: 'Like, 4 likes' })).not.toBeSelected();
    expect(sent().at(-1)).toMatchObject({ method: 'DELETE', path: '/v1/community/picks/pick_1/like' });
  });

  it('leaves the like as it was and says so when it is not saved', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick]) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Like, 2 likes' }));
    expect(await screen.findByText("OddVex can't reach its data service right now. Try again in a moment.")).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Like, 2 likes' })).not.toBeSelected();
  });

  it('opens the pick, the author and the leaderboard', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick]) });

    await fireEvent.press(await screen.findByRole('button', { name: /^Iron Valley Forge at Harbor City Gulls\. Harbor City Gulls -3\.5 spread\./ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/picks/[id]', params: { id: 'pick_1' } });
    await fireEvent.press(screen.getByRole('link', { name: 'Profile of fictional_fox' }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/profiles/[handle]', params: { handle: 'fictional_fox' } });
    await fireEvent.press(screen.getByRole('button', { name: 'Your profile' }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/profiles/[handle]', params: { handle: 'sam_reads_lines' } });
    await fireEvent.press(screen.getByRole('button', { name: 'Leaderboard' }));
    expect(router.push).toHaveBeenLastCalledWith('/community/leaderboard');
  });

  it('has no leaderboard link while that flag is off', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([upcomingPick]) }, { flags: { ...flagsCommunityOn, community_leaderboard: false } });

    expect(await screen.findByRole('button', { name: 'Your profile' })).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Leaderboard' })).toBeNull();
  });

  it('tells someone with a private profile that they can browse but not post', async () => {
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: privateProfile, [FOLLOWING]: page([upcomingPick]) });

    expect(await screen.findByText(PRIVATE_PROFILE)).toBeOnTheScreen();
    expect(screen.getByText('Harbor City Gulls -3.5 spread')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Edit your profile' }));
    expect(router.push).toHaveBeenLastCalledWith('/community/profile');
  });

  it('offers a retry when the feed does not load', async () => {
    const { serve } = await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile });

    expect(await screen.findByText("OddVex can't reach its data service")).toBeOnTheScreen();
    serve({ [PROFILE]: myProfile, [FOLLOWING]: page([wonPick]) });
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Harbor City Gulls moneyline')).toBeOnTheScreen();
  });

  it('draws what people wrote as plain text', async () => {
    const analysis = '<b>bold</b> [link](https://example.test) www.example.test';
    await showCommunity(<CommunityFeedScreen />, { [PROFILE]: myProfile, [FOLLOWING]: page([{ ...upcomingPick, analysis }]) });

    expect(await screen.findByText(analysis)).toBeOnTheScreen();
    expect(screen.queryByRole('link', { name: /example/ })).toBeNull();
  });
});
