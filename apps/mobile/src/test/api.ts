/** Test helpers for the API client: a fake `fetch` and readable views of what was sent to it. */
export function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

export function errorResponse(status: number, code: string, message: string, details?: unknown) {
  return jsonResponse({ error: details === undefined ? { code, message } : { code, message, details } }, status);
}

export type SentRequest = { method: string; path: string; headers: Record<string, string>; body: unknown };

export function installFetch() {
  const fetchMock = jest.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  const sent = (): SentRequest[] =>
    fetchMock.mock.calls.map(([url, init]) => ({
      method: init.method,
      path: String(url).replace('http://localhost:8000', ''),
      headers: init.headers,
      body: init.body === undefined ? undefined : JSON.parse(init.body),
    }));
  return { fetchMock, sent };
}

/**
 * Answers requests by "METHOD /path" (query string included). A value is sent as a 200 JSON body; a function
 * returns the response itself, so a test can answer with an error or change the answer between calls.
 * A request with no entry rejects, which the client reports as the data service being unreachable.
 */
export function serveRoutes(fetchMock: jest.Mock, routes: Record<string, unknown>) {
  fetchMock.mockImplementation(async (url: string, init: { method: string }) => {
    const key = `${init.method} ${String(url).replace('http://localhost:8000', '')}`;
    if (!(key in routes)) throw new Error(`Unexpected request: ${key}`);
    const route = routes[key];
    return typeof route === 'function' ? route() : jsonResponse(route);
  });
}
