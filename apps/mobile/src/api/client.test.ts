import {
  API_URL,
  ApiError,
  ApiUnavailableError,
  apiGet,
  apiRequest,
  askAssistant,
  deleteBet,
  describeError,
  getBets,
  setAuthToken,
  setUnauthorizedHandler,
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

describe('signed-in requests', () => {
  afterEach(() => {
    setAuthToken(null);
    setUnauthorizedHandler(null);
  });

  it('sends the bearer token on the user\'s own data and never on public data', async () => {
    setAuthToken('token-1');
    fetchMock.mockResolvedValue(jsonResponse([]));

    await getBets();
    await getEvents();

    expect(fetchMock.mock.calls[0][1].headers).toEqual({ accept: 'application/json', authorization: 'Bearer token-1' });
    expect(fetchMock.mock.calls[1][1].headers).toEqual({ accept: 'application/json' });
  });

  it('refuses a signed-in request without a token, before any network call', async () => {
    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);

    const error = await getBets().catch((caught: unknown) => caught);

    expect(error).toMatchObject({ name: 'ApiError', status: 401, code: 'not_logged_in' });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('sends a JSON body with its content type and defaults to POST', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    await apiRequest('/v1/quant/convert', { body: { odds: '-110', odds_format: 'american' } });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/quant/convert');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ accept: 'application/json', 'content-type': 'application/json' });
    expect(JSON.parse(init.body)).toEqual({ odds: '-110', odds_format: 'american' });
  });

  it('treats 204 as success with no body', async () => {
    setAuthToken('token-1');
    fetchMock.mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => {
        throw new SyntaxError('No content');
      },
    });

    await expect(deleteBet('bet 1')).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/v1/bets/bet%201');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
  });

  it('reports a rejected token to the session, and still throws the API error', async () => {
    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);
    setAuthToken('token-1');
    fetchMock.mockResolvedValue(jsonResponse({ error: { code: 'unauthorized', message: 'Token expired' } }, 401));

    const error = await getBets().catch((caught: unknown) => caught);

    expect(error).toMatchObject({ status: 401, code: 'unauthorized', message: 'Token expired' });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not end the session for a 401 on a request that sent no token', async () => {
    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);
    setAuthToken('token-1');
    fetchMock.mockResolvedValue(jsonResponse({ error: { code: 'invalid_credentials', message: 'Incorrect email or password' } }, 401));

    await apiRequest('/v1/auth/login', { body: { email: 'a@b.test', password: 'x' } }).catch(() => {});

    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('sends the token to the assistant only when there is one', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: 'ok' }));

    await askAssistant('What is expected value?');
    setAuthToken('token-1');
    await askAssistant('How are my bets doing?');

    expect(fetchMock.mock.calls[0][1].headers.authorization).toBeUndefined();
    expect(fetchMock.mock.calls[1][1].headers.authorization).toBe('Bearer token-1');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ message: 'How are my bets doing?' });
  });
});

describe('describeError', () => {
  it('uses the web wording for rate limits and an unreachable service', () => {
    expect(describeError(new ApiError(429, 'rate_limited', 'Rate limit exceeded'), 'fallback')).toBe(
      'Too many attempts. Wait a minute, then try again.',
    );
    expect(describeError(new ApiUnavailableError(), 'fallback')).toBe(
      "OddVex can't reach its data service right now. Try again in a moment.",
    );
  });

  it("passes the API's own message through, and falls back for anything else", () => {
    expect(describeError(new ApiError(422, 'invalid_odds', 'American odds cannot be between -100 and 100.'), 'fallback')).toBe(
      'American odds cannot be between -100 and 100.',
    );
    expect(describeError(new Error('boom'), 'The bet was not saved. Try again.')).toBe('The bet was not saved. Try again.');
  });
});
