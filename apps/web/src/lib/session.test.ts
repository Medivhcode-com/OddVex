import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, ApiUnavailableError } from "@/lib/api";
import { API_URL, PAGE_PATH_HEADER, SESSION_COOKIE } from "@/lib/config";
import { currentUser, SESSION_ENDED_PATH } from "@/lib/session";

/**
 * `currentUser()` with the request it runs in replaced by a stub: a cookie jar, the request
 * headers, and the upstream API. `redirect()` is the real one from Next.js.
 */
const upstream = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();
vi.stubGlobal("fetch", upstream);

const request = vi.hoisted(() => ({
  jar: new Map<string, string>(),
  headers: new Headers(),
  /** A page render may read cookies but not change them; a server action may do both. */
  mayChangeCookies: false,
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  headers: async () => request.headers,
  cookies: async () => ({
    get: (name: string) => (request.jar.has(name) ? { name, value: request.jar.get(name) } : undefined),
    delete: (name: string) => {
      if (!request.mayChangeCookies) throw new Error("Cookies can only be modified in a Server Action or Route Handler.");
      request.jar.delete(name);
    },
  }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const apiError = (status: number, code: string) => json(status, { error: { code, message: code } });

/** Where `currentUser()` redirected to, or the value it returned. */
async function outcome(): Promise<{ redirect: string } | { user: unknown }> {
  try {
    return { user: await currentUser() };
  } catch (error) {
    const digest = (error as { digest?: unknown }).digest;
    if (typeof digest === "string" && digest.startsWith("NEXT_REDIRECT;")) return { redirect: digest.split(";")[2] };
    throw error;
  }
}

function onPage(pagePath: string | null, token: string | null = "revoked") {
  request.headers = new Headers(pagePath === null ? {} : { [PAGE_PATH_HEADER]: pagePath });
  request.jar = new Map(token === null ? [] : [[SESSION_COOKIE, token]]);
  request.mayChangeCookies = false;
}

beforeEach(() => {
  upstream.mockReset();
  onPage("/app/games?league=nba");
});

describe("currentUser", () => {
  it("is null without a cookie, and the API is not asked", async () => {
    onPage("/app/games", null);
    expect(await outcome()).toEqual({ user: null });
    expect(upstream).not.toHaveBeenCalled();
  });

  it("is the account the API returns for the cookie's token", async () => {
    onPage("/app/games", "good");
    upstream.mockImplementation(async () => json(200, { id: "usr_1", role: "user" }));
    expect(await outcome()).toEqual({ user: { id: "usr_1", role: "user" } });
    expect(upstream.mock.calls[0][0]).toBe(`${API_URL}/v1/me`);
    expect((upstream.mock.calls[0][1].headers as Record<string, string>).authorization).toBe("Bearer good");
  });

  it("sends a page whose token the API rejects to have the cookie cleared, naming the page to come back to", async () => {
    upstream.mockImplementation(async () => apiError(401, "invalid_token"));
    expect(await outcome()).toEqual({ redirect: `${SESSION_ENDED_PATH}?next=${encodeURIComponent("/app/games?league=nba")}` });
    expect(request.jar.get(SESSION_COOKIE)).toBe("revoked");
  });

  it("reads as signed out, without a redirect, when the page to come back to is unknown or unusable", async () => {
    upstream.mockImplementation(async () => apiError(401, "invalid_token"));
    for (const pagePath of [null, "", "//evil.example", "/\t/evil.example", "https://evil.example", "/%2F/evil.example", `/app/games?q=${"%2F".repeat(3400)}`]) {
      onPage(pagePath);
      expect(await outcome(), String(pagePath).slice(0, 40)).toEqual({ user: null });
    }
  });

  it("in a server action, drops the cookie on the spot and redirects nobody", async () => {
    request.mayChangeCookies = true;
    upstream.mockImplementation(async () => apiError(401, "invalid_token"));
    expect(await outcome()).toEqual({ user: null });
    expect(request.jar.has(SESSION_COOKIE)).toBe(false);
  });

  it("sends a suspended account to be signed out, to the login page", async () => {
    upstream.mockImplementation(async () => apiError(401, "account_suspended"));
    expect(await outcome()).toEqual({ redirect: SESSION_ENDED_PATH });
  });

  it("reads any other 401 or 403 as signed out and leaves the cookie", async () => {
    for (const reply of [() => apiError(401, "not_authenticated"), () => apiError(403, "forbidden"), () => apiError(403, "invalid_token")]) {
      request.mayChangeCookies = true;
      upstream.mockImplementation(async () => reply());
      expect(await outcome()).toEqual({ user: null });
      expect(request.jar.get(SESSION_COOKIE)).toBe("revoked");
    }
  });

  it("passes on an API failure, which is not an answer about the session", async () => {
    upstream.mockImplementation(async () => apiError(500, "invalid_token"));
    await expect(outcome()).rejects.toBeInstanceOf(ApiError);
    upstream.mockImplementation(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(outcome()).rejects.toBeInstanceOf(ApiUnavailableError);
    expect(request.jar.get(SESSION_COOKIE)).toBe("revoked");
  });
});
