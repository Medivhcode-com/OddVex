import { fireEvent, render, screen } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import { SettingsScreen } from '@/screens/settings';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { PREVIEW_EMAIL_NOTE } from '@/components/account-forms';
import { flagsAllOn, reminderExceeded, unverifiedUser, user } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

const preferences = {
  in_app: {
    price_alert: true,
    line_move: true,
    game_start: true,
    game_final: true,
    bet_settled: true,
    sync_finished: true,
    stake_reminder: true,
    new_follower: true,
    pick_comment: true,
    pick_graded: true,
  },
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

  it('adds the three community switches while the community flag is on', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/me/notification-preferences': preferences, 'GET /v1/me/stake-reminder': reminderExceeded });
    await render(
      <WithFlags flags={{ community: true }}>
        <WithSession value={fakeSession()}>
          <SettingsScreen />
        </WithSession>
      </WithFlags>,
    );

    for (const label of ['New followers', 'Comments on your picks', 'Graded picks']) {
      expect(await screen.findByRole('switch', { name: label })).toBeChecked();
    }
    expect(screen.getAllByRole('switch')).toHaveLength(10);
  });

  it('logs out through the session and says that it ends every session for the account', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/me/notification-preferences': preferences, 'GET /v1/me/stake-reminder': reminderExceeded });
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <SettingsScreen />
      </WithSession>,
    );

    expect(screen.getByText('Logging out ends every session for this account, on every device where it is signed in.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Log out' }));
    expect(session.logOut).toHaveBeenCalledTimes(1);
    expect(session.logOut).toHaveBeenCalledWith();
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

describe('SettingsScreen account', () => {
  const base = { 'GET /v1/me/notification-preferences': preferences, 'GET /v1/me/stake-reminder': reminderExceeded };
  const entitlements = (preview: boolean) => ({
    plan: 'free',
    preview,
    features: { value_screen: { enabled: true, limit: null }, 'alerts.max_active': { enabled: true, limit: 100 } },
  });

  async function mount(session = fakeSession(), flags = flagsAllOn) {
    await render(
      <WithFlags flags={flags}>
        <WithSession value={session}>
          <SettingsScreen />
        </WithSession>
      </WithFlags>,
    );
  }

  it('shows the plan, a verified email and the preview line', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { ...base, 'GET /v1/me/entitlements': entitlements(true) });
    await mount();

    expect(screen.getByLabelText('Plan: Free')).toBeOnTheScreen();
    expect(screen.getByText('Email verified')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Send verification email' })).toBeNull();
    expect(await screen.findByText('Preview: every feature is included')).toBeOnTheScreen();
    expect(screen.queryByText(/upgrade|subscribe|buy|purchase|\$\d+ a month/i)).toBeNull();
  });

  it('leaves out the plan when the API sends none and the preview line when plans are enforced', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { ...base, 'GET /v1/me/entitlements': entitlements(false) });
    await mount(fakeSession({ user: { ...user, plan: null } }));

    expect(await screen.findByRole('switch', { name: 'Price alerts' })).toBeOnTheScreen();
    expect(screen.queryByLabelText(/^Plan:/)).toBeNull();
    expect(screen.queryByText('Preview: every feature is included')).toBeNull();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/v1/me/entitlements'))).toBe(true);
  });

  it('requests a verification email, shows the confirmation and says no email is actually sent', async () => {
    setAuthToken('token-1');
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, {
      ...base,
      'GET /v1/me/entitlements': entitlements(true),
      'POST /v1/auth/verify-email/request': () => jsonResponse({ message: 'A confirmation email has been queued for your address.' }, 202),
    });
    const session = fakeSession({ user: unverifiedUser });
    await mount(session);

    expect(screen.getByText('Email not verified')).toBeOnTheScreen();
    expect(screen.getByText(PREVIEW_EMAIL_NOTE)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Send verification email' }));

    expect(await screen.findByText('A confirmation email has been queued for your address.')).toBeOnTheScreen();
    expect(screen.getByText(PREVIEW_EMAIL_NOTE)).toBeOnTheScreen();
    const request = sent().find((item) => item.path === '/v1/auth/verify-email/request');
    expect(request).toMatchObject({ method: 'POST' });
    expect(request?.headers.authorization).toBe('Bearer token-1');
    expect(session.refreshUser).toHaveBeenCalledTimes(1);
  });

  it('uses the "Too many attempts" copy when the request is rate limited', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, {
      ...base,
      'POST /v1/auth/verify-email/request': () => errorResponse(429, 'rate_limited', 'Rate limit exceeded'),
    });
    await mount(fakeSession({ user: unverifiedUser }));

    await fireEvent.press(screen.getByRole('button', { name: 'Send verification email' }));
    expect(await screen.findByText('Too many attempts. Wait a minute, then try again.')).toBeOnTheScreen();
  });

  it('shows "not verified" without the action while email flows are off', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, base);
    await mount(fakeSession({ user: unverifiedUser }), { ...flagsAllOn, email_flows: false });

    expect(screen.getByText('Email not verified')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Send verification email' })).toBeNull();
    expect(screen.queryByText(PREVIEW_EMAIL_NOTE)).toBeNull();
  });
});
