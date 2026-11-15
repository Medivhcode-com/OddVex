import type {
  AssistantReply,
  AuthResponse,
  AutoSettle,
  Bet,
  BetCreate,
  BetSettle,
  BetSummary,
  BetUpdate,
  Book,
  ClvResult,
  ConvertResult,
  EventDetail,
  EventStatus,
  EventSummary,
  EvResult,
  League,
  Market,
  Meta,
  NoVigResult,
  OddsComparison,
  ParlayRequest,
  ParlayResult,
  PropAnalysis,
  PropBoardRow,
  PropSplit,
  PropWindow,
  SyncConnection,
  SyncDelete,
  SyncProvider,
  SyncRun,
  User,
  WatchItem,
  WatchKind,
} from '@/api/types';

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

type Query = Record<string, string | number | boolean | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const parts: string[] = [];
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return parts.length ? `${path}?${parts.join('&')}` : path;
}

// The bearer token lives in memory here and in SecureStore (see src/session/store.ts). The session provider
// is the only caller of these two setters.
let authToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

/** Called when the API rejects the token the app holds (401 on a request that sent it). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
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

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
  /**
   * `none`: public data, no token sent. `required`: the user's own data; fails without a token.
   * `optional`: sends the token when there is one (the assistant answers more when it knows who is asking).
   */
  auth?: 'none' | 'required' | 'optional';
};

/**
 * One JSON request. Nothing is cached: prices are live by nature.
 * Aborting `signal` rejects with the abort error so callers can tell "cancelled" from "unreachable".
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const auth = options.auth ?? 'none';
  const token = auth === 'none' ? null : authToken;
  if (auth === 'required' && !token) throw new ApiError(401, 'not_logged_in', 'Log in to continue.');

  const controller = new AbortController();
  const outer = options.signal;
  const forwardAbort = () => controller.abort();
  if (outer?.aborted) controller.abort();
  outer?.addEventListener('abort', forwardAbort);
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  const headers: Record<string, string> = { accept: 'application/json' };
  if (options.body !== undefined) headers['content-type'] = 'application/json';
  if (token) headers.authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${withQuery(path, options.query)}`, {
      method: options.method ?? (options.body === undefined ? 'GET' : 'POST'),
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
  } catch (error) {
    if (outer?.aborted) throw error;
    throw new ApiUnavailableError();
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener('abort', forwardAbort);
  }

  if (!response.ok) {
    const error = await parseError(response);
    // Only a rejected token ends the session, and only if it is still the one in use.
    if (response.status === 401 && token && token === authToken) unauthorizedHandler?.();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, 'invalid_response', 'The data service sent a response the app could not read.');
  }
}

export function apiGet<T>(path: string, options: { query?: Query; signal?: AbortSignal } = {}): Promise<T> {
  return apiRequest<T>(path, options);
}

const id = encodeURIComponent;

// Public research data

export function getMeta(signal?: AbortSignal): Promise<Meta> {
  return apiGet<Meta>('/v1/meta', { signal });
}

export function getLeagues(signal?: AbortSignal): Promise<League[]> {
  return apiGet<League[]>('/v1/leagues', { signal });
}

export function getSportsbooks(signal?: AbortSignal): Promise<Book[]> {
  return apiGet<Book[]>('/v1/sportsbooks', { signal });
}

export function getEvents(
  filters: { league?: string | null; status?: EventStatus | null } = {},
  signal?: AbortSignal,
): Promise<EventSummary[]> {
  return apiGet<EventSummary[]>('/v1/events', { query: { league: filters.league, status: filters.status }, signal });
}

export function getEvent(eventId: string, signal?: AbortSignal): Promise<EventDetail> {
  return apiGet<EventDetail>(`/v1/events/${id(eventId)}`, { signal });
}

export function getEventOdds(eventId: string, market: Market, signal?: AbortSignal): Promise<OddsComparison> {
  return apiGet<OddsComparison>(`/v1/events/${id(eventId)}/odds`, { query: { market }, signal });
}

export function getProps(league?: string | null, signal?: AbortSignal): Promise<PropBoardRow[]> {
  return apiGet<PropBoardRow[]>('/v1/props', { query: { league }, signal });
}

export function getPlayerProps(
  playerId: string,
  filters: { market?: string | null; window?: PropWindow; split?: PropSplit } = {},
  signal?: AbortSignal,
): Promise<PropAnalysis> {
  return apiGet<PropAnalysis>(`/v1/players/${id(playerId)}/props`, {
    query: { market: filters.market, window: filters.window, split: filters.split },
    signal,
  });
}

// Account

export function login(email: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/v1/auth/login', { body: { email, password } });
}

export function register(input: { email: string; password: string; display_name: string }): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/v1/auth/register', { body: { ...input, age_confirmed: true } });
}

export function getMe(signal?: AbortSignal): Promise<User> {
  return apiRequest<User>('/v1/me', { auth: 'required', signal });
}

/** The API signs out every earlier session and answers with a fresh token. */
export function changePassword(currentPassword: string, newPassword: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/v1/me/password', {
    auth: 'required',
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export function deleteAccount(): Promise<void> {
  return apiRequest<void>('/v1/me', { method: 'DELETE', auth: 'required' });
}

// Bet tracker

export function getBets(signal?: AbortSignal): Promise<Bet[]> {
  return apiRequest<Bet[]>('/v1/bets', { auth: 'required', signal });
}

export function getBetSummary(signal?: AbortSignal): Promise<BetSummary> {
  return apiRequest<BetSummary>('/v1/bets/summary', { auth: 'required', signal });
}

export function createBet(bet: BetCreate): Promise<Bet> {
  return apiRequest<Bet>('/v1/bets', { auth: 'required', body: bet });
}

export function updateBet(betId: string, patch: BetUpdate): Promise<Bet> {
  return apiRequest<Bet>(`/v1/bets/${id(betId)}`, { method: 'PATCH', auth: 'required', body: patch });
}

export function settleBet(betId: string, settlement: BetSettle): Promise<Bet> {
  return apiRequest<Bet>(`/v1/bets/${id(betId)}/settle`, { auth: 'required', body: settlement });
}

export function deleteBet(betId: string): Promise<void> {
  return apiRequest<void>(`/v1/bets/${id(betId)}`, { method: 'DELETE', auth: 'required' });
}

export function autoSettleBets(): Promise<AutoSettle> {
  return apiRequest<AutoSettle>('/v1/bets/auto-settle', { method: 'POST', auth: 'required', body: {} });
}

// Watchlist

export async function getWatchlist(signal?: AbortSignal): Promise<WatchItem[]> {
  return (await apiRequest<{ items: WatchItem[] }>('/v1/watchlist', { auth: 'required', signal })).items;
}

export function getWatchlistEvents(signal?: AbortSignal): Promise<EventSummary[]> {
  return apiRequest<EventSummary[]>('/v1/watchlist/events', { auth: 'required', signal });
}

export function follow(kind: WatchKind, refId: string): Promise<WatchItem> {
  return apiRequest<WatchItem>('/v1/watchlist', { auth: 'required', body: { kind, ref_id: refId } });
}

export function unfollow(itemId: string): Promise<void> {
  return apiRequest<void>(`/v1/watchlist/${id(itemId)}`, { method: 'DELETE', auth: 'required' });
}

// Calculators. Every number comes back from the API's quant engine.

type OddsInput = { odds: string; odds_format: 'american' | 'decimal' | 'fractional' };

export function quantConvert(body: OddsInput): Promise<ConvertResult> {
  return apiRequest<ConvertResult>('/v1/quant/convert', { body });
}

export function quantNoVig(body: { odds: string[]; odds_format: OddsInput['odds_format'] }): Promise<NoVigResult> {
  return apiRequest<NoVigResult>('/v1/quant/no-vig', { body });
}

export function quantEv(body: OddsInput & { win_probability: number; stake: number }): Promise<EvResult> {
  return apiRequest<EvResult>('/v1/quant/ev', { body });
}

export function quantClv(
  body: OddsInput & { closing_odds: string; closing_opposite_odds: string | null },
): Promise<ClvResult> {
  return apiRequest<ClvResult>('/v1/quant/clv', { body });
}

export function quantParlay(body: ParlayRequest): Promise<ParlayResult> {
  return apiRequest<ParlayResult>('/v1/quant/parlay', { body });
}

// Assistant

export function askAssistant(message: string): Promise<AssistantReply> {
  return apiRequest<AssistantReply>('/v1/assistant/query', { auth: 'optional', body: { message } });
}

// Sportsbook sync (mock provider only)

export function getSyncProviders(signal?: AbortSignal): Promise<SyncProvider[]> {
  return apiRequest<SyncProvider[]>('/v1/sync/providers', { auth: 'required', signal });
}

export function getSyncConnections(signal?: AbortSignal): Promise<SyncConnection[]> {
  return apiRequest<SyncConnection[]>('/v1/sync/connections', { auth: 'required', signal });
}

export function createSyncConnection(provider: string): Promise<SyncConnection> {
  return apiRequest<SyncConnection>('/v1/sync/connections', { auth: 'required', body: { provider } });
}

export function runSync(connectionId: string): Promise<SyncRun> {
  return apiRequest<SyncRun>(`/v1/sync/connections/${id(connectionId)}/sync`, {
    method: 'POST',
    auth: 'required',
    body: {},
  });
}

export function deleteSyncConnection(connectionId: string): Promise<SyncDelete> {
  return apiRequest<SyncDelete>(`/v1/sync/connections/${id(connectionId)}`, {
    method: 'DELETE',
    auth: 'required',
    query: { delete_data: true },
  });
}

/** One sentence for an inline error, with the web app's wording for the two cases that need their own. */
export function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Try again in a moment.";
  if (error instanceof ApiError) {
    if (error.status === 429) return 'Too many attempts. Wait a minute, then try again.';
    return error.message || fallback;
  }
  return fallback;
}
