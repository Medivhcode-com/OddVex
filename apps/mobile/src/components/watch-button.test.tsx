import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { WatchButton } from '@/components/watch-button';
import { watchId } from '@/hooks/use-watchlist';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { fakeSession, WithSession } from '@/test/session';

beforeEach(() => {
  setAuthToken('token-1');
  jest.mocked(router.push).mockClear();
});
afterEach(() => setAuthToken(null));

describe('WatchButton', () => {
  it('says "Follow" and is not selected when the team is not followed', async () => {
    await render(
      <WithSession value={fakeSession()}>
        <WatchButton kind="team" refId="t_home" name="Harbor City Gulls" itemId={null} />
      </WithSession>,
    );

    const button = screen.getByRole('button', { name: 'Follow Harbor City Gulls' });
    expect(button).not.toBeSelected();
    expect(screen.getByText('☆', { includeHiddenElements: true })).toBeOnTheScreen();
  });

  it('says "Following" and is selected when it is', async () => {
    await render(
      <WithSession value={fakeSession()}>
        <WatchButton kind="team" refId="t_home" name="Harbor City Gulls" itemId="w_1" />
      </WithSession>,
    );

    expect(screen.getByRole('button', { name: 'Following Harbor City Gulls' })).toBeSelected();
    expect(screen.getByText('★', { includeHiddenElements: true })).toBeOnTheScreen();
  });

  it('follows through the API and tells the app the watchlist changed', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ id: 'w_1', kind: 'player', ref_id: 'plr_1', label: 'Corwin Ashdown' }, 201));
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <WatchButton kind="player" refId="plr_1" name="Corwin Ashdown" itemId={null} />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Follow Corwin Ashdown' }));

    await waitFor(() => expect(session.changed).toHaveBeenCalledWith('watchlist'));
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/watchlist', body: { kind: 'player', ref_id: 'plr_1' } });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
  });

  it('unfollows by deleting the watchlist item', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue({ ok: true, status: 204, json: async () => null });
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <WatchButton kind="event" refId="evt_1" name="this game" itemId="w_9" />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Following this game' }));

    await waitFor(() => expect(session.changed).toHaveBeenCalledWith('watchlist'));
    expect(sent()[0]).toMatchObject({ method: 'DELETE', path: '/v1/watchlist/w_9' });
  });

  it('sends a signed-out person to log in instead of calling the API', async () => {
    const { fetchMock } = installFetch();
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <WatchButton kind="team" refId="t_home" name="Harbor City Gulls" itemId={null} />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Follow Harbor City Gulls' }));

    expect(router.push).toHaveBeenCalledWith('/login');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('announces a failure and leaves the state as it was', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(404, 'not_found', 'That team is not available.'));
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <WatchButton kind="team" refId="t_gone" name="Harbor City Gulls" itemId={null} />
      </WithSession>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Follow Harbor City Gulls' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That team is not available.');
    expect(session.changed).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Follow Harbor City Gulls' })).not.toBeSelected();
  });
});

describe('watchId', () => {
  it('finds the item for a kind and id, and nothing otherwise', () => {
    const items = [
      { id: 'w_1', kind: 'team' as const, ref_id: 't_home', label: 'Harbor City Gulls', available: true, created_at: '2026-11-15T00:00:00Z' },
      { id: 'w_2', kind: 'event' as const, ref_id: 'evt_1', label: 'Forge at Gulls', available: true, created_at: '2026-11-15T00:00:00Z' },
    ];
    expect(watchId(items, 'team', 't_home')).toBe('w_1');
    expect(watchId(items, 'event', 'evt_1')).toBe('w_2');
    expect(watchId(items, 'player', 't_home')).toBeNull();
    expect(watchId(undefined, 'team', 't_home')).toBeNull();
  });
});
