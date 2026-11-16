import { act, render, screen, waitFor } from '@testing-library/react-native';
import { AppState, Text } from 'react-native';

import { setAuthToken } from '@/api/client';
import { flagOn, FlagsProvider, useFlags } from '@/providers/flags';
import { LoginScreen } from '@/screens/auth';
import { GamesScreen } from '@/screens/games';
import { ToolsScreen } from '@/screens/tools';
import { TrackerScreen } from '@/screens/tracker';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { flagsAllOn, unverifiedUser, user } from '@/test/fixtures';
import { WithFlags } from '@/test/flags';
import { fakeSession, WithSession } from '@/test/session';

function Probe() {
  const flags = useFlags();
  return (
    <Text>
      {flags.status}|value:{String(flags.isOn('value_screen'))}|analytics:{String(flags.isOn('tracker_analytics'))}|email:
      {String(flags.isOn('email_flows'))}
    </Text>
  );
}

const flagCalls = (fetchMock: jest.Mock) => fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/v1/flags')).length;

afterEach(() => {
  setAuthToken(null);
  jest.restoreAllMocks();
});

describe('flagOn', () => {
  it('is off for a flag the API did not list and when nothing was loaded', () => {
    expect(flagOn({ value_screen: true }, 'value_screen')).toBe(true);
    expect(flagOn({ value_screen: false }, 'value_screen')).toBe(false);
    expect(flagOn({ community: true }, 'tracker_analytics')).toBe(false);
    expect(flagOn(undefined, 'email_flows')).toBe(false);
  });
});

describe('FlagsProvider', () => {
  it('reads the flags once at start and answers from them', async () => {
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/flags': { flags: { ...flagsAllOn, tracker_analytics: false } } });
    await render(
      <FlagsProvider>
        <Probe />
      </FlagsProvider>,
    );

    expect(await screen.findByText('ready|value:true|analytics:false|email:true')).toBeOnTheScreen();
    expect(flagCalls(fetchMock)).toBe(1);
    expect(sent()[0].headers.authorization).toBeUndefined();
  });

  it('turns every flagged feature off when the flags call fails', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(
      <FlagsProvider>
        <Probe />
      </FlagsProvider>,
    );

    expect(await screen.findByText('error|value:false|analytics:false|email:false')).toBeOnTheScreen();
  });

  it('reads them again when the app returns to the foreground, and keeps the last flags if that read fails', async () => {
    const listen = jest.spyOn(AppState, 'addEventListener');
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse({ flags: flagsAllOn }));
    await render(
      <FlagsProvider>
        <Probe />
      </FlagsProvider>,
    );
    expect(await screen.findByText('ready|value:true|analytics:true|email:true')).toBeOnTheScreen();

    fetchMock.mockResolvedValueOnce(errorResponse(500, 'server_error', 'Something went wrong'));
    const onChange = listen.mock.calls[listen.mock.calls.length - 1][1];
    await act(async () => onChange('active'));
    await waitFor(() => expect(flagCalls(fetchMock)).toBe(2));
    expect(screen.getByText('ready|value:true|analytics:true|email:true')).toBeOnTheScreen();

    fetchMock.mockResolvedValueOnce(jsonResponse({ flags: { ...flagsAllOn, value_screen: false } }));
    await act(async () => onChange('active'));
    expect(await screen.findByText('ready|value:false|analytics:true|email:true')).toBeOnTheScreen();
    await act(async () => onChange('background'));
    expect(flagCalls(fetchMock)).toBe(3);
  });

  it('reads them again after a sign-in, not after a sign-out', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ flags: flagsAllOn }));
    const tree = (session: ReturnType<typeof fakeSession>) => (
      <WithSession value={session}>
        <FlagsProvider>
          <Probe />
        </FlagsProvider>
      </WithSession>
    );
    const view = await render(tree(fakeSession({ user: null })));
    await screen.findByText(/^ready/);
    expect(flagCalls(fetchMock)).toBe(1);

    await view.rerender(tree(fakeSession({ user })));
    await waitFor(() => expect(flagCalls(fetchMock)).toBe(2));

    await view.rerender(tree(fakeSession({ user: null })));
    await view.rerender(tree(fakeSession({ user: unverifiedUser })));
    await waitFor(() => expect(flagCalls(fetchMock)).toBe(3));
  });
});

describe('entry points', () => {
  it('hides the value screen on Tools and Games, analytics on the Tracker and the reset link on Log in while their flags are off', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    const off = { ...flagsAllOn, value_screen: false, tracker_analytics: false, email_flows: false };

    const tools = await render(
      <WithFlags flags={off}>
        <ToolsScreen />
      </WithFlags>,
    );
    expect(screen.getByRole('button', { name: 'Open parlay research' })).toBeOnTheScreen();
    expect(screen.queryByText('Value screen')).toBeNull();
    await tools.unmount();

    const games = await render(
      <WithFlags flags={off}>
        <WithSession value={fakeSession({ user: null })}>
          <GamesScreen />
        </WithSession>
      </WithFlags>,
    );
    expect(screen.getByText('Ask OddVex AI')).toBeOnTheScreen();
    expect(screen.queryByText('Value screen')).toBeNull();
    await games.unmount();

    const login = await render(
      <WithFlags flags={off}>
        <WithSession value={fakeSession({ user: null })}>
          <LoginScreen />
        </WithSession>
      </WithFlags>,
    );
    expect(screen.queryByRole('button', { name: 'Forgot password?' })).toBeNull();
    await login.unmount();
  });

  it('shows them while the flags are on', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));

    const tools = await render(
      <WithFlags flags={flagsAllOn}>
        <ToolsScreen />
      </WithFlags>,
    );
    expect(screen.getByRole('button', { name: 'Open value screen' })).toBeOnTheScreen();
    await tools.unmount();

    const games = await render(
      <WithFlags flags={flagsAllOn}>
        <WithSession value={fakeSession({ user: null })}>
          <GamesScreen />
        </WithSession>
      </WithFlags>,
    );
    expect(screen.getByRole('link', { name: 'Value screen: best prices against the consensus of other books' })).toBeOnTheScreen();
    await games.unmount();

    await render(
      <WithFlags flags={flagsAllOn}>
        <WithSession value={fakeSession({ user: null })}>
          <LoginScreen />
        </WithSession>
      </WithFlags>,
    );
    expect(screen.getByRole('button', { name: 'Forgot password?' })).toBeOnTheScreen();
  });

  it('offers nothing flagged when no flags have loaded', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <TrackerScreen />
        <ToolsScreen />
      </WithSession>,
    );
    expect(screen.queryByText('Value screen')).toBeNull();
    expect(screen.queryByText('Analytics')).toBeNull();
  });
});
