/**
 * Turns text a visitor can control (`?next=`, a hidden form field) into a redirect target.
 * Pure, so it can be tested without a request; see `safe-next.test.ts`.
 *
 * The value is parsed the way a browser parses a `Location` header, and what is returned is
 * the parsed path, never the text that came in. A pattern check on the raw text is not
 * enough: a browser drops tab and line-break characters and reads a backslash as a slash, so
 * `/<tab>/other.example` passes a "starts with one slash" test and still leaves the site.
 */

/** Any origin the value cannot name. Only used to resolve the value against. */
const BASE = "https://next.invalid";

/** Control characters (a browser strips tab, LF and CR before parsing) and the backslash. */
const UNSAFE_CHARS = /[\u0000-\u001f\u007f\\]/;

/**
 * A percent-encoded slash, backslash, percent sign or control character in the path. A
 * browser leaves these alone, so they are not a way off the site by themselves; they are
 * refused so that the path stays harmless if anything on the way decodes it once more.
 */
const UNSAFE_ESCAPES = /%(?:2f|5c|25|7f|[01][0-9a-f])/i;

/** The same-site path, query and fragment that `value` names, or null if it is anything else. */
export function safePath(value: unknown): string | null {
  if (typeof value !== "string" || !value.startsWith("/") || UNSAFE_CHARS.test(value)) return null;
  let url: URL;
  try {
    url = new URL(value, BASE);
  } catch {
    return null;
  }
  // `//host` and `///host` name another origin. `/.//host` keeps this one, but resolves to a
  // path that starts with two slashes, which the next parser would read as a host.
  if (url.origin !== BASE || url.pathname.includes("//") || UNSAFE_ESCAPES.test(url.pathname)) return null;
  return url.pathname + url.search + url.hash;
}

/** The post-login destination: a same-site path, or the app home when `next` is not one. */
export function safeNext(next: unknown): string {
  return safePath(next) ?? "/app";
}

/**
 * The path and query of a page request, as `src/proxy.ts` passes it to the page. The query is
 * passed on as it is given, without the parameter Next.js adds to its own data requests.
 *
 * Next.js has already rewritten the query once before the proxy sees it (`?flag&q=a%20b`
 * arrives as `?flag=&q=a+b`), so a visitor who is sent away and back returns to an address
 * that means the same but may be spelled differently. Nothing is rewritten a second time here.
 */
export function pagePath(pathname: string, search: string): string {
  const kept = search
    .replace(/^\?/, "")
    .split("&")
    .filter((pair) => pair !== "" && pair.split("=", 1)[0] !== "_rsc");
  return kept.length ? `${pathname}?${kept.join("&")}` : pathname;
}

/**
 * The longest address `withNext` builds. Web servers refuse long request lines (Node answers
 * 431 once a request's headers pass 16 KB, and proxies in front of it allow less), and
 * encoding a query for `?next=` can triple its length.
 */
const MAX_HREF_LENGTH = 2048;

/**
 * `path?next=<here>` for a same-site `here`, or null when `here` is not a same-site path or
 * the address would be too long to request.
 */
export function withNext(path: string, here: unknown): string | null {
  const next = safePath(here);
  if (next === null) return null;
  const href = `${path}?next=${encodeURIComponent(next)}`;
  return href.length <= MAX_HREF_LENGTH ? href : null;
}
