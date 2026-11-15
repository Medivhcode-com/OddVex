import { fireEvent, render, screen } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import type { SyncConnection } from '@/api/types';
import { SyncPanel } from '@/components/sync-panel';
import { installFetch, jsonResponse } from '@/test/api';
import { now } from '@/test/fixtures';

const provider = { key: 'mock', name: 'Mock Sportsbook', description: '', is_mock: true, requires_credentials: false };
const connection: SyncConnection = {
  id: 'conn_1',
  provider: 'mock',
  provider_name: 'Mock Sportsbook',
  label: '',
  is_mock: true,
  status: 'active',
  bet_count: 3,
  created_at: '2026-11-15T19:00:00Z',
  last_synced_at: '2026-11-15T19:54:00Z',
};

beforeEach(() => setAuthToken('token-1'));
afterEach(() => setAuthToken(null));

describe('SyncPanel', () => {
  it('always says it is a demonstration and never asks for a sportsbook password', async () => {
    await render(<SyncPanel providers={[provider]} connections={[]} now={now} onChanged={() => {}} />);

    expect(screen.getByText('Demonstration only')).toBeOnTheScreen();
    expect(screen.getByText(/OddVex never asks for a sportsbook password\.$/)).toBeOnTheScreen();
    expect(screen.getByText('No connections yet.')).toBeOnTheScreen();
  });

  it('connects to the mock provider', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(connection, 201));
    const onChanged = jest.fn();
    await render(<SyncPanel providers={[provider]} connections={[]} now={now} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Connect Mock Sportsbook' }));

    expect(await screen.findByText('Connected to Mock Sportsbook. Choose Sync now to import its sample bets.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/sync/connections', body: { provider: 'mock' } });
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('syncs now and reports what was imported', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ status: 'succeeded', imported_count: 1, duplicate_count: 3, retryable: false }));
    await render(<SyncPanel providers={[provider]} connections={[connection]} now={now} onChanged={() => {}} />);

    expect(screen.getByText('3 synced bets. Last synced 6 min ago.')).toBeOnTheScreen();
    expect(screen.getByText('Mock')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Sync Mock Sportsbook now' }));

    expect(await screen.findByText('Sync finished. 1 new bet imported, 3 already here.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/sync/connections/conn_1/sync' });
  });

  it('reports a failed sync as a caution', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ status: 'failed', retryable: true, error_message: 'provider timed out', imported_count: 0, duplicate_count: 0 }));
    await render(<SyncPanel providers={[provider]} connections={[connection]} now={now} onChanged={() => {}} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Sync Mock Sportsbook now' }));

    expect(await screen.findByText('Sync failed and can be retried: provider timed out.')).toBeOnTheScreen();
  });

  it('disconnects and deletes the synced bets', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ deleted: true, bets_deleted: 3, bets_kept: 0 }));
    await render(<SyncPanel providers={[provider]} connections={[connection]} now={now} onChanged={() => {}} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Disconnect Mock Sportsbook and delete its bets' }));

    expect(await screen.findByText('Disconnected. 3 synced bets deleted.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'DELETE', path: '/v1/sync/connections/conn_1?delete_data=true' });
  });
});
