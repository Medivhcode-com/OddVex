import "server-only";
import { cookies, headers as incomingHeaders } from "next/headers";
import { apiUnavailableDigest } from "@/lib/app-error";
import { API_TIMEOUT_MS, API_URL, SESSION_COOKIE } from "@/lib/config";
import { isRequestId, upstreamMetaHeaders } from "@/lib/request-meta";

export { API_URL, SESSION_COOKIE };

export class ApiError extends Error {
  /**
   * Next.js keeps an error's own `digest` and hands it to the client error boundary (the
   * message is redacted in production), so the request id is what `app/app/error.tsx` shows
   * as "Reference <id>". The same id is in the API's log line for the failed call.
   */
  digest?: string;

  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    if (requestId) this.digest = requestId;
  }
}

/**
 * Thrown when the API cannot be reached at all, as opposed to answering with an error.
 *
 * The digest is the only field of a server error that reaches the browser in a production
 * build, so it carries a fixed marker and the request id (`lib/app-error.ts`). That is how
 * `app/app/error.tsx` can say "OddVex can't reach its data service"; the message below stays
 * on the server.
 */
export class ApiUnavailableError extends Error {
  digest: string;

  constructor(public requestId?: string) {
    super("The OddVex API is not reachable.");
    this.name = "ApiUnavailableError";
    this.digest = apiUnavailableDigest(requestId);
  }
}

export async function sessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

/**
 * Drops the session cookie if this request is allowed to change cookies, which is the case in
 * a server action or a route handler. While a page renders it is not, and nothing happens.
 */
async function forgetSession(): Promise<void> {
  try {
    (await cookies()).delete(SESSION_COOKIE);
  } catch {}
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export async function parseError(response: Response, requestId?: string): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed (${response.status}).`;
  let details: unknown;
  try {
    const body = await response.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      details = body.error.details;
    }
  } catch {}
  // Prefer the id the API actually logged; it equals ours unless the API replaced it.
  const upstreamId = response.headers.get("x-request-id");
  return new ApiError(response.status, code, message, details, isRequestId(upstreamId) ? upstreamId : requestId);
}

/**
 * Server-side API call. Data is live by nature, so nothing is cached here.
 * Pass `auth: true` to attach the session token.
 *
 * Every call forwards the visitor's address (`X-Forwarded-For`) and a request id
 * (`X-Request-ID`, set once per request by `src/proxy.ts`), so the API can rate-limit per
 * visitor instead of per web server and its logs can be joined to a web error. The API only
 * honours `X-Forwarded-For` when `ODDVEX_TRUST_PROXY=true`; see `lib/request-meta.ts`.
 *
 * Reading request headers makes the calling route dynamic, so `api()` may only be called from
 * request-scoped code (the `/app` tree, auth pages, server actions), never at module scope
 * and never from a marketing page, which must stay static.
 *
 * When the API answers that the token it was sent is no longer valid (`401 invalid_token`:
 * logged out or password changed on another device), the session cookie is dropped right
 * here if the call comes from a server action. A page render cannot change cookies; pages
 * go through `currentUser()`, which sends the visitor to `SESSION_ENDED_PATH` instead.
 */
export async function api<T>(
  path: string,
  options: { query?: Query; method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const meta = upstreamMetaHeaders(await incomingHeaders());
  const headers: Record<string, string> = { accept: "application/json", ...meta.headers };
  if (options.body !== undefined) headers["content-type"] = "application/json";
  let sentToken = false;
  if (options.auth) {
    const token = await sessionToken();
    if (token) headers.authorization = `Bearer ${token}`;
    sentToken = Boolean(token);
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${withQuery(path, options.query)}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
  } catch {
    throw new ApiUnavailableError(meta.requestId);
  }
  if (!response.ok) {
    const error = await parseError(response, meta.requestId);
    if (sentToken && error.status === 401 && error.code === "invalid_token") await forgetSession();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Like `api`, but returns null on 404 so pages can call notFound(). */
export async function apiOrNull<T>(...args: Parameters<typeof api<T>>): Promise<T | null> {
  try {
    return await api<T>(...args);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
