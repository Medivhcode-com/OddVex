import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Linking } from 'react-native';

import { setAuthToken } from '@/api/client';
import { HELPLINE, HELPLINE_ABOUT, HELPLINE_CHAT, HELPLINE_NOT_EMERGENCY, RESPONSIBLE_GAMBLING_LINE } from '@/helpline';
import { META_RETRY_DELAYS_MS, MetaProvider } from '@/providers/meta';
import { SettingsScreen } from '@/screens/settings';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { PREVIEW_EMAIL_NOTE } from '@/components/account-forms';
import { flagsAllOn, reminderExceeded, unverifiedUser, user } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';
import { screenStrings } from '@/test/strings';

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

// The React Native Jest preset makes `Linking.openURL` one shared mock for the whole file, which
// `restoreAllMocks` does not empty: its calls and its answer are cleared here so no test depends on another.
beforeEach(() => jest.mocked(Linking.openURL).mockReset());
afterEach(() => {
  setAuthToken(null);
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('SettingsScreen data source', () => {
  it('keeps saying the data service cannot be reached while it asks again, instead of going back to "Checking"', async () => {
    jest.useFakeTimers();
    const UNKNOWN = /^OddVex can.t reach its data service, so the data source is unknown\.$/;
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed'));
    await render(
      <MetaProvider>
        <WithSession value={fakeSession({ user: null })}>
          <SettingsScreen />
        </WithSession>
      </MetaProvider>,
    );
    expect(await screen.findByText(UNKNOWN)).toBeOnTheScreen();
    expect(screen.queryByText('Checking the data source.')).toBeNull();

    // The automatic second read is on its way and has not been answered.
    let answer: (response: unknown) => void = () => {};
    fetchMock.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    await act(async () => jest.advanceTimersByTime(META_RETRY_DELAYS_MS[0]));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText(UNKNOWN)).toBeOnTheScreen();
    expect(screen.queryByText('Checking the data source.')).toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeOnTheScreen();

    await act(async () => answer(jsonResponse({ provider: 'synthetic', data_mode: 'synthetic', version: '0.1.0', server_time: '2026-01-10T18:00:00Z', notice: 'Notice.' })));
    expect(await screen.findByText(/^Synthetic data — fictional teams/)).toBeOnTheScreen();
    expect(screen.queryByText(UNKNOWN)).toBeNull();
  });
});

describe('SettingsScreen responsible gambling', () => {
  it('gives the national helpline with a phone link, the text line, and where to turn in a crisis', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(undefined);
    installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <SettingsScreen />
      </WithSession>,
    );

    expect(screen.getByText('21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738).')).toBeOnTheScreen();
    expect(screen.getByText(RESPONSIBLE_GAMBLING_LINE)).toBeOnTheScreen();
    expect(screen.getByText(HELPLINE_ABOUT)).toBeOnTheScreen();
    expect(screen.getByText(HELPLINE_NOT_EMERGENCY)).toBeOnTheScreen();
    expect(screen.getByText(HELPLINE_CHAT)).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('link', { name: 'Call the National Problem Gambling Helpline, 1-800-697-3738' }));
    expect(openURL).toHaveBeenLastCalledWith('tel:+18006973738');
    expect(openURL).toHaveBeenLastCalledWith(HELPLINE.tel);

    await fireEvent.press(screen.getByRole('link', { name: 'Call 988, the Suicide and Crisis Lifeline' }));
    expect(openURL).toHaveBeenLastCalledWith('tel:988');

    await fireEvent.press(screen.getByRole('link', { name: 'Open the National Council on Problem Gambling website' }));
    expect(openURL).toHaveBeenLastCalledWith('https://www.ncpgambling.org');
    expect(openURL).toHaveBeenCalledTimes(3);

    // The helpline is described as confidential and always open, and never as the old number.
    for (const text of screenStrings()) expect(text).not.toMatch(/426-?2537|Call or text 1-800/);
  });

  it('leaves the number readable when the device cannot open the dialer', async () => {
    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('No app can open this'));
    installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <SettingsScreen />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('link', { name: 'Call the National Problem Gambling Helpline, 1-800-697-3738' }));
    expect(screen.getByText(RESPONSIBLE_GAMBLING_LINE)).toBeOnTheScreen();
  });
});

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
    expect(screen.getByText(/confidential help is available at 1-800-MY-RESET \(1-800-697-3738\)\.$/)).toBeOnTheScreen();
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
