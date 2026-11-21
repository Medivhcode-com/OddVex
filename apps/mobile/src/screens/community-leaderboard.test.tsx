import { fireEvent, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { RANKING_EXPLAINED } from '@/components/community-copy';
import { CommunityLeaderboardScreen } from '@/screens/community-leaderboard';
import { errorResponse } from '@/test/api';
import { BANNED_COPY } from '@/test/banned-copy';
import { showCommunity } from '@/test/community';
import { flagsCommunityOn, leaderboard } from '@/test/fixtures';
import { fakeSession } from '@/test/session';
import { screenStrings } from '@/test/strings';

const BOARD = 'GET /v1/community/leaderboard?window=90d';
const leagues = [{ key: 'nfl', name: 'NFL' }];
const show = (routes: Record<string, unknown> = {}, options?: Parameters<typeof showCommunity>[2]) =>
  showCommunity(<CommunityLeaderboardScreen />, { 'GET /v1/leagues': leagues, [BOARD]: leaderboard, ...routes }, options);

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('CommunityLeaderboardScreen', () => {
  it('needs both flags', async () => {
    const off = await show({}, { flags: { ...flagsCommunityOn, community_leaderboard: false } });
    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(off.fetchMock).not.toHaveBeenCalled();

    const neither = await show({}, { flags: { ...flagsCommunityOn, community: false } });
    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(neither.fetchMock).not.toHaveBeenCalled();
  });

  it('shows the same state when the API says the leaderboard is switched off', async () => {
    await show({ [BOARD]: () => errorResponse(404, 'feature_disabled', 'This feature is not available') });
    expect(await screen.findByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
  });

  it('asks a signed-out person to log in', async () => {
    await show({}, { session: fakeSession({ user: null }) });
    expect(screen.getByText('Log in to see the community')).toBeOnTheScreen();
  });

  it("puts the API's caveat above the rows and says how the ranking works", async () => {
    await show();

    expect(await screen.findByText(leaderboard.caveat)).toBeOnTheScreen();
    expect(screen.getByText('What a ranking does not tell you')).toBeOnTheScreen();
    expect(screen.getByText(RANKING_EXPLAINED)).toBeOnTheScreen();
    expect(RANKING_EXPLAINED).toMatch(/^Ranking uses the lower end of each win-rate interval/);
    expect(screen.getByText(leaderboard.method)).toBeOnTheScreen();

    // The caveat comes before the first row in reading order.
    const strings = screenStrings();
    expect(strings.indexOf(leaderboard.caveat)).toBeGreaterThanOrEqual(0);
    expect(strings.indexOf(leaderboard.caveat)).toBeLessThan(strings.indexOf('fictional_fox'));
  });

  it('shows rank, handle, graded picks, the win rate with its interval, the average price and the flat-stake return on each row', async () => {
    await show({
      [BOARD]: {
        ...leaderboard,
        items: [leaderboard.items[0], { ...leaderboard.items[1], record: { ...leaderboard.items[1].record, average_price: null, flat_stake_roi: -0.0612 } }],
      },
    });

    expect(
      await screen.findByRole('button', {
        name: 'Rank 1. fictional_fox. 36 graded picks. Win rate 50.0%, 95% interval 34.5% to 65.5%. Average price +119, flat-stake ROI +4.3%.',
      }),
    ).toBeOnTheScreen();
    expect(
      screen.getByRole('button', {
        name: 'Rank 2. sample_sam. 32 graded picks. Win rate 46.9%, 95% interval 30.9% to 63.6%. Average price n/a, flat-stake ROI −6.1%.',
      }),
    ).toBeOnTheScreen();
    expect(screen.getByText('Average price +119 · Flat-stake ROI +4.3%')).toBeOnTheScreen();
    expect(screen.getByText('@fictional_fox')).toBeOnTheScreen();
    expect(screen.getByText('36 graded picks · 18-18-0')).toBeOnTheScreen();
    expect(screen.getByText('Win rate 50.0%')).toBeOnTheScreen();
    expect(screen.getByText('95% interval 34.5% to 65.5%')).toBeOnTheScreen();
    // The API's order is kept: nothing is sorted here.
    const strings = screenStrings();
    expect(strings.indexOf('fictional_fox')).toBeLessThan(strings.indexOf('sample_sam'));

    await fireEvent.press(screen.getByRole('button', { name: /^Rank 2\./ }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/community/profiles/[handle]', params: { handle: 'sample_sam' } });
  });

  it('has no trophies, medals, flames, "hot" wording or banned phrases', async () => {
    await show();
    await screen.findByText('@fictional_fox');

    const strings = screenStrings();
    expect(strings.length).toBeGreaterThan(10);
    for (const text of strings) {
      for (const banned of BANNED_COPY) expect(text).not.toMatch(banned);
      expect(text).not.toMatch(/trophy|medal|flame|\bhot\b|champion|winner|🏆|🥇|🔥|👑/iu);
    }
  });

  it('sends the league and the period chosen with the pills', async () => {
    const { sent } = await show({
      'GET /v1/community/leaderboard?window=30d': leaderboard,
      'GET /v1/community/leaderboard?league=nfl&window=30d': { ...leaderboard, window: '30d', league: 'nfl', items: [] },
    });

    expect(await screen.findByRole('radio', { name: 'Period: Last 90 days' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'League: All leagues' })).toBeChecked();
    await fireEvent.press(screen.getByRole('radio', { name: 'Period: Last 30 days' }));
    await fireEvent.press(await screen.findByRole('radio', { name: 'League: NFL' }));

    expect(await screen.findByText('Nobody is ranked yet')).toBeOnTheScreen();
    expect(sent().at(-1)?.path).toBe('/v1/community/leaderboard?league=nfl&window=30d');
    expect(sent().at(-1)?.headers.authorization).toBe('Bearer token-1');
    expect(screen.getByRole('radio', { name: 'Period: All time' })).not.toBeChecked();
  });

  it('has an empty state that says who gets ranked, with the caveat still above it', async () => {
    await show({ [BOARD]: { ...leaderboard, items: [] } });

    expect(await screen.findByText('Nobody is ranked yet')).toBeOnTheScreen();
    expect(screen.getByText('Only profiles with at least 30 graded picks in this period are ranked. Try a longer period or another league.')).toBeOnTheScreen();
    expect(screen.getByText(leaderboard.caveat)).toBeOnTheScreen();
  });

  it('offers a retry when it does not load', async () => {
    const { serve } = await show({ [BOARD]: () => errorResponse(500, 'server_error', 'Something went wrong on our side.') });

    expect(await screen.findByText('Something went wrong on our side.')).toBeOnTheScreen();
    serve({ 'GET /v1/leagues': leagues, [BOARD]: leaderboard });
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('@fictional_fox')).toBeOnTheScreen();
  });
});
