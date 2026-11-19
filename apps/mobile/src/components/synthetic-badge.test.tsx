import { act, render, screen, waitFor } from '@testing-library/react-native';
import { AppState } from 'react-native';

import { SyntheticBadge } from '@/components/synthetic-badge';
import { META_RETRY_DELAYS_MS, MetaProvider } from '@/providers/meta';
import { installFetch, jsonResponse, serveRoutes } from '@/test/api';

const base = { provider: 'synthetic', version: '0.1.0', server_time: '2026-01-10T18:00:00Z', notice: 'Notice.' };
const synthetic = { ...base, data_mode: 'synthetic' };
const NOT_CONFIRMED = 'Data source not confirmed';
const metaCalls = (fetchMock: jest.Mock) => fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/v1/meta')).length;

async function mount() {
  await render(
    <MetaProvider>
      <SyntheticBadge />
    </MetaProvider>,
  );
}

async function renderWithMeta(meta: Record<string, unknown>) {
  const { fetchMock } = installFetch();
  serveRoutes(fetchMock, { 'GET /v1/meta': meta });
  await mount();
}

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('SyntheticBadge', () => {
  it('labels synthetic data', async () => {
    await renderWithMeta(synthetic);
    expect(await screen.findByText('Synthetic data')).toBeOnTheScreen();
    expect(screen.getByLabelText('Synthetic data. Teams, players and sportsbooks are fictional.')).toBeOnTheScreen();
    expect(screen.queryByText(NOT_CONFIRMED)).toBeNull();
  });

  it('labels a replay of past games and says prices are simulated', async () => {
    await renderWithMeta({ ...base, provider: 'replay', data_mode: 'replay', attribution: 'Credit.' });
    expect(await screen.findByText('Replay')).toBeOnTheScreen();
    expect(screen.getByLabelText('Replay of past games. Sportsbooks and prices are simulated.')).toBeOnTheScreen();
    expect(screen.queryByText('Synthetic data')).not.toBeOnTheScreen();
  });

  it('says the data source is not confirmed while the answer has not arrived', async () => {
    const { fetchMock } = installFetch();
    let answer: (response: unknown) => void = () => {};
    fetchMock.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    await mount();

    expect(screen.getByText(NOT_CONFIRMED)).toBeOnTheScreen();
    expect(screen.getByLabelText('Data source not confirmed. OddVex has not yet confirmed whether this data is synthetic.')).toBeOnTheScreen();

    await act(async () => answer(jsonResponse(synthetic)));
    expect(await screen.findByText('Synthetic data')).toBeOnTheScreen();
    expect(screen.queryByText(NOT_CONFIRMED)).toBeNull();
  });

  it('keeps saying so when the call fails, instead of showing nothing', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await mount();

    await waitFor(() => expect(metaCalls(fetchMock)).toBe(1));
    expect(await screen.findByText(NOT_CONFIRMED)).toBeOnTheScreen();
    expect(screen.queryByText('Synthetic data')).toBeNull();
  });

  it('says the data source is not confirmed when the answer carries no data mode', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/meta': base });
    await mount();

    await waitFor(() => expect(metaCalls(fetchMock)).toBe(1));
    expect(await screen.findByText(NOT_CONFIRMED)).toBeOnTheScreen();
    // Settled, not merely still loading: the badge stays.
    await act(async () => {});
    expect(screen.getByText(NOT_CONFIRMED)).toBeOnTheScreen();
  });

  it('draws nothing once the API reports a mode that needs no label', async () => {
    await renderWithMeta({ ...base, provider: 'live', data_mode: 'live' });
    await waitFor(() => expect(screen.queryByText(NOT_CONFIRMED)).toBeNull());
    expect(screen.queryByText('Synthetic data')).toBeNull();
    expect(screen.queryByText('Replay')).toBeNull();
  });
});

describe('MetaProvider', () => {
  it('asks again after a failure, waiting longer each time, until the mode is known', async () => {
    jest.useFakeTimers();
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await mount();
    await waitFor(() => expect(metaCalls(fetchMock)).toBe(1));
    expect(screen.getByText(NOT_CONFIRMED)).toBeOnTheScreen();

    await act(async () => jest.advanceTimersByTime(META_RETRY_DELAYS_MS[0] - 1));
    expect(metaCalls(fetchMock)).toBe(1);
    await act(async () => jest.advanceTimersByTime(1));
    await waitFor(() => expect(metaCalls(fetchMock)).toBe(2));

    // The second pause is longer than the first.
    await act(async () => jest.advanceTimersByTime(META_RETRY_DELAYS_MS[0]));
    expect(metaCalls(fetchMock)).toBe(2);
    expect(screen.getByText(NOT_CONFIRMED)).toBeOnTheScreen();

    fetchMock.mockResolvedValue(jsonResponse(synthetic));
    await act(async () => jest.advanceTimersByTime(META_RETRY_DELAYS_MS[1] - META_RETRY_DELAYS_MS[0]));
    expect(await screen.findByText('Synthetic data')).toBeOnTheScreen();
    expect(metaCalls(fetchMock)).toBe(3);

    // Known now: no further requests on a timer.
    await act(async () => jest.advanceTimersByTime(10 * 60_000));
    expect(metaCalls(fetchMock)).toBe(3);
  });

  it('asks again when the app returns to the foreground', async () => {
    const listen = jest.spyOn(AppState, 'addEventListener');
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await mount();
    expect(await screen.findByText(NOT_CONFIRMED)).toBeOnTheScreen();
    await waitFor(() => expect(metaCalls(fetchMock)).toBe(1));

    fetchMock.mockResolvedValue(jsonResponse(synthetic));
    const onChange = listen.mock.calls[listen.mock.calls.length - 1][1];
    await act(async () => onChange('background'));
    expect(metaCalls(fetchMock)).toBe(1);
    await act(async () => onChange('active'));

    expect(await screen.findByText('Synthetic data')).toBeOnTheScreen();
    expect(metaCalls(fetchMock)).toBe(2);
  });
});
