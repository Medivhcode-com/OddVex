import { describe, expect, it } from "vitest";
import { pagePath, safeNext, safePath, withNext } from "./safe-next";

/** Where the browser is when it follows the redirect: the login page of the site. */
const PAGE = "https://preview.oddvex.com/login?next=x";
const SITE = "https://preview.oddvex.com";

/** What a browser does with a `Location` or `x-action-redirect` value. */
const lands = (target: string) => new URL(target, PAGE).origin;

const OFF_SITE = [
  // The audit finding, and its line-break siblings: the URL parser drops tab, LF and CR.
  "/\t/evil.example",
  "/\n/evil.example",
  "/\r/evil.example",
  "/\r\n/evil.example",
  "/\t\t/evil.example",
  "/\t\\evil.example",
  "/\t/evil.example:99999",
  "/\t/[",
  // A second slash, and the backslash a browser reads as one.
  "//evil.example",
  "///evil.example",
  "//evil.example/app",
  "//[",
  "/\\evil.example",
  "/\\/evil.example",
  "\\\\evil.example",
  "\\/evil.example",
  // Dot segments that leave a double slash at the front once resolved.
  "/.//evil.example",
  "/x/..//evil.example",
  "/./\\evil.example",
  "/%2e//evil.example",
  "/x/%2E%2E//evil.example",
  // Leading whitespace, which a browser strips before it parses.
  " //evil.example",
  "\t//evil.example",
  "\n//evil.example",
  " /\\evil.example",
  " https://evil.example",
  // A scheme, or no leading slash at all.
  "https://evil.example",
  "HTTPS://evil.example/app",
  "http:evil.example",
  "https:/evil.example",
  "javascript:alert(1)",
  "data:text/html,x",
  "evil.example",
  "app/tracker",
  "@evil.example",
  "?next=//evil.example",
  "",
];

/** Stay on the site when a browser resolves them, but nothing in the app has such a path. */
const ENCODED = [
  "/%09/evil.example",
  "/%0a/evil.example",
  "/%0D/evil.example",
  "/%0d%0aSet-Cookie:%20x=1",
  "/%2F/evil.example",
  "/%2f%2fevil.example",
  "/%5Cevil.example",
  "/%5c%5cevil.example",
  "/%252F%252Fevil.example",
  "/%00",
  "/%7f",
];

describe("safePath", () => {
  it("refuses everything a browser would take to another site", () => {
    for (const value of OFF_SITE) expect(safePath(value), JSON.stringify(value)).toBeNull();
  });

  it("refuses percent-encoded slashes, backslashes and control characters in the path", () => {
    for (const value of ENCODED) expect(safePath(value), value).toBeNull();
  });

  it("refuses anything that is not a string", () => {
    for (const value of [undefined, null, 7, {}, ["/app", "/app/tracker"], ["//evil.example"]]) expect(safePath(value)).toBeNull();
  });

  it("keeps an ordinary app path as it is, with its query and fragment", () => {
    for (const value of [
      "/",
      "/app",
      "/app/tracker",
      "/app/tracker?x=1#y",
      "/app/games/evt_nba_20261119_2",
      "/app/community/profiles/demo_bettor",
      "/app/odds?league=nba&q=a%2Fb",
      "/app/admin/users?q=a.b@example.test",
    ]) {
      expect(safePath(value), value).toBe(value);
    }
  });

  it("returns the path the parser resolved, never the raw text", () => {
    expect(safePath("/app/./tracker")).toBe("/app/tracker");
    expect(safePath("/app/x/../tracker")).toBe("/app/tracker");
    expect(safePath("/app/../../..")).toBe("/");
  });

  it("stays on the site for every mix of the usual bypass pieces", () => {
    const pieces = ["/", "\\", "\t", "\n", "\r", " ", ".", "..", "%2f", "%5C", "%09", "%2e", "%25", "@", ":", "?", "#", "evil.example", "https:"];
    let checked = 0;
    const walk = (prefix: string, depth: number) => {
      const out = safePath(prefix);
      if (out !== null) {
        checked += 1;
        expect(lands(out), JSON.stringify(prefix)).toBe(SITE);
        // Still on the site if something decodes the path once more on the way.
        const path = out.split(/[?#]/)[0];
        expect(lands(decodeURIComponent(path)), JSON.stringify(prefix)).toBe(SITE);
        expect(out.startsWith("/") && !out.startsWith("//"), JSON.stringify(prefix)).toBe(true);
        // The answer is stable: checking it again changes nothing.
        expect(safePath(out), JSON.stringify(prefix)).toBe(out);
      }
      if (depth > 0) for (const piece of pieces) walk(prefix + piece, depth - 1);
    };
    walk("", 4);
    for (const piece of pieces) walk(`/${piece}`, 3);
    expect(checked).toBeGreaterThan(1000);
  });
});

describe("safeNext", () => {
  it("falls back to the app home for a refused destination", () => {
    for (const value of [...OFF_SITE, ...ENCODED]) expect(safeNext(value), JSON.stringify(value)).toBe("/app");
    expect(safeNext(undefined)).toBe("/app");
    expect(safeNext(null)).toBe("/app");
    // `?next=a&next=b` reaches the page as an array.
    expect(safeNext(["/app/tracker", "//evil.example"])).toBe("/app");
  });

  it("never sends a browser off the site", () => {
    for (const value of [...OFF_SITE, ...ENCODED]) expect(lands(safeNext(value)), JSON.stringify(value)).toBe(SITE);
  });

  it("keeps a same-site destination", () => {
    expect(safeNext("/app/tracker?x=1#y")).toBe("/app/tracker?x=1#y");
    expect(safeNext("/app/settings")).toBe("/app/settings");
  });
});

describe("pagePath", () => {
  it("keeps the query it is given as it is", () => {
    expect(pagePath("/app/games", "")).toBe("/app/games");
    expect(pagePath("/app/games", "?league=nba")).toBe("/app/games?league=nba");
    expect(pagePath("/app/games", "?flag=&q=a+b")).toBe("/app/games?flag=&q=a+b");
    // Parsing and writing the query again would turn these into `flag=` and `a+b`.
    expect(pagePath("/app/games", "?flag&q=a%20b")).toBe("/app/games?flag&q=a%20b");
    expect(pagePath("/app/odds", "?q=a+b&league=nba&league=nfl&x=%E2%9C%93")).toBe("/app/odds?q=a+b&league=nba&league=nfl&x=%E2%9C%93");
  });

  it("drops the parameter Next.js adds to its data requests, and only that one", () => {
    expect(pagePath("/app/games", "?_rsc=1a2b3")).toBe("/app/games");
    expect(pagePath("/app/games", "?league=nba&_rsc=1a2b3")).toBe("/app/games?league=nba");
    expect(pagePath("/app/games", "?_rsc=1a2b3&league=nba&flag")).toBe("/app/games?league=nba&flag");
    expect(pagePath("/app/games", "?a=1&_rsc&b=2")).toBe("/app/games?a=1&b=2");
    expect(pagePath("/app/games", "?x_rsc=1&_rscx=2&q=_rsc=3")).toBe("/app/games?x_rsc=1&_rscx=2&q=_rsc=3");
    expect(pagePath("/app/games", "?")).toBe("/app/games");
  });

  it("gives a value that passes the same-site check unchanged", () => {
    for (const [pathname, search] of [
      ["/app/games", "?flag&q=a%20b"],
      ["/app/tracker", ""],
      ["/app/odds", "?league=nba&market=moneyline"],
    ]) {
      const value = pagePath(pathname, search);
      expect(safePath(value), value).toBe(value);
    }
  });
});

describe("withNext", () => {
  const read = (href: string | null) => new URL(href ?? "", SITE).searchParams.get("next");

  it("carries a same-site page in ?next= so that it reads back as it was", () => {
    for (const here of ["/app", "/app/games?league=nba", "/app/games?flag&q=a%20b", "/app/odds?q=a+b&x=1#y", "/app/community/profiles/demo_bettor"]) {
      const href = withNext("/api/session/ended", here);
      expect(href, here).toBe(`/api/session/ended?next=${encodeURIComponent(here)}`);
      expect(read(href), here).toBe(here);
    }
  });

  it("is null for anything that is not a same-site page", () => {
    for (const value of [...OFF_SITE, ...ENCODED, undefined, null, 7, ["/app"]]) expect(withNext("/api/session/ended", value), JSON.stringify(value)).toBeNull();
  });

  it("is null when the address would be too long for a server to accept", () => {
    // Node refuses a request whose headers pass 16 KB (431); encoding can triple a query.
    const fits = `/app/games?q=${"a".repeat(1900)}`;
    expect(withNext("/api/session/ended", fits)).not.toBeNull();
    for (const here of [`/app/games?q=${"a".repeat(2100)}`, `/app/games?q=${"%2F".repeat(700)}`, `/app/games?q=${"%2F".repeat(4000)}`]) {
      expect(withNext("/api/session/ended", here), `${here.length} characters`).toBeNull();
    }
    for (const length of [10, 500, 1000, 1500, 1990, 2000, 2010, 3000, 12000]) {
      const href = withNext("/api/session/ended", `/app/games?q=${"%2F".repeat(Math.ceil(length / 3))}`);
      if (href !== null) expect(href.length).toBeLessThanOrEqual(2048);
    }
  });
});
