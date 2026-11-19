/** Server-side configuration shared by the proxy, `api()` and the `/api/ov` bridge. No request APIs here. */
export const API_URL = (process.env.ODDVEX_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const SESSION_COOKIE = "ov_session";

/** Local and e2e runs serve the production build over plain http; see `.env.example`. */
export function servedOverHttps(env: Record<string, string | undefined> = process.env): boolean {
  return env.NODE_ENV === "production" && env.ODDVEX_INSECURE_COOKIES !== "true";
}

/**
 * Request header in which `src/proxy.ts` tells server components the path and query of the
 * page being rendered; they have no other way to learn it. The proxy overwrites whatever the
 * client sent, but it does not run for every request (prefetches skip it), so a reader must
 * treat the value as untrusted text: `lib/safe-next.ts`.
 */
export const PAGE_PATH_HEADER = "x-ov-page-path";

/**
 * How long the web server waits for one answer from the API when it reads something for a
 * page. `api()` and the session-ended route share it: that route re-asks a question a page
 * has just had answered, so it must not give up sooner than the page did.
 */
export const API_TIMEOUT_MS = 8000;
