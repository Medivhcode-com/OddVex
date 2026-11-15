/** Test helpers for the API client: a fake `fetch` and readable views of what was sent to it. */
export function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

export function errorResponse(status: number, code: string, message: string) {
  return jsonResponse({ error: { code, message } }, status);
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
