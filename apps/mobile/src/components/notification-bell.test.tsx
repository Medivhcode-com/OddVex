import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { AppState } from 'react-native';

import { setAuthToken } from '@/api/client';
import { bellLabel, NotificationBell } from '@/components/notification-bell';
import { installFetch, serveRoutes } from '@/test/api';
import { fakeSession, WithSession } from '@/test/session';

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => {
  setAuthToken(null);
  jest.restoreAllMocks();
});

describe('bellLabel', () => {
  it('says how many are unread, and nothing about a count at zero', () => {
    expect(bellLabel(3)).toBe('Notifications, 3 unread');
    expect(bellLabel(1)).toBe('Notifications, 1 unread');
    expect(bellLabel(0)).toBe('Notifications');
  });
});

describe('NotificationBell', () => {
  it('shows the unread count as a number and in its label, and opens Notifications', async () => {
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/notifications/unread-count': { unread_count: 3 } });
    await render(
      <WithSession value={fakeSession()}>
        <NotificationBell />
      </WithSession>,
    );

    const bell = await screen.findByRole('button', { name: 'Notifications, 3 unread' });
    expect(screen.getByText('3')).toBeOnTheScreen();
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
    await fireEvent.press(bell);
    expect(router.push).toHaveBeenCalledWith('/notifications');
  });

  it('hides the badge when nothing is unread', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/notifications/unread-count': { unread_count: 0 } });
    await render(
      <WithSession value={fakeSession()}>
        <NotificationBell />
      </WithSession>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeOnTheScreen();
    expect(screen.queryByText('0')).toBeNull();
  });

  it('asks for nothing when signed out, and still opens the screen that prompts to log in', async () => {
    const { fetchMock } = installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <NotificationBell />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Notifications' }));
    expect(router.push).toHaveBeenCalledWith('/notifications');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('reads the count again after a notification changes and when the app comes back to the foreground', async () => {
    const listen = jest.spyOn(AppState, 'addEventListener');
    const { fetchMock } = installFetch();
    let unread = 3;
    serveRoutes(fetchMock, { 'GET /v1/notifications/unread-count': () => ({ ok: true, status: 200, json: async () => ({ unread_count: unread }) }) });
    const session = fakeSession();
    const view = await render(
      <WithSession value={session}>
        <NotificationBell />
      </WithSession>,
    );
    expect(await screen.findByRole('button', { name: 'Notifications, 3 unread' })).toBeOnTheScreen();

    unread = 2;
    await view.rerender(
      <WithSession value={{ ...session, revision: { ...session.revision, notifications: 1 } }}>
        <NotificationBell />
      </WithSession>,
    );
    expect(await screen.findByRole('button', { name: 'Notifications, 2 unread' })).toBeOnTheScreen();

    unread = 0;
    const onChange = listen.mock.calls.at(-1)![1];
    await waitFor(() => onChange('active'));
    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeOnTheScreen();
    expect(screen.queryByText('2')).toBeNull();
  });
});
