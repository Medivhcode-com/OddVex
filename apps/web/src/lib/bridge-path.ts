/**
 * Which API paths the `/api/ov` bridge forwards. Pure, so it can be tested without a request;
 * see `bridge-path.test.ts` and `bridge-route.test.ts`.
 *
 * `/v1/admin` is deliberately not on the list: admin reads happen in server components and
 * admin changes in server actions (`lib/admin-actions.ts`), never from the browser. That
 * includes community moderation (`/v1/admin/community`); `/v1/community` is the member API.
 * `/v1/auth` is not on it either: signing in and out are server actions (`lib/auth-actions.ts`).
 */
const ALLOWED = /^\/v1\/(quant|bets|sync|assistant|events|players|props|me|watchlist|alerts|notifications|value|flags|community)(\/|$)/;

/**
 * What one path segment may consist of once Next.js has percent-decoded it: the characters
 * the API uses in route names, ids and handles. Everything else is refused, which covers a
 * slash or backslash (an encoded separator), a percent sign (a second layer of encoding), a
 * control character, and `?`, `#` or `;`.
 */
const SEGMENT = /^[A-Za-z0-9._~-]+$/;
const ONLY_DOTS = /^\.+$/;

/**
 * The API path for the decoded segments of a bridge request, or null when the request must
 * not be forwarded. The caller sends exactly the returned string: the allow-list is tested
 * against the path as the URL parser resolves it, and a path the parser would change at all
 * is refused, so the path that was checked and the path that is fetched cannot differ.
 */
export function bridgePath(segments: unknown): string | null {
  if (!Array.isArray(segments) || segments.length === 0) return null;
  for (const segment of segments) {
    if (typeof segment !== "string" || !SEGMENT.test(segment) || ONLY_DOTS.test(segment)) return null;
  }
  const path = `/${segments.join("/")}`;
  let resolved: string;
  try {
    resolved = new URL(path, "http://api.invalid").pathname;
  } catch {
    return null;
  }
  return resolved === path && ALLOWED.test(resolved) ? resolved : null;
}
