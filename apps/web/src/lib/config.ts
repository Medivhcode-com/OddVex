/** Server-side configuration shared by the proxy, `api()` and the `/api/ov` bridge. No request APIs here. */
export const API_URL = (process.env.ODDVEX_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const SESSION_COOKIE = "ov_session";

/** Local and e2e runs serve the production build over plain http; see `.env.example`. */
export function servedOverHttps(env: Record<string, string | undefined> = process.env): boolean {
  return env.NODE_ENV === "production" && env.ODDVEX_INSECURE_COOKIES !== "true";
}
