import type { EventDetail, EventStatus, EventSummary, League, Market, Meta, OddsComparison } from '@/api/types';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '');

const TIMEOUT_MS = 8000;

/** The API answered, but with an error. `code` and `message` come from its `{error:{code,message}}` envelope. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** The API could not be reached at all: no network, wrong address, or no answer in time. */
export class ApiUnavailableError extends Error {
  constructor() {
    super('The OddVex data service is not reachable.');
    this.name = 'ApiUnavailableError';
  }
}

type Query = Record<string, string | number | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const parts: string[] = [];
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return parts.length ? `${path}?${parts.join('&')}` : path;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = 'http_error';
  let message = `Request failed (${response.status}).`;
  try {
    const body = await response.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    // Not JSON. Keep the generic message.
  }
  return new ApiError(response.status, code, message);
}

/**
 * GET a JSON resource. Nothing is cached: prices are live by nature.
 * Aborting `signal` rejects with the abort error so callers can tell "cancelled" from "unreachable".
 */
export async function apiGet<T>(path: string, options: { query?: Query; signal?: AbortSignal } = {}): Promise<T> {
  const controller = new AbortController();
  const outer = options.signal;
  const forwardAbort = () => controller.abort();
  if (outer?.aborted) controller.abort();
  outer?.addEventListener('abort', forwardAbort);
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${withQuery(path, options.query)}`, {
      method: 'GET',
      headers: { accept: 'application/json' },
      signal: controller.signal,
    });
  } catch (error) {
    if (outer?.aborted) throw error;
    throw new ApiUnavailableError();
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener('abort', forwardAbort);
  }

  if (!response.ok) throw await parseError(response);
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, 'invalid_response', 'The data service sent a response the app could not read.');
  }
}

export function getMeta(signal?: AbortSignal): Promise<Meta> {
  return apiGet<Meta>('/v1/meta', { signal });
}

export function getLeagues(signal?: AbortSignal): Promise<League[]> {
  return apiGet<League[]>('/v1/leagues', { signal });
}

export function getEvents(
  filters: { league?: string | null; status?: EventStatus | null } = {},
  signal?: AbortSignal,
): Promise<EventSummary[]> {
  return apiGet<EventSummary[]>('/v1/events', { query: { league: filters.league, status: filters.status }, signal });
}

export function getEvent(id: string, signal?: AbortSignal): Promise<EventDetail> {
  return apiGet<EventDetail>(`/v1/events/${encodeURIComponent(id)}`, { signal });
}

export function getEventOdds(id: string, market: Market, signal?: AbortSignal): Promise<OddsComparison> {
  return apiGet<OddsComparison>(`/v1/events/${encodeURIComponent(id)}/odds`, { query: { market }, signal });
}
