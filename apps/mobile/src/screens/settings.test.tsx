import { render, screen } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import { SettingsScreen } from '@/screens/settings';
import { installFetch, serveRoutes } from '@/test/api';
import { reminderExceeded } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const preferences = {
  in_app: { price_alert: true, line_move: true, game_start: true, game_final: true, bet_settled: true, sync_finished: true, stake_reminder: true },
};

afterEach(() => setAuthToken(null));

describe('SettingsScreen notifications', () => {
  it('has the notification switches and the staking reminder, and says what they are not', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/me/notification-preferences': preferences, 'GET /v1/me/stake-reminder': reminderExceeded });
    await render(
      <WithSession value={fakeSession()}>
        <SettingsScreen />
      </WithSession>,
    );

    expect(screen.getByText('Notifications')).toBeOnTheScreen();
    expect(screen.getByText('Notifications appear in the app only. There is no push or email yet.')).toBeOnTheScreen();
    expect(await screen.findByRole('switch', { name: 'Price alerts' })).toBeChecked();
    expect(screen.getAllByRole('switch')).toHaveLength(7);

    expect(screen.getByText('A reminder, not a limit. OddVex will not stop you logging bets.')).toBeOnTheScreen();
    expect(await screen.findByText('You have staked $250.00 this week.')).toBeOnTheScreen();
    expect(screen.getByText('Your reminder is set at $200.00 a week.')).toBeOnTheScreen();
    expect(screen.getByText(/free, confidential help is available at 1-800-GAMBLER\.$/)).toBeOnTheScreen();
  });

  it('shows neither section signed out', async () => {
    const { fetchMock } = installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <SettingsScreen />
      </WithSession>,
    );

    expect(screen.queryByText('Weekly staking reminder')).toBeNull();
    expect(screen.queryByRole('switch')).toBeNull();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/v1/me/'))).toHaveLength(0);
  });
});
