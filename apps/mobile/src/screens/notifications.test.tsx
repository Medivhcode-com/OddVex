import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { NotificationsScreen } from '@/screens/notifications';
import { installFetch, serveRoutes } from '@/test/api';
import { activeRule, priceNotification } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const routes = {
  'GET /v1/notifications?limit=30': { items: [priceNotification], unread_count: 1, next_before: null },
  'GET /v1/alerts': { items: [activeRule] },
};

beforeEach(() => jest.mocked(router.push).mockClear());
afterEach(() => setAuthToken(null));

describe('NotificationsScreen', () => {
  it('asks a signed-out person to log in and loads nothing', async () => {
    const { fetchMock } = installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <NotificationsScreen />
      </WithSession>,
    );

    expect(screen.getByText('Log in to see your notifications')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));
    expect(router.push).toHaveBeenCalledWith('/login');
    await fireEvent.press(screen.getByRole('button', { name: 'Create an account' }));
    expect(router.push).toHaveBeenCalledWith('/signup');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('opens on notifications and switches to the alert rules', async () => {
    setAuthToken('token-1');
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, routes);
    await render(
      <WithSession value={fakeSession()}>
        <NotificationsScreen />
      </WithSession>,
    );

    expect(screen.getByRole('radio', { name: 'Notifications' })).toBeChecked();
    expect(await screen.findByText('Price reached +120')).toBeOnTheScreen();
    expect(sent().map((request) => request.path)).toEqual(['/v1/notifications?limit=30']);

    await fireEvent.press(screen.getByRole('radio', { name: 'Alerts' }));
    expect(screen.getByRole('radio', { name: 'Alerts' })).toBeChecked();
    expect(await screen.findByText('Iron Valley Forge moneyline at +130 or higher')).toBeOnTheScreen();
    expect(screen.queryByText('Price reached +120')).toBeNull();
  });

  it('opens on the alert rules when the link asks for them', async () => {
    setAuthToken('token-1');
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, routes);
    await render(
      <WithSession value={fakeSession()}>
        <NotificationsScreen initialTab="alerts" />
      </WithSession>,
    );

    expect(await screen.findByText('Iron Valley Forge moneyline at +130 or higher')).toBeOnTheScreen();
    expect(sent().map((request) => request.path)).toEqual(['/v1/alerts']);
  });
});
