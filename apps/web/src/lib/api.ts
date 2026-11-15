import "server-only";
import { cookies } from "next/headers";

export const API_URL = (process.env.ODDVEX_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const SESSION_COOKIE = "ov_session";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Thrown when the API cannot be reached at all, as opposed to answering with an error. */
export class ApiUnavailableError extends Error {
  constructor() {
    super("The OddVex API is not reachable.");
    this.name = "ApiUnavailableError";
  }
}

export async function sessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
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

export async function parseError(response: Response): Promise<ApiError> {
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
  return new ApiError(response.status, code, message, details);
}

/**
 * Server-side API call. Data is live by nature, so nothing is cached here.
 * Pass `auth: true` to attach the session token.
 */
export async function api<T>(
  path: string,
  options: { query?: Query; method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (options.body !== undefined) headers["content-type"] = "application/json";
  if (options.auth) {
    const token = await sessionToken();
    if (token) headers.authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${withQuery(path, options.query)}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new ApiUnavailableError();
  }
  if (!response.ok) throw await parseError(response);
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
