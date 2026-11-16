/** Browser-side calls go through the same-origin bridge at /api/ov. */
export class ClientApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    /** The API's `error.details`, when it sent any (for example the content rule that matched). */
    public details?: unknown,
  ) {
    super(message);
  }
}

export async function clientApi<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/ov${path}`, {
      method: options.method ?? (options.body === undefined ? "GET" : "POST"),
      headers: options.body === undefined ? undefined : { "content-type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ClientApiError(0, "network", "You appear to be offline. Check your connection and try again.");
  }
  if (response.status === 204) return undefined as T;
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {}
  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ClientApiError(response.status, error?.code ?? "http_error", error?.message ?? `Request failed (${response.status}).`, error?.details);
  }
  return payload as T;
}
