import {
  API_URL,
  ApiError,
  ApiUnavailableError,
  apiGet,
  getEventOdds,
  getEvents,
  getMeta,
  withQuery,
} from '@/api/client';

const fetchMock = jest.fn();

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeEach(() => {
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

describe('withQuery', () => {
  it('drops empty values and encodes the rest', () => {
    expect(withQuery('/v1/events', { league: 'nfl', status: null })).toBe('/v1/events?league=nfl');
    expect(withQuery('/v1/events', { league: undefined, status: '' })).toBe('/v1/events');
    expect(withQuery('/v1/x', { q: 'a b&c' })).toBe('/v1/x?q=a%20b%26c');
  });
});

describe('apiGet', () => {
  it('defaults to the local API address', () => {
    expect(API_URL).toBe('http://localhost:8000');
  });

  it('returns the parsed body on success', async () => {
    const meta = { data_mode: 'synthetic', provider: 'synthetic', version: '0.1.0', server_time: '2026-11-15T20:00:00Z' };
    fetchMock.mockResolvedValue(jsonResponse(meta));

    await expect(getMeta()).resolves.toEqual(meta);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/meta');
    expect(init.method).toBe('GET');
    expect(init.headers).toEqual({ accept: 'application/json' });
  });

  it('builds the events and odds URLs from their filters', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await getEvents({ league: 'nba', status: 'live' });
    await getEvents({ league: null });
    await getEventOdds('evt 1', 'spread');

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      'http://localhost:8000/v1/events?league=nba&status=live',
      'http://localhost:8000/v1/events',
      'http://localhost:8000/v1/events/evt%201/odds?market=spread',
    ]);
  });

  it('turns the API error envelope into an ApiError', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: { code: 'not_found', message: 'Event not found.' } }, 404));

    const error = await apiGet('/v1/events/missing').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: 'not_found', message: 'Event not found.' });
  });

  it('falls back to a generic message when the error body is not the envelope', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token <');
      },
    });

    const error = await apiGet('/v1/meta').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, code: 'http_error', message: 'Request failed (502).' });
  });

  it('reports a network failure as the data service being unreachable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));

    const error = await apiGet('/v1/meta').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiUnavailableError);
    expect(error).not.toBeInstanceOf(ApiError);
  });

  it('reports a request that never answers as unreachable once the timeout passes', async () => {
    jest.useFakeTimers();
    try {
      fetchMock.mockImplementation(
        (_url: string, init: { signal: AbortSignal }) =>
          new Promise((_resolve, reject) => {
            init.signal.addEventListener('abort', () => reject(new Error('Aborted')));
          }),
      );
      const pending = apiGet('/v1/meta').catch((caught: unknown) => caught);
      await jest.advanceTimersByTimeAsync(8000);
      expect(await pending).toBeInstanceOf(ApiUnavailableError);
    } finally {
      jest.useRealTimers();
    }
  });

  it('passes a caller abort through instead of calling it unreachable', async () => {
    const controller = new AbortController();
    const abortError = new Error('Aborted');
    fetchMock.mockImplementation(
      (_url: string, init: { signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          init.signal.addEventListener('abort', () => reject(abortError));
        }),
    );
    const pending = apiGet('/v1/meta', { signal: controller.signal }).catch((caught: unknown) => caught);
    controller.abort();
    expect(await pending).toBe(abortError);
  });

  it('reports an unreadable success body as an ApiError', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected end of input');
      },
    });
    const error = await apiGet('/v1/meta').catch((caught: unknown) => caught);
    expect(error).toMatchObject({ name: 'ApiError', code: 'invalid_response' });
  });
});
