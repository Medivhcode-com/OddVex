import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { GameDetailScreen } from '@/screens/game-detail';
import { Watchlist } from '@/screens/games';
import { installFetch, jsonResponse } from '@/test/api';
import { liveEvent, moneyline } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const detail = { ...liveEvent, available_markets: ['moneyline', 'spread'], league_name: 'NFL', has_draw: false, players: [], as_of: moneyline.as_of, data_mode: 'synthetic' };
const watchItem = (id: string, kind: string, ref_id: string, label: string) => ({ id, kind, ref_id, label, created_at: '2026-11-15T00:00:00Z' });

function serve(fetchMock: jest.Mock, routes: Record<string, unknown>) {
  fetchMock.mockImplementation(async (url: string) => {
    const path = url.replace('http://localhost:8000', '');
    if (!(path in routes)) throw new Error(`Unexpected request to ${path}`);
    return jsonResponse(routes[path]);
  });
}

beforeEach(() => jest.mocked(router.push).mockClear());
afterEach(() => setAuthToken(null));

describe('GameDetailScreen', () => {
  it('prompts a signed-out person to log in before tracking a bet or following', async () => {
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/events/evt_1': detail, '/v1/events/evt_1/odds?market=moneyline': moneyline });
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <GameDetailScreen eventId="evt_1" />
      </WithSession>,
    );

    expect(await screen.findByText('Track a bet on this game')).toBeOnTheScreen();
    expect(screen.getByText('OddVex records the bet. It does not place it.')).toBeOnTheScreen();
    expect(screen.getByText('Log in to add this game to your tracker.')).toBeOnTheScreen();
    expect(screen.queryByLabelText('Stake ($)')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Log in to track a bet' }));
    expect(router.push).toHaveBeenCalledWith('/login');

    expect(screen.getByRole('button', { name: 'Follow this game' })).not.toBeSelected();
    await fireEvent.press(screen.getByRole('button', { name: 'Follow Harbor City Gulls' }));
    expect(router.push).toHaveBeenCalledTimes(2);
  });

  it('shows the quick-bet form and what is already followed when signed in', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serve(fetchMock, {
      '/v1/events/evt_1': detail,
      '/v1/events/evt_1/odds?market=moneyline': moneyline,
      '/v1/watchlist': { items: [watchItem('w_1', 'team', 't_away', 'Iron Valley Forge')] },
    });
    await render(
      <WithSession value={fakeSession()}>
        <GameDetailScreen eventId="evt_1" />
      </WithSession>,
    );

    expect(await screen.findByLabelText('Stake ($)')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Add to tracker' })).toBeOnTheScreen();
    expect(await screen.findByRole('button', { name: 'Following Iron Valley Forge' })).toBeSelected();
    expect(screen.getByRole('button', { name: 'Follow Harbor City Gulls' })).not.toBeSelected();
    expect(screen.getByRole('button', { name: 'Follow this game' })).not.toBeSelected();
  });

  it('offers no bet tracking on a game that is over', async () => {
    const { fetchMock } = installFetch();
    const final = { ...detail, status: 'final', status_detail: null };
    serve(fetchMock, { '/v1/events/evt_1': final, '/v1/events/evt_1/odds?market=moneyline': { ...moneyline, event: final } });
    await render(
      <WithSession value={fakeSession({ user: null })}>
        <GameDetailScreen eventId="evt_1" />
      </WithSession>,
    );

    expect(await screen.findByText('This game is over')).toBeOnTheScreen();
    await screen.findByText('No-vig consensus');
    expect(screen.queryByText('Track a bet on this game')).toBeNull();
  });
});

describe('Watchlist', () => {
  const leagues = [{ key: 'nfl' as const, name: 'NFL', sport: 'football', has_draw: false, markets: [], prop_markets: [] }];

  it('shows games for what is followed and links to followed players', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serve(fetchMock, {
      '/v1/watchlist': { items: [watchItem('w_1', 'team', 't_home', 'Harbor City Gulls'), watchItem('w_2', 'player', 'plr_1', 'Corwin Ashdown')] },
      '/v1/watchlist/events': [liveEvent],
    });
    await render(
      <WithSession value={fakeSession()}>
        <Watchlist userId="usr_1" leagues={leagues} />
      </WithSession>,
    );

    expect(screen.getByText('Your watchlist')).toBeOnTheScreen();
    expect(await screen.findByText('Live, Q3 4:12')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Corwin Ashdown, followed player' }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/player/[id]', params: { id: 'plr_1' } });
  });

  it('says what to do when nothing is followed', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/watchlist': { items: [] }, '/v1/watchlist/events': [] });
    await render(
      <WithSession value={fakeSession()}>
        <Watchlist userId="usr_1" leagues={leagues} />
      </WithSession>,
    );

    expect(await screen.findByText('Nothing followed yet')).toBeOnTheScreen();
    expect(screen.getByText('Open a game or a player and choose Follow. Their upcoming games show up here.')).toBeOnTheScreen();
  });

  it('says there are no games when only quiet teams are followed', async () => {
    setAuthToken('token-1');
    const { fetchMock } = installFetch();
    serve(fetchMock, { '/v1/watchlist': { items: [watchItem('w_1', 'team', 't_home', 'Harbor City Gulls')] }, '/v1/watchlist/events': [] });
    await render(
      <WithSession value={fakeSession()}>
        <Watchlist userId="usr_1" leagues={leagues} />
      </WithSession>,
    );

    expect(await screen.findByText('No live or upcoming games for what you follow.')).toBeOnTheScreen();
  });
});
