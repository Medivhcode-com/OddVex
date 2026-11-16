import { render, screen } from '@testing-library/react-native';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { AnalyticsScreen, rowDetail, streakText } from '@/screens/analytics';
import { errorResponse, installFetch, serveRoutes } from '@/test/api';
import { analytics, emptyAnalytics } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

async function mount(session = fakeSession()) {
  await render(
    <WithSession value={session}>
      <AnalyticsScreen />
    </WithSession>,
  );
}

beforeEach(() => setAuthToken('token-1'));
afterEach(() => setAuthToken(null));

describe('display helpers', () => {
  it('writes a row out in words, with signs on profit and ROI', () => {
    expect(rowDetail(analytics.by_odds_band[1])).toBe('7 bets · $175.00 staked · profit −$12.50 · ROI −7.1% · win rate 42.9%');
    expect(rowDetail(analytics.by_odds_band[0])).toBe('No settled bets');
    expect(rowDetail({ key: 'k', label: 'One', bets: 1, staked: 10, profit: 0, roi: null, win_rate: null })).toBe(
      '1 bet · $10.00 staked · profit $0.00 · ROI n/a · win rate n/a',
    );
  });

  it('describes a run neutrally', () => {
    expect(streakText({ kind: 'loss', length: 2 })).toBe('2 losses in a row');
    expect(streakText({ kind: 'win', length: 1 })).toBe('1 win');
    expect(streakText({ kind: 'none', length: 0 })).toBe('No current run');
  });
});

describe('AnalyticsScreen', () => {
  it('shows the odds bands, weekdays and months with their values as text', async () => {
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': analytics });
    await mount();

    expect(await screen.findByText('By odds')).toBeOnTheScreen();
    for (const band of ['-200 or shorter', '-199 to -110', '-109 to +100', '+101 to +200', 'Longer than +200']) {
      expect(screen.getByText(band)).toBeOnTheScreen();
    }
    expect(screen.getByLabelText('-199 to -110: 7 bets · $175.00 staked · profit −$12.50 · ROI −7.1% · win rate 42.9%')).toBeOnTheScreen();
    expect(screen.getByLabelText('+101 to +200: 2 bets · $40.00 staked · profit +$24.00 · ROI +60.0% · win rate 50.0%')).toBeOnTheScreen();
    expect(screen.getByLabelText('-200 or shorter: No settled bets')).toBeOnTheScreen();

    expect(screen.getByText('Sunday')).toBeOnTheScreen();
    expect(screen.getByLabelText('Thursday: 4 bets · $100.00 staked · profit −$18.00 · ROI −18.0% · win rate 25.0%')).toBeOnTheScreen();
    expect(screen.getByText('November 2026')).toBeOnTheScreen();
    expect(screen.getByLabelText(/^October 2026: 5 bets/)).toBeOnTheScreen();

    expect(screen.getByLabelText('Average stake, $24.17')).toBeOnTheScreen();
    expect(screen.getByLabelText("Average odds, −104, Mean of the bets' decimal odds")).toBeOnTheScreen();

    expect(screen.getByLabelText('Average, +1.3%, From 6 bets')).toBeOnTheScreen();
    expect(screen.getByLabelText('Share above the close, 66.7%, Bets with a value above 0')).toBeOnTheScreen();
    expect(screen.getByLabelText('0% to 2%: 3 bets')).toBeOnTheScreen();
    expect(screen.getByLabelText('Under $25: 8 bets · $150.00 staked')).toBeOnTheScreen();

    expect(screen.getByText(analytics.note)).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'GET', path: '/v1/bets/analytics' });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
  });

  it('shows the sample note as a caution when the API sends one', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': analytics });
    await mount();

    expect(await screen.findByText('Only 12 settled bets. Results from a sample this small are mostly noise.')).toBeOnTheScreen();
    expect(screen.getByText('Small sample')).toBeOnTheScreen();
    expect(screen.getByRole('alert')).toBeOnTheScreen();
  });

  it('leaves the caution out when there is no sample note', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': { ...analytics, settled_count: 40, sample_note: null } });
    await mount();

    expect(await screen.findByText('By odds')).toBeOnTheScreen();
    expect(screen.queryByText('Small sample')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows runs in plain words, and the streak note only when the API sends it', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': analytics });
    const first = await render(
      <WithSession value={fakeSession()}>
        <AnalyticsScreen />
      </WithSession>,
    );

    expect(await screen.findByLabelText('Current run, 2 losses in a row')).toBeOnTheScreen();
    expect(screen.getByLabelText('Longest run of wins, 3')).toBeOnTheScreen();
    expect(screen.getByLabelText('Longest run of losses, 2')).toBeOnTheScreen();
    expect(screen.queryByText(/streak/i)).toBeNull();
    await first.unmount();

    const note = 'Runs of wins and losses happen by chance. A run does not make the next result more or less likely.';
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': { ...analytics, streak_note: note } });
    await mount();
    expect(await screen.findByText(note)).toBeOnTheScreen();
  });

  it('has an empty state when nothing is settled', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': emptyAnalytics });
    await mount();

    expect(await screen.findByText('No settled bets yet')).toBeOnTheScreen();
    expect(screen.getByText('Analytics are built from settled bets only. Settle a bet in the tracker and its numbers show up here.')).toBeOnTheScreen();
    expect(screen.queryByText('By odds')).toBeNull();
  });

  it('asks a signed-out person to log in and loads nothing', async () => {
    setAuthToken(null);
    const { fetchMock } = installFetch();
    await mount(fakeSession({ user: null }));

    expect(screen.getByText('Log in to see your analytics')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('says so plainly when the feature is switched off', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/bets/analytics': () => errorResponse(404, 'feature_disabled', 'This feature is not available') });
    await mount();

    expect(await screen.findByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
  });
});
