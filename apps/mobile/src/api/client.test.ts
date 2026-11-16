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
import * as client from '@/api/client';

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

describe('alerts and notifications', () => {
  const calls = () =>
    fetchMock.mock.calls.map(([url, init]) => ({
      method: init.method,
      path: String(url).replace(client.API_URL, ''),
      auth: init.headers.authorization,
      body: init.body === undefined ? undefined : JSON.parse(init.body),
    }));

  beforeEach(() => setAuthToken('token-1'));
  afterEach(() => setAuthToken(null));

  it('refuses every one of them without a token, before any request', async () => {
    setAuthToken(null);
    for (const call of [
      () => client.getAlerts(),
      () => client.evaluateAlerts(),
      () => client.getNotifications(),
      () => client.getUnreadCount(),
      () => client.markAllNotificationsRead(),
      () => client.getNotificationPreferences(),
      () => client.setStakeReminder(100),
    ]) {
      await expect(call()).rejects.toMatchObject({ status: 401, code: 'not_logged_in' });
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('unwraps the alert list and the unread count, and builds the notification query', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ items: [{ id: 'alr_1' }] }))
      .mockResolvedValueOnce(jsonResponse({ unread_count: 3 }))
      .mockResolvedValue(jsonResponse({ items: [], unread_count: 0, next_before: null }));

    await expect(client.getAlerts('active')).resolves.toEqual([{ id: 'alr_1' }]);
    await expect(client.getUnreadCount()).resolves.toBe(3);
    await client.getNotifications();
    await client.getNotifications({ unread: true, limit: 30, before: 'abc/1' });

    expect(calls().map(({ method, path, auth }) => `${method} ${path} ${auth}`)).toEqual([
      'GET /v1/alerts?state=active Bearer token-1',
      'GET /v1/notifications/unread-count Bearer token-1',
      'GET /v1/notifications Bearer token-1',
      'GET /v1/notifications?unread=true&limit=30&before=abc%2F1 Bearer token-1',
    ]);
  });

  it('uses the method and body each write needs', async () => {
    fetchMock.mockImplementation(async (_url: string, init: { method: string }) =>
      init.method === 'DELETE' ? { ok: true, status: 204, json: async () => undefined } : jsonResponse({}),
    );

    await client.createAlert({ kind: 'game_final', event_id: 'evt_1' });
    await client.updateAlert('alr_1', 'paused');
    await client.deleteAlert('alr 1');
    await client.evaluateAlerts();
    await client.markNotificationRead('ntf_1');
    await client.markAllNotificationsRead();
    await client.deleteNotification('ntf_1');
    await client.updateNotificationPreferences({ in_app: { line_move: false } });
    await client.setStakeReminder(250);
    await client.setStakeReminder(null);

    expect(calls().map(({ method, path, body }) => [`${method} ${path}`, body])).toEqual([
      ['POST /v1/alerts', { kind: 'game_final', event_id: 'evt_1' }],
      ['PATCH /v1/alerts/alr_1', { state: 'paused' }],
      ['DELETE /v1/alerts/alr%201', undefined],
      ['POST /v1/alerts/evaluate', {}],
      ['POST /v1/notifications/ntf_1/read', {}],
      ['POST /v1/notifications/read-all', {}],
      ['DELETE /v1/notifications/ntf_1', undefined],
      ['PUT /v1/me/notification-preferences', { in_app: { line_move: false } }],
      ['PUT /v1/me/stake-reminder', { weekly_stake_threshold: 250 }],
      ['PUT /v1/me/stake-reminder', { weekly_stake_threshold: null }],
    ]);
  });
});

describe('flags, value screen, analytics and account flows', () => {
  const sent = () =>
    fetchMock.mock.calls.map(([url, init]) => ({
      method: init.method as string,
      path: String(url).replace(client.API_URL, ''),
      headers: init.headers as Record<string, string>,
      body: init.body === undefined ? undefined : (JSON.parse(init.body) as unknown),
    }));

  afterEach(() => setAuthToken(null));

  it('unwraps the flags and sends no token', async () => {
    setAuthToken('token-1');
    fetchMock.mockResolvedValue(jsonResponse({ flags: { value_screen: true, community: false } }));

    await expect(client.getFlags()).resolves.toEqual({ value_screen: true, community: false });
    expect(sent()[0]).toMatchObject({ method: 'GET', path: '/v1/flags' });
    expect(sent()[0].headers.authorization).toBeUndefined();
  });

  it('builds the value screen query and leaves out filters that are not set', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ rows: [] }));

    await client.getValueScreen();
    await client.getValueScreen({ league: 'nba', market: 'total', minEdge: 0.02 });
    await client.getValueScreen({ league: null, market: null, minEdge: 0 });

    expect(sent().map((request) => request.path)).toEqual(['/v1/value', '/v1/value?league=nba&market=total&min_edge=0.02', '/v1/value']);
  });

  it('sends the token for analytics, entitlements and a verification request, and not for the link flows', async () => {
    setAuthToken('token-1');
    fetchMock.mockResolvedValue(jsonResponse({ message: 'ok' }, 202));

    await client.getBetAnalytics();
    await client.getEntitlements();
    await client.requestEmailVerification();
    await client.confirmEmailVerification('tok_0123456789abcdef');
    await client.requestPasswordReset('sam@example.test');
    fetchMock.mockResolvedValue({ ok: true, status: 204, json: async () => undefined });
    await expect(client.confirmPasswordReset('tok_0123456789abcdef', 'a much newer password')).resolves.toBeUndefined();

    expect(sent().map((request) => [request.method, request.path, request.headers.authorization, request.body])).toEqual([
      ['GET', '/v1/bets/analytics', 'Bearer token-1', undefined],
      ['GET', '/v1/me/entitlements', 'Bearer token-1', undefined],
      ['POST', '/v1/auth/verify-email/request', 'Bearer token-1', {}],
      ['POST', '/v1/auth/verify-email/confirm', undefined, { token: 'tok_0123456789abcdef' }],
      ['POST', '/v1/auth/password-reset/request', undefined, { email: 'sam@example.test' }],
      ['POST', '/v1/auth/password-reset/confirm', undefined, { token: 'tok_0123456789abcdef', new_password: 'a much newer password' }],
    ]);
  });

  it('tells a switched-off feature and a suspended account apart from other errors', async () => {
    const disabled = new client.ApiError(404, 'feature_disabled', 'This feature is not available');
    expect(client.isFeatureDisabled(disabled)).toBe(true);
    expect(client.isFeatureDisabled(new client.ApiError(404, 'not_found', 'Event not found'))).toBe(false);
    expect(client.describeError(disabled, 'fallback')).toBe("This feature isn't available right now.");

    expect(client.isAccountSuspended(new client.ApiError(401, 'account_suspended', 'This account is suspended'))).toBe(true);
    expect(client.isAccountSuspended(new client.ApiError(403, 'account_suspended', 'x'))).toBe(true);
    expect(client.isAccountSuspended(new client.ApiError(401, 'invalid_token', 'x'))).toBe(false);
  });

  it('hands the reason to the session when a token is rejected', async () => {
    setAuthToken('token-1');
    const onUnauthorized = jest.fn();
    client.setUnauthorizedHandler(onUnauthorized);
    fetchMock.mockResolvedValue(jsonResponse({ error: { code: 'account_suspended', message: 'This account is suspended' } }, 401));

    await expect(client.getBetAnalytics()).rejects.toMatchObject({ status: 401, code: 'account_suspended' });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(client.isAccountSuspended(onUnauthorized.mock.calls[0][0])).toBe(true);
    client.setUnauthorizedHandler(null);
  });
});
