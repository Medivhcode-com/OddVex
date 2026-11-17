import { render, screen } from '@testing-library/react-native';

import { SyntheticBadge } from '@/components/synthetic-badge';
import { MetaProvider } from '@/providers/meta';
import { installFetch, serveRoutes } from '@/test/api';

const base = { provider: 'synthetic', version: '0.1.0', server_time: '2026-01-10T18:00:00Z', notice: 'Notice.' };

async function renderWithMeta(meta: Record<string, unknown>) {
  const { fetchMock } = installFetch();
  serveRoutes(fetchMock, { 'GET /v1/meta': meta });
  await render(
    <MetaProvider>
      <SyntheticBadge />
    </MetaProvider>,
  );
}

describe('SyntheticBadge', () => {
  it('labels synthetic data', async () => {
    await renderWithMeta({ ...base, data_mode: 'synthetic' });
    expect(await screen.findByText('Synthetic data')).toBeOnTheScreen();
    expect(screen.getByLabelText('Synthetic data. Teams, players and sportsbooks are fictional.')).toBeOnTheScreen();
  });

  it('labels a replay of past games and says prices are simulated', async () => {
    await renderWithMeta({ ...base, provider: 'replay', data_mode: 'replay', attribution: 'Credit.' });
    expect(await screen.findByText('Replay')).toBeOnTheScreen();
    expect(screen.getByLabelText('Replay of past games. Sportsbooks and prices are simulated.')).toBeOnTheScreen();
    expect(screen.queryByText('Synthetic data')).not.toBeOnTheScreen();
  });
});
