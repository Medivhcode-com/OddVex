import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { Linking } from 'react-native';

import { setAuthToken } from '@/api/client';
import type { Bet, BetSummary } from '@/api/types';
import { NO_CHANGES } from '@/providers/session';
import { TrackerScreen } from '@/screens/tracker';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { lostSyncedBet, openBet, reminderExceeded, wonBet } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

const summary: BetSummary = {
  totals: {
    settled_count: 2,
    pending_count: 1,
    pending_exposure: 25,
    staked: 50,
    profit: -2.27,
    roi: -0.0454,
    wins: 1,
    losses: 1,
    pushes: 0,
    avg_clv: 0.0125,
    clv_sample: 1,
  },
  by_sport: [],
  by_market: [],
  by_sportsbook: [],
  by_bet_type: [],
  timeline: [],
  note: '',
};

const OPEN = '/v1/bets?status=pending&limit=1000';
const settledPage = (offset: number, limit = 50) => `/v1/bets?status=settled&limit=${limit}&offset=${offset}`;
const HELP_LINE = '21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738).';
const CALL = 'Call the National Problem Gambling Helpline, 1-800-697-3738';

/** Settled bets numbered from the most recently placed: "Settled pick 1" is the newest. */
function settledBets(count: number): Bet[] {
  return Array.from({ length: count }, (_, index) => ({
    ...wonBet,
    id: `settled_${index + 1}`,
    legs: [{ ...wonBet.legs[0], id: `leg_settled_${index + 1}`, selection: `Settled pick ${index + 1}` }],
  }));
}
const withSettled = (count: number): BetSummary => ({ ...summary, totals: { ...summary.totals, settled_count: count } });

function serve(fetchMock: jest.Mock, overrides: Record<string, () => unknown> = {}) {
  const routes: Record<string, () => unknown> = {
    '/v1/bets/summary': () => jsonResponse(summary),
    [OPEN]: () => jsonResponse([openBet]),
    [settledPage(0)]: () => jsonResponse([wonBet, lostSyncedBet]),
    '/v1/leagues': () => jsonResponse([{ key: 'nfl', name: 'NFL' }]),
    '/v1/sync/providers': () => jsonResponse([{ key: 'mock', name: 'Mock Sportsbook', description: '', is_mock: true, requires_credentials: false }]),
    '/v1/sync/connections': () => jsonResponse([]),
    ...overrides,
  };
  fetchMock.mockImplementation(async (url: string) => {
    const path = url.replace('http://localhost:8000', '');
    const route = routes[path];
    if (!route) throw new Error(`Unexpected request to ${path}`);
    return route();
  });
}

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  // One shared mock for the whole file (the React Native Jest preset), which `restoreAllMocks` does not empty.
  jest.mocked(Linking.openURL).mockReset();
  setAuthToken('token-1');
});
afterEach(() => {
  setAuthToken(null);
  jest.restoreAllMocks();
});

describe('TrackerScreen', () => {
  it('invites a signed-out person to log in and loads nothing', async () => {
    const { fetchMock } = installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(screen.getByText('Log in to track your bets')).toBeOnTheScreen();
    expect(screen.getByText('Your bets are private to your account. You can delete them, and your account, at any time.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));
    expect(router.push).toHaveBeenCalledWith('/login');
    await fireEvent.press(screen.getByRole('button', { name: 'Create an account' }));
    expect(router.push).toHaveBeenCalledWith('/signup');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(HELP_LINE)).toBeOnTheScreen();
    expect(screen.getByRole('link', { name: CALL })).toBeOnTheScreen();
  });

  it('carries the helpline while the saved session is still being checked at launch', async () => {
    installFetch();
    await render(
      <WithSession value={fakeSession({ status: 'loading', user: null })}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(screen.getByLabelText('Checking your account')).toBeOnTheScreen();
    expect(screen.getByText(HELP_LINE)).toBeOnTheScreen();
    expect(screen.getByRole('link', { name: CALL })).toBeOnTheScreen();
  });

  it('carries the helpline as a phone link, on the screen and in the sync panel', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(undefined);
    const { fetchMock } = installFetch();
    serve(fetchMock);
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(await screen.findByRole('button', { name: 'Connect Mock Sportsbook' })).toBeOnTheScreen();
    expect(screen.getAllByText(HELP_LINE)).toHaveLength(2);
    const links = screen.getAllByRole('link', { name: CALL });
    expect(links).toHaveLength(2);
    await fireEvent.press(links[0]);
    expect(openURL).toHaveBeenCalledWith('tel:+18006973738');
  });

  it('links to Analytics only while its flag is on', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock);
    const off = await render(
      <WithFlags flags={{ tracker_analytics: false }}>
        <WithSession value={fakeSession()}>
          <TrackerScreen />
        </WithSession>
      </WithFlags>,
    );
    expect(await screen.findByRole('button', { name: 'Log a bet' })).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Open analytics' })).toBeNull();
    await off.unmount();

    await render(
      <WithFlags flags={{ tracker_analytics: true }}>
        <WithSession value={fakeSession()}>
          <TrackerScreen />
        </WithSession>
      </WithFlags>,
    );
    await fireEvent.press(await screen.findByRole('button', { name: 'Open analytics' }));
    expect(router.push).toHaveBeenCalledWith('/analytics');
  });

  it('shows the performance summary and the open and settled bets', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock);
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
    expect(screen.getByLabelText('ROI, −4.5%, $50.00 staked')).toBeOnTheScreen();
    expect(screen.getByLabelText('Record, 1-1-0, Won, lost, push')).toBeOnTheScreen();
    expect(screen.getByLabelText('Closing line value, +1.3%, Average, where a closing price was recorded')).toBeOnTheScreen();
    expect(screen.getByLabelText('Open bets, 1, $25.00 at risk')).toBeOnTheScreen();
    expect(screen.getByText('2 settled bets')).toBeOnTheScreen();
    expect(screen.getByText('1 open')).toBeOnTheScreen();
    expect(screen.getByText('2 settled, most recently placed first')).toBeOnTheScreen();
    expect(screen.getByText('OddVex records the bet. It does not place it.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Settle from final scores' })).toBeOnTheScreen();
    expect(screen.getByText('Won')).toBeOnTheScreen();
    expect(screen.getByText('Lost')).toBeOnTheScreen();
    expect(
      screen.getByText(
        'This connects to a mock sportsbook that returns sample bets. No real sportsbook account is contacted, and OddVex never asks for a sportsbook password.',
      ),
    ).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Connect Mock Sportsbook' })).toBeOnTheScreen();
  });

  it('shows the staking reminder notice at the top once this week is at or above the amount set', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/me/stake-reminder': () => jsonResponse(reminderExceeded) });
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(await screen.findByText('You have reached your weekly staking reminder')).toBeOnTheScreen();
    expect(screen.getByText(/^You have staked \$250\.00 this week\. Your reminder is set at \$200\.00\. This is a reminder, not a limit: OddVex will not stop you logging bets\..*1-800-MY-RESET \(1-800-697-3738\)\.$/)).toBeOnTheScreen();
    // The tracker itself is unchanged: logging a bet is still offered.
    expect(await screen.findByRole('button', { name: 'Log a bet' })).toBeEnabled();
  });

  it('shows no reminder notice below the amount, or when the reminder cannot be loaded', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/me/stake-reminder': () => jsonResponse({ ...reminderExceeded, staked_this_week: 150, exceeded: false }) });
    const view = await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
    expect(screen.queryByText(/confidential help is available/)).toBeNull();
    await view.unmount();

    serve(fetchMock);
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
    expect(screen.queryByText(/confidential help is available/)).toBeNull();
  });

  it('says what to do next when there are no bets', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { [OPEN]: () => jsonResponse([]), [settledPage(0)]: () => jsonResponse([]) });
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(await screen.findByText('No open bets')).toBeOnTheScreen();
    expect(screen.getByText('Bets you log appear here until you settle them.')).toBeOnTheScreen();
    expect(screen.getByText('Settle an open bet to start building your record.')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Settle from final scores' })).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Log a bet' }));
    expect(router.push).toHaveBeenCalledWith('/log-bet');
  });

  it('says the data service cannot be reached and offers a retry', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );

    expect(await screen.findByText("OddVex can't reach its data service")).toBeOnTheScreen();
    // The helpline does not depend on anything loading.
    expect(screen.getByText(HELP_LINE)).toBeOnTheScreen();
    expect(screen.getByRole('link', { name: CALL })).toBeOnTheScreen();
    serve(fetchMock);
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
  });
});

describe('TrackerScreen with more settled bets than one page', () => {
  const all = settledBets(120);
  const pages = {
    [settledPage(0)]: () => jsonResponse(all.slice(0, 50)),
    [settledPage(50)]: () => jsonResponse(all.slice(50, 100)),
    [settledPage(100)]: () => jsonResponse(all.slice(100, 150)),
  };
  const paths = (fetchMock: jest.Mock) => fetchMock.mock.calls.map(([url]) => String(url).replace('http://localhost:8000', ''));

  async function mount(overrides: Record<string, () => unknown> = {}) {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/bets/summary': () => jsonResponse(withSettled(120)), ...pages, ...overrides });
    const view = await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByText('Settled pick 1')).toBeOnTheScreen();
    return { fetchMock, view };
  }

  it('asks for open bets on their own, and for the first page of settled bets', async () => {
    const { fetchMock } = await mount();

    expect(paths(fetchMock)).toContain(OPEN);
    expect(paths(fetchMock)).toContain(settledPage(0));
    expect(paths(fetchMock)).not.toContain('/v1/bets');
    // Both counts are the summary's, not the length of a list.
    expect(screen.getByText('1 open')).toBeOnTheScreen();
    expect(screen.getByText('Showing 50 of 120, most recently placed first')).toBeOnTheScreen();
    expect(screen.getByText('Settled pick 50')).toBeOnTheScreen();
    expect(screen.queryByText('Settled pick 51')).toBeNull();
  });

  it('reaches every older bet with "Show more", a page at a time', async () => {
    const { fetchMock } = await mount();

    await fireEvent.press(screen.getByRole('button', { name: 'Show more settled bets' }));
    expect(await screen.findByText('Settled pick 100')).toBeOnTheScreen();
    expect(paths(fetchMock)).toContain(settledPage(50));
    expect(screen.getByText('Showing 100 of 120, most recently placed first')).toBeOnTheScreen();
    expect(screen.queryByText('Settled pick 101')).toBeNull();

    await fireEvent.press(screen.getByRole('button', { name: 'Show more settled bets' }));
    expect(await screen.findByText('Settled pick 120')).toBeOnTheScreen();
    expect(paths(fetchMock)).toContain(settledPage(100));
    expect(screen.getByText('120 settled, most recently placed first')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Show more settled bets' })).toBeNull();
    // The oldest bet can be edited and deleted like any other.
    expect(screen.getByRole('button', { name: 'Edit Settled pick 120' })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Delete Settled pick 120' })).toBeOnTheScreen();
    expect(screen.getByText('Settled pick 1')).toBeOnTheScreen();
  });

  it('offers no "Show more" when the first page holds everything', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock);
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByText('2 settled, most recently placed first')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Show more settled bets' })).toBeNull();
  });

  it('keeps the older bets on screen when the list reloads after a change', async () => {
    const { fetchMock, view } = await mount({ [settledPage(0, 100)]: () => jsonResponse(all.slice(0, 100)) });
    await fireEvent.press(screen.getByRole('button', { name: 'Show more settled bets' }));
    expect(await screen.findByText('Settled pick 100')).toBeOnTheScreen();

    // What a settled, edited or deleted bet does: the session's bet counter goes up.
    await view.rerender(
      <WithSession value={fakeSession({ revision: { ...NO_CHANGES, bets: 1 } })}>
        <TrackerScreen />
      </WithSession>,
    );

    await waitFor(() => expect(paths(fetchMock)).toContain(settledPage(0, 100)));
    expect(await screen.findByText('Settled pick 100')).toBeOnTheScreen();
    expect(screen.getByText('Showing 100 of 120, most recently placed first')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Show more settled bets' })).toBeOnTheScreen();
  });

  it('offers no "Show more" when a full page is everything there is', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/bets/summary': () => jsonResponse(withSettled(50)), [settledPage(0)]: () => jsonResponse(all.slice(0, 50)) });
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByText('50 settled, most recently placed first')).toBeOnTheScreen();
    expect(screen.getByText('Settled pick 50')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Show more settled bets' })).toBeNull();
  });

  it('says when the next page could not be loaded and keeps what is on screen', async () => {
    let fail = true;
    await mount({
      [settledPage(50)]: () => (fail ? errorResponse(500, 'server_error', 'Something went wrong') : jsonResponse(all.slice(50, 100))),
    });

    await fireEvent.press(screen.getByRole('button', { name: 'Show more settled bets' }));
    expect(await screen.findByText('Something went wrong')).toBeOnTheScreen();
    expect(screen.getByText('Settled pick 50')).toBeOnTheScreen();
    expect(screen.getByText('Showing 50 of 120, most recently placed first')).toBeOnTheScreen();

    fail = false;
    await fireEvent.press(screen.getByRole('button', { name: 'Show more settled bets' }));
    expect(await screen.findByText('Settled pick 100')).toBeOnTheScreen();
    expect(screen.queryByText('Something went wrong')).toBeNull();
  });
});
