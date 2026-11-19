import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DELETE, GET, POST, PUT } from "@/app/api/ov/[...path]/route";
import { API_URL, SESSION_COOKIE } from "@/lib/config";

/**
 * The `/api/ov` route handler, called the way Next.js calls it, with the upstream API replaced
 * by a stub. Each test states what reached the API, which is what the allow-list is for.
 */
const upstream = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();
vi.stubGlobal("fetch", upstream);

const HANDLERS = { GET, POST, PUT, DELETE } as const;
const SITE = "http://localhost:3210";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const apiError = (status: number, code: string, message = code) => json(status, { error: { code, message } });

/**
 * Next.js gives a catch-all handler each URL segment percent-decoded once. An address it
 * cannot decode never reaches the handler, hence the plain `decodeURIComponent` here.
 */
function call(method: keyof typeof HANDLERS, rawPath: string, options: { cookie?: string; body?: unknown; headers?: Record<string, string> } = {}) {
  const headers = new Headers(options.headers);
  if (options.cookie) headers.set("cookie", `${SESSION_COOKIE}=${options.cookie}`);
  const request = new NextRequest(`${SITE}/api/ov/${rawPath}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const segments = rawPath.split("?")[0].split("/").map((segment) => decodeURIComponent(segment));
  return HANDLERS[method](request, { params: Promise.resolve({ path: segments }) });
}

const sent = (index = 0) => ({ url: upstream.mock.calls[index][0], init: upstream.mock.calls[index][1] });
const authorization = (index = 0) => (sent(index).init.headers as Record<string, string>).authorization;
const clearsSession = (response: Response) => new RegExp(`^${SESSION_COOKIE}=;.*(Expires=Thu, 01 Jan 1970|Max-Age=0)`, "i").test(response.headers.get("set-cookie") ?? "");

beforeEach(() => {
  upstream.mockReset();
  upstream.mockImplementation(async () => json(200, { ok: true }));
});

const REFUSED: Record<string, string[]> = {
  "a path that is not on the list": ["v1/admin/users", "v1/admin/flags/community", "v1/auth/login", "v1/dev/email-outbox/latest", "v1/meta", "v1", "health", "v2/me", "V1/me", "v1/Me", "v1/mexico", ""],
  "an encoded slash": [
    "v1/me%2F..%2Fadmin%2Fusers",
    "v1/me%2f..%2fadmin%2fflags%2fcommunity",
    "v1/me/..%2Fadmin/users",
    "v1/flags%2F..%2F..%2Fhealth",
    "v1/me%2F..%2Fauth%2Flogin",
    "v1%2Fadmin%2Fusers",
    "v1/community/x%2F..%2F..%2Fadmin%2Fusers",
    "v1/me%2Fexport",
  ],
  "a dot segment": ["v1/me/../admin/users", "v1/me/./export", "v1/me/..", "v1/../health", "v1/me/.../admin", "../v1/me"],
  "an encoded dot": ["v1/me/%2e%2e/admin/users", "v1/me/%2E%2E/admin/users", "v1/me/.%2e/admin/users", "v1/me/%2e/export", "v1/flags/%2e%2e/%2e%2e/health"],
  "double encoding": [
    "v1/me/%252e%252e/admin/users",
    "v1/me/%252E%252E/admin/users",
    "v1/me/.%252e/admin/users",
    "v1/me%252F..%252Fadmin%252Fusers",
    "v1/me/%25252e%25252e/admin/users",
    "v1/me/%255Cadmin",
  ],
  "a backslash": ["v1/me/..%5Cadmin/users", "v1/me%5C..%5Cadmin%5Cusers", "v1/me%5c..%5cauth%5clogin", "v1/flags%5C..%5C..%5Chealth", "v1%5Cadmin%5Cusers"],
  "a query, fragment or parameter smuggled into a segment": ["v1/me%3Fx=1", "v1/me%23/admin", "v1/me/..;/admin/users", "v1/me;x=1/export", "v1/me%3F/../admin/users"],
  "a control character or a space": ["v1/me%00", "v1/me/%09", "v1/me%0A/export", "v1/me%0D%0Ax-injected:1", "v1/me/%20", "v1/me%7F"],
  "an empty segment": ["v1//me", "v1/me//admin/users", "/v1/me", "v1/me/"],
};

describe("the /api/ov allow-list", () => {
  for (const [family, paths] of Object.entries(REFUSED)) {
    it(`answers 404 and calls nothing for ${family}`, async () => {
      for (const path of paths) {
        for (const method of ["GET", "PUT", "POST", "DELETE"] as const) {
          const response = await call(method, path, { cookie: "token", body: method === "GET" || method === "DELETE" ? undefined : { enabled: true } });
          expect(response.status, `${method} ${path}`).toBe(404);
          expect((await response.json()).error.code, `${method} ${path}`).toBe("not_found");
          expect(upstream, `${method} ${path}`).not.toHaveBeenCalled();
        }
      }
    });
  }

  it("forwards a listed path exactly as it was checked, with the query", async () => {
    for (const path of [
      "v1/me",
      "v1/me/export",
      "v1/events",
      "v1/events/evt_nba_20261119_2/odds?market=moneyline",
      "v1/players/plr_mlb_mrp_4/props",
      "v1/community/profiles/demo_bettor",
      "v1/bets/3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f",
      "v1/sync/connections/12?delete_data=true",
      "v1/community/picks/abc/comments?limit=20&before=2026-11-19T10%3A00%3A00Z",
      "v1/quant/convert",
      "v1/flags",
    ]) {
      upstream.mockClear();
      const response = await call("GET", path);
      expect(response.status, path).toBe(200);
      expect(upstream, path).toHaveBeenCalledTimes(1);
      expect(sent().url, path).toBe(`${API_URL}/${path}`);
    }
  });

  it("an encoded form of a listed path reaches the API as the plain path", async () => {
    await call("GET", "v1/%6De/export");
    expect(sent().url).toBe(`${API_URL}/v1/me/export`);
  });

  it("never asks the API for anything outside the listed areas, whatever the pieces", async () => {
    const pieces = ["v1", "me", "admin", "auth", "users", "..", ".", "%2e%2e", "%252e%252e", "..%2F", "%2F", "%5C", "..%5C", "%3F", "health", "x"];
    const asked = new Set<string>();
    const walk = async (parts: string[], depth: number) => {
      if (parts.length) {
        upstream.mockClear();
        await call("GET", parts.join("/"), { cookie: "token" });
        for (const [url] of upstream.mock.calls) asked.add(url);
      }
      if (depth > 0) for (const piece of pieces) await walk([...parts, piece], depth - 1);
    };
    await walk(["v1"], 3);
    await walk([], 2);
    expect(asked.size).toBeGreaterThan(0);
    for (const url of asked) {
      // "me" is the only listed area among the pieces, so every call must be inside /v1/me.
      expect(url === `${API_URL}/v1/me` || url.startsWith(`${API_URL}/v1/me/`), url).toBe(true);
      // The address the API receives resolves to itself: there is nothing left to normalise.
      expect(new URL(url).href, url).toBe(url);
      expect(url, url).not.toMatch(/\.\.|%|\\|\/\.\//);
    }
  });

  it("still refuses a cross-origin write", async () => {
    const response = await call("POST", "v1/quant/convert", { body: { odds: "-110" }, headers: { origin: "https://evil.example", host: "localhost:3210" } });
    expect(response.status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("refuses a write whose Origin is not a URL, as it does any other foreign origin", async () => {
    // A sandboxed frame sends `Origin: null`.
    for (const origin of ["null", "evil.example", "not a url"]) {
      const response = await call("POST", "v1/quant/convert", { body: { odds: "-110" }, headers: { origin, host: "localhost:3210" } });
      expect(response.status, origin).toBe(403);
      expect((await response.json()).error.code, origin).toBe("cross_origin");
      expect(upstream, origin).not.toHaveBeenCalled();
    }
  });

  it("lets a write from the site's own origin through", async () => {
    const response = await call("POST", "v1/quant/convert", { body: { odds: "-110" }, headers: { origin: SITE, host: "localhost:3210" } });
    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(1);
  });
});

describe("the /api/ov bridge and a session the API no longer accepts", () => {
  it("clears the cookie and asks again without the token, so a public route still answers", async () => {
    upstream.mockImplementationOnce(async () => apiError(401, "invalid_token", "The access token is invalid or has expired"));
    upstream.mockImplementationOnce(async () => json(200, { answer: "Expected value is ..." }));
    const response = await call("POST", "v1/assistant/query", { cookie: "revoked", body: { message: "What is expected value?" } });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ answer: "Expected value is ..." });
    expect(clearsSession(response)).toBe(true);
    expect(upstream).toHaveBeenCalledTimes(2);
    expect(authorization(0)).toBe("Bearer revoked");
    expect(authorization(1)).toBeUndefined();
    expect(sent(1).url).toBe(`${API_URL}/v1/assistant/query`);
    expect(sent(1).init.method).toBe("POST");
    expect(sent(1).init.body).toBe(JSON.stringify({ message: "What is expected value?" }));
  });

  it("clears the cookie and answers as signed out on a route that needs an account", async () => {
    upstream.mockImplementationOnce(async () => apiError(401, "invalid_token"));
    upstream.mockImplementationOnce(async () => apiError(401, "not_authenticated", "Authentication is required"));
    const response = await call("GET", "v1/bets", { cookie: "revoked" });
    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe("not_authenticated");
    expect(clearsSession(response)).toBe(true);
    expect(upstream).toHaveBeenCalledTimes(2);
  });

  it("still clears the cookie when the second call cannot reach the API", async () => {
    upstream.mockImplementationOnce(async () => apiError(401, "invalid_token"));
    upstream.mockImplementationOnce(async () => {
      throw new TypeError("fetch failed");
    });
    const response = await call("GET", "v1/assistant/query", { cookie: "revoked" });
    expect(response.status).toBe(503);
    expect((await response.json()).error.code).toBe("api_unavailable");
    expect(clearsSession(response)).toBe(true);
  });

  it("clears the cookie of a suspended account and does not ask again", async () => {
    upstream.mockImplementationOnce(async () => apiError(401, "account_suspended", "This account is suspended"));
    const response = await call("GET", "v1/bets", { cookie: "suspended" });
    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe("account_suspended");
    expect(clearsSession(response)).toBe(true);
    expect(upstream).toHaveBeenCalledTimes(1);
  });

  it("leaves a working session alone", async () => {
    for (const reply of [json(200, { ok: true }), apiError(403, "forbidden"), apiError(404, "not_found"), apiError(422, "validation_error", "invalid_token"), apiError(401, "not_authenticated"), apiError(500, "invalid_token")]) {
      upstream.mockReset();
      upstream.mockImplementationOnce(async () => reply);
      const response = await call("GET", "v1/bets", { cookie: "good" });
      expect(response.headers.get("set-cookie"), String(reply.status)).toBeNull();
      expect(upstream).toHaveBeenCalledTimes(1);
    }
  });

  it("sets no cookie for a visitor who has none", async () => {
    upstream.mockImplementationOnce(async () => apiError(401, "invalid_token"));
    const response = await call("GET", "v1/bets");
    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(upstream).toHaveBeenCalledTimes(1);
  });
});
