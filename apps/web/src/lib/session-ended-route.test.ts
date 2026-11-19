import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/session/ended/route";
import { API_TIMEOUT_MS, API_URL, SESSION_COOKIE } from "@/lib/config";

/**
 * The `/api/session/ended` route handler, called the way Next.js calls it, with the upstream
 * API replaced by a stub. A page sends a visitor here when the API has rejected the session
 * token, with `?next=` naming that page. The handler may send the visitor back to it only when
 * that page will not send them here again.
 */
const upstream = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();
vi.stubGlobal("fetch", upstream);

const SITE = "http://localhost:3210";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const apiError = (status: number, code: string) => json(status, { error: { code, message: code } });
const user = () => json(200, { id: "usr_1", email: "a@example.com", role: "user" });

function visit(query: string, options: { cookie?: string; headers?: Record<string, string> } = {}) {
  const headers = new Headers(options.headers);
  if (options.cookie) headers.set("cookie", `${SESSION_COOKIE}=${options.cookie}`);
  return GET(new NextRequest(`${SITE}/api/session/ended${query}`, { headers }));
}

const clearsSession = (response: Response) => new RegExp(`^${SESSION_COOKIE}=;.*(Expires=Thu, 01 Jan 1970|Max-Age=0)`, "i").test(response.headers.get("set-cookie") ?? "");

/** Ways the API can fail to say whether the token is still good. */
const NO_ANSWER: Record<string, () => Promise<Response>> = {
  "a refused connection": async () => {
    throw new TypeError("fetch failed");
  },
  "a timeout": async () => {
    throw new DOMException("The operation was aborted due to timeout", "TimeoutError");
  },
  "a 500": async () => apiError(500, "internal_error"),
  "a 502 that is not JSON": async () => new Response("<html>Bad Gateway</html>", { status: 502, headers: { "content-type": "text/html" } }),
  "a 503": async () => apiError(503, "service_unavailable"),
  "a 429": async () => apiError(429, "rate_limited"),
  "a 404": async () => apiError(404, "not_found"),
  "a 500 that names a dead token": async () => apiError(500, "invalid_token"),
  "a 304": async () => new Response(null, { status: 304 }),
};

beforeEach(() => {
  upstream.mockReset();
  upstream.mockImplementation(async () => user());
});

describe("/api/session/ended", () => {
  it("asks the API about the cookie's token and nothing else", async () => {
    await visit("?next=/app/tools", { cookie: "token-1" });
    expect(upstream).toHaveBeenCalledTimes(1);
    expect(upstream.mock.calls[0][0]).toBe(`${API_URL}/v1/me`);
    expect((upstream.mock.calls[0][1].headers as Record<string, string>).authorization).toBe("Bearer token-1");
  });

  it("clears the cookie of a token the API rejects and goes back to the page", async () => {
    upstream.mockImplementation(async () => apiError(401, "invalid_token"));
    const response = await visit(`?next=${encodeURIComponent("/app/games?league=nba")}`, { cookie: "revoked" });
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("/app/games?league=nba");
    expect(clearsSession(response)).toBe(true);
  });

  it("clears the cookie and shows the login page when no page was named", async () => {
    for (const reply of [() => apiError(401, "invalid_token"), () => apiError(401, "not_authenticated"), () => apiError(403, "forbidden"), () => new Response("no", { status: 401 })]) {
      upstream.mockImplementation(async () => reply());
      const response = await visit("", { cookie: "revoked" });
      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toBe("/login");
      expect(clearsSession(response)).toBe(true);
    }
  });

  it("sends a suspended account to the login page with the explanation, whatever page was named", async () => {
    upstream.mockImplementation(async () => apiError(401, "account_suspended"));
    for (const query of ["", "?next=/app/tools"]) {
      const response = await visit(query, { cookie: "suspended" });
      expect(response.headers.get("location"), query).toBe("/login?suspended=1");
      expect(clearsSession(response), query).toBe(true);
    }
  });

  it("leaves a working session alone", async () => {
    const named = await visit("?next=/app/settings", { cookie: "good" });
    expect(named.status).toBe(307);
    expect(named.headers.get("location")).toBe("/app/settings");
    expect(named.headers.get("set-cookie")).toBeNull();
    const bare = await visit("", { cookie: "good" });
    expect(bare.headers.get("location")).toBe("/app");
    expect(bare.headers.get("set-cookie")).toBeNull();
  });

  it("does not call the API for a visitor without a cookie", async () => {
    expect((await visit("?next=/app/tools")).headers.get("location")).toBe("/app/tools");
    expect((await visit("")).headers.get("location")).toBe("/login");
    expect(upstream).not.toHaveBeenCalled();
  });

  for (const [what, reply] of Object.entries(NO_ANSWER)) {
    // The page named in ?next= sent the visitor here because its own call was answered
    // "invalid token". Going back to it with the cookie still set would start that over.
    it(`goes to the login page with the cookie untouched when the API gives ${what}`, async () => {
      for (const query of ["?next=/app/tools", `?next=${encodeURIComponent("/app/games?league=nba")}`, ""]) {
        upstream.mockReset();
        upstream.mockImplementation(reply);
        const response = await visit(query, { cookie: "revoked" });
        expect(response.status, query).toBe(307);
        expect(response.headers.get("location"), query).toBe("/login");
        expect(response.headers.get("set-cookie"), query).toBeNull();
        expect(upstream, query).toHaveBeenCalledTimes(1);
      }
    });
  }

  it("never sends a visitor back to the page with a cookie the API has not accepted", async () => {
    const replies = [...Object.values(NO_ANSWER), async () => user(), async () => apiError(401, "invalid_token"), async () => apiError(401, "account_suspended"), async () => apiError(403, "forbidden")];
    for (const reply of replies) {
      upstream.mockReset();
      upstream.mockImplementation(reply);
      const response = await visit("?next=/app/tools", { cookie: "token" });
      if (response.headers.get("location") !== "/app/tools") continue;
      const accepted = await reply().then((answer) => answer.ok, () => false);
      expect(accepted || clearsSession(response)).toBe(true);
    }
  });

  it("gives the API as long to answer as a page does", async () => {
    // With less time than `api()`, an answer the page waited for would be missed here.
    const timeout = vi.spyOn(AbortSignal, "timeout");
    await visit("?next=/app/tools", { cookie: "token" });
    expect(timeout).toHaveBeenCalledWith(API_TIMEOUT_MS);
    expect(API_TIMEOUT_MS).toBe(8000);
    timeout.mockRestore();
  });

  it("accepts only a same-site path as the page to go back to", async () => {
    const offSite = ["//evil.example", "/\t/evil.example", "/%09/evil.example", "/\\evil.example", "https://evil.example", "/.//evil.example", "/%2F/evil.example", "evil.example"];
    for (const next of offSite) {
      const query = `?next=${encodeURIComponent(next)}`;
      expect((await visit(query)).headers.get("location"), next).toBe("/login");
      upstream.mockImplementation(async () => user());
      expect((await visit(query, { cookie: "good" })).headers.get("location"), next).toBe("/app");
      upstream.mockImplementation(async () => apiError(401, "invalid_token"));
      expect((await visit(query, { cookie: "revoked" })).headers.get("location"), next).toBe("/login");
    }
  });

  it("answers a fetch with plain text and does nothing else", async () => {
    upstream.mockImplementation(async () => apiError(401, "invalid_token"));
    const response = await visit("?next=/app/tools", { cookie: "revoked", headers: { "sec-fetch-dest": "empty" } });
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/plain");
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(upstream).not.toHaveBeenCalled();
  });
});
