import type {
  AlertCreate,
  AlertEvaluation,
  AlertRule,
  AlertState,
  AssistantReply,
  AuthResponse,
  AutoSettle,
  Bet,
  BetAnalytics,
  BetCreate,
  BetSettle,
  BetSummary,
  BetUpdate,
  Book,
  ClvResult,
  ConvertResult,
  EmailVerification,
  Entitlements,
  EventDetail,
  EventStatus,
  EventSummary,
  EvResult,
  Flags,
  League,
  Market,
  Message,
  Meta,
  Notification,
  NotificationList,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  NoVigResult,
  OddsComparison,
  ParlayRequest,
  ParlayResult,
  PasswordResetConfirm,
  PasswordResetRequest,
  PropAnalysis,
  PropBoardRow,
  PropSplit,
  PropWindow,
  StakeReminder,
  SyncConnection,
  SyncDelete,
  SyncProvider,
  SyncRun,
  User,
  ValueScreen,
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
let unauthorizedHandler: ((error: ApiError) => void) | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

/**
 * Called when the API rejects the token the app holds (401 on a request that sent it). The error says why:
 * an expired or replaced token, or `account_suspended`.
 */
export function setUnauthorizedHandler(handler: ((error: ApiError) => void) | null): void {
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
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
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
    if (response.status === 401 && token && token === authToken) unauthorizedHandler?.(error);
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

/** Every known feature flag and whether it is on. Public. */
export async function getFlags(signal?: AbortSignal): Promise<Flags> {
  return (await apiGet<{ flags: Flags }>('/v1/flags', { signal })).flags;
}

/** Best price against the consensus of the other books. Behind the `value_screen` flag. */
export function getValueScreen(
  filters: { league?: string | null; market?: Market | null; minEdge?: number | null } = {},
  signal?: AbortSignal,
): Promise<ValueScreen> {
  return apiGet<ValueScreen>('/v1/value', {
    query: { league: filters.league, market: filters.market, min_edge: filters.minEdge || undefined },
    signal,
  });
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

/** The plan and what it includes. `preview` is true while plans are not enforced. There is no purchase route. */
export function getEntitlements(signal?: AbortSignal): Promise<Entitlements> {
  return apiRequest<Entitlements>('/v1/me/entitlements', { auth: 'required', signal });
}

// Email flows, behind the `email_flows` flag. The API queues the message in an outbox; in this preview no
// email is actually sent.

export function requestEmailVerification(): Promise<Message> {
  return apiRequest<Message>('/v1/auth/verify-email/request', { method: 'POST', auth: 'required', body: {} });
}

/** No sign-in needed: the token from the link identifies the account. It works once. */
export function confirmEmailVerification(token: string): Promise<EmailVerification> {
  return apiRequest<EmailVerification>('/v1/auth/verify-email/confirm', { body: { token } });
}

/** Always answers the same way, whether or not an account exists for the address. */
export function requestPasswordReset(email: string): Promise<Message> {
  const body: PasswordResetRequest = { email };
  return apiRequest<Message>('/v1/auth/password-reset/request', { body });
}

/** Signs out every earlier session and returns no token: the user logs in again with the new password. */
export function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  const body: PasswordResetConfirm = { token, new_password: newPassword };
  return apiRequest<void>('/v1/auth/password-reset/confirm', { body });
}

// Bet tracker

export function getBets(signal?: AbortSignal): Promise<Bet[]> {
  return apiRequest<Bet[]>('/v1/bets', { auth: 'required', signal });
}

export function getBetSummary(signal?: AbortSignal): Promise<BetSummary> {
  return apiRequest<BetSummary>('/v1/bets/summary', { auth: 'required', signal });
}

/** Breakdowns of the user's settled bets. Behind the `tracker_analytics` flag. */
export function getBetAnalytics(signal?: AbortSignal): Promise<BetAnalytics> {
  return apiRequest<BetAnalytics>('/v1/bets/analytics', { auth: 'required', signal });
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

// Alerts and notifications. In-app only: there is no push, and no background worker. The API evaluates the
// user's alert rules when the app reads the notifications or the unread count, or calls `evaluateAlerts`.

export async function getAlerts(state?: AlertState | null, signal?: AbortSignal): Promise<AlertRule[]> {
  return (await apiRequest<{ items: AlertRule[] }>('/v1/alerts', { auth: 'required', query: { state }, signal })).items;
}

/** 201 for a new rule; 200 with the existing rule when an identical active one is already there. */
export function createAlert(rule: AlertCreate): Promise<AlertRule> {
  return apiRequest<AlertRule>('/v1/alerts', { auth: 'required', body: rule });
}

/** `paused` pauses an active rule. `active` resumes a paused rule or sets a triggered one again. */
export function updateAlert(alertId: string, state: 'active' | 'paused'): Promise<AlertRule> {
  return apiRequest<AlertRule>(`/v1/alerts/${id(alertId)}`, { method: 'PATCH', auth: 'required', body: { state } });
}

export function deleteAlert(alertId: string): Promise<void> {
  return apiRequest<void>(`/v1/alerts/${id(alertId)}`, { method: 'DELETE', auth: 'required' });
}

export function evaluateAlerts(): Promise<AlertEvaluation> {
  return apiRequest<AlertEvaluation>('/v1/alerts/evaluate', { method: 'POST', auth: 'required', body: {} });
}

export function getNotifications(
  filters: { unread?: boolean; limit?: number; before?: string | null } = {},
  signal?: AbortSignal,
): Promise<NotificationList> {
  return apiRequest<NotificationList>('/v1/notifications', {
    auth: 'required',
    query: { unread: filters.unread, limit: filters.limit, before: filters.before },
    signal,
  });
}

export async function getUnreadCount(signal?: AbortSignal): Promise<number> {
  return (await apiRequest<{ unread_count: number }>('/v1/notifications/unread-count', { auth: 'required', signal })).unread_count;
}

export function markNotificationRead(notificationId: string): Promise<Notification> {
  return apiRequest<Notification>(`/v1/notifications/${id(notificationId)}/read`, { method: 'POST', auth: 'required', body: {} });
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return apiRequest<{ updated: number }>('/v1/notifications/read-all', { method: 'POST', auth: 'required', body: {} });
}

export function deleteNotification(notificationId: string): Promise<void> {
  return apiRequest<void>(`/v1/notifications/${id(notificationId)}`, { method: 'DELETE', auth: 'required' });
}

export function getNotificationPreferences(signal?: AbortSignal): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>('/v1/me/notification-preferences', { auth: 'required', signal });
}

/** Sends only the kinds that changed; the API leaves the others alone. */
export function updateNotificationPreferences(update: NotificationPreferencesUpdate): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>('/v1/me/notification-preferences', { method: 'PUT', auth: 'required', body: update });
}

export function getStakeReminder(signal?: AbortSignal): Promise<StakeReminder> {
  return apiRequest<StakeReminder>('/v1/me/stake-reminder', { auth: 'required', signal });
}

/** A weekly amount, or `null` to turn the reminder off. A reminder, never a limit: bets are always saved. */
export function setStakeReminder(weeklyStakeThreshold: number | null): Promise<StakeReminder> {
  return apiRequest<StakeReminder>('/v1/me/stake-reminder', {
    method: 'PUT',
    auth: 'required',
    body: { weekly_stake_threshold: weeklyStakeThreshold },
  });
}

export const FEATURE_UNAVAILABLE = "This feature isn't available right now.";

/** A route behind a feature flag that is off answers 404 `feature_disabled`. */
export function isFeatureDisabled(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && error.code === 'feature_disabled';
}

/** 401 on any call that carried the token, or 403 on log in with the right password. */
export function isAccountSuspended(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'account_suspended';
}

/** One sentence for an inline error, with the web app's wording for the two cases that need their own. */
export function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Try again in a moment.";
  if (error instanceof ApiError) {
    if (error.status === 429) return 'Too many attempts. Wait a minute, then try again.';
    if (isFeatureDisabled(error)) return FEATURE_UNAVAILABLE;
    return error.message || fallback;
  }
  return fallback;
}
