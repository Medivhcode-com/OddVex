import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import type { BetSummary } from '@/api/types';
import { TrackerScreen } from '@/screens/tracker';
import { installFetch, jsonResponse } from '@/test/api';
import { lostSyncedBet, openBet, reminderExceeded, wonBet } from '@/test/fixtures';
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

function serve(fetchMock: jest.Mock, overrides: Record<string, () => unknown> = {}) {
  const routes: Record<string, () => unknown> = {
    '/v1/bets/summary': () => jsonResponse(summary),
    '/v1/bets': () => jsonResponse([openBet, wonBet, lostSyncedBet]),
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
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

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
    expect(screen.getByText('2 settled, most recent first')).toBeOnTheScreen();
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
    expect(screen.getByText(/^You have staked \$250\.00 this week\. Your reminder is set at \$200\.00\. This is a reminder, not a limit: OddVex will not stop you logging bets\..*1-800-GAMBLER\.$/)).toBeOnTheScreen();
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
    expect(screen.queryByText(/1-800-GAMBLER/)).toBeNull();
    await view.unmount();

    serve(fetchMock);
    await render(
      <WithSession value={fakeSession()}>
        <TrackerScreen />
      </WithSession>,
    );
    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
    expect(screen.queryByText(/1-800-GAMBLER/)).toBeNull();
  });

  it('says what to do next when there are no bets', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/bets': () => jsonResponse([]) });
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
    serve(fetchMock);
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText('Profit, −$2.27')).toBeOnTheScreen();
  });
});
