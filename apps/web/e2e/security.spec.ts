import { readdirSync } from "node:fs";
import path from "node:path";
import type { APIRequestContext, BrowserContext } from "@playwright/test";
import { expect, test, type Page } from "./fixtures";
import { adminSignIn, logIn, openMoreOnPhone, PASSWORD, signUp } from "./helpers";

const API = "http://localhost:8210";
const SESSION_COOKIE = "ov_session";

function directives(csp: string | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of (csp ?? "").split(";")) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (name) out[name] = values.join(" ");
  }
  return out;
}

const FIXED: Record<string, string> = {
  "default-src": "'self'",
  "style-src": "'self'",
  "img-src": "'self' data:",
  "font-src": "'self'",
  "connect-src": "'self'",
  "object-src": "'none'",
  "base-uri": "'self'",
  "form-action": "'self'",
  "frame-ancestors": "'none'",
};

test.describe("security headers", () => {
  test("a marketing page allows its inline scripts by hash only", async ({ request }) => {
    const response = await request.get("/");
    const headers = response.headers();
    const csp = directives(headers["content-security-policy"]);
    for (const [name, value] of Object.entries(FIXED)) expect(csp[name], name).toBe(value);
    expect(csp["script-src"]).toMatch(/^'self'( 'sha256-[A-Za-z0-9+/]+=*')+$/);
    expect(headers["content-security-policy"]).not.toMatch(/unsafe-eval|nonce-/);
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-request-id"]).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
    // The suite serves the production build over http (ODDVEX_INSECURE_COOKIES=true), where HSTS must not be sent.
    expect(headers["strict-transport-security"]).toBeUndefined();
  });

  test("an app page allows its scripts by a fresh nonce on every request", async ({ request }) => {
    const nonces = new Set<string>();
    for (const path of ["/app", "/app", "/login"]) {
      const response = await request.get(path);
      const csp = directives(response.headers()["content-security-policy"]);
      for (const [name, value] of Object.entries(FIXED)) expect(csp[name], `${path} ${name}`).toBe(value);
      const nonce = /'nonce-([A-Za-z0-9+/=]+)'/.exec(csp["script-src"])?.[1];
      expect(nonce, path).toBeTruthy();
      nonces.add(nonce!);
      expect(csp["script-src"]).not.toMatch(/unsafe-inline|unsafe-eval/);
      // Next.js put the same nonce on the scripts it rendered.
      expect(await response.text()).toContain(`nonce="${nonce}"`);
    }
    expect(nonces.size).toBe(3);
  });

  test("the policy really blocks an injected inline script", async ({ page, cspViolations }) => {
    for (const path of ["/", "/app/tools"]) {
      await page.goto(path);
      const ran = await page.evaluate(() => {
        const script = document.createElement("script");
        script.textContent = "window.__injected = true";
        document.head.appendChild(script);
        return (window as unknown as { __injected?: boolean }).__injected === true;
      });
      expect(ran, path).toBe(false);
    }
    await expect.poll(() => cspViolations.length).toBeGreaterThanOrEqual(2);
    cspViolations.length = 0; // provoked on purpose
  });

  test("no page reports a violation, signed out", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    const props = await (await request.get(`${API}/v1/props`)).json();
    const paths = [
      "/", "/help", "/blog/removing-the-vig", "/design", "/no-such-page", "/app/no-such-page", "/login", "/signup", "/forgot-password",
      "/app", `/app/games/${events[0].id}`, `/app/props/${props[0].player.id}`, "/app/tools", "/app/tracker", "/app/value", "/app/tracker/analytics",
    ];
    for (const path of paths) {
      await page.goto(path);
      await expect(page.locator("h1")).toHaveCount(1);
      // Hydration ran: without it React never attaches, and nothing on the page would respond.
      await expect
        .poll(() => page.evaluate(() => Object.keys(document.querySelector("h1") ?? {}).some((key) => key.startsWith("__react"))), { message: `${path} hydrated` })
        .toBe(true);
    }
    // The auto fixture fails this test if any of the pages above logged a violation.
  });

  test("no violation while signed in, switching theme and odds format", async ({ page }) => {
    const email = `e2e-csp-${Date.now()}-${Math.floor(Math.random() * 1e6)}@oddvex.test`;
    await page.goto("/signup?next=/app/tracker");
    await page.getByLabel("Name").fill("Casey Tester");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
    for (const path of ["/app/tracker", "/app", "/app/alerts", "/app/settings"]) {
      await page.goto(path);
      await expect(page.locator("h1")).toHaveCount(1);
    }
    const main = page.getByRole("main");
    await main.getByRole("button", { name: /theme\. Switch to light/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await main.getByRole("button", { name: "Decimal" }).click();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light"); // the inline theme script ran
    await expect(main.getByRole("button", { name: "Decimal" })).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("request id", () => {
  test("the API bridge reuses a well-formed id and replaces a malformed one", async ({ request }) => {
    const kept = await request.get("/api/ov/v1/events", { headers: { "x-request-id": "e2e-request-id-0001" } });
    expect(kept.status()).toBe(200);
    expect(kept.headers()["x-request-id"]).toBe("e2e-request-id-0001");
    const replaced = await request.get("/api/ov/v1/events", { headers: { "x-request-id": "bad id" } });
    expect(replaced.headers()["x-request-id"]).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
    expect(replaced.headers()["x-request-id"]).not.toBe("bad id");
    const refused = await request.get("/api/ov/v1/admin/overview", { headers: { "x-request-id": "e2e-request-id-0002" } });
    expect(refused.status()).toBe(404);
    expect(refused.headers()["x-request-id"]).toBe("e2e-request-id-0002");
  });

  test("pages answer with the id they were given", async ({ request }) => {
    const response = await request.get("/app", { headers: { "x-request-id": "e2e-request-id-0003" } });
    expect(response.headers()["x-request-id"]).toBe("e2e-request-id-0003");
  });
});

test.describe("not-found status", () => {
  test("an unknown app path is a 404", async ({ page }) => {
    expect((await page.goto("/app/no-such-screen"))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
  });
});

/** No test may reach a real outside host: anything addressed to the stand-in is answered here. */
async function trapOffSite(context: BrowserContext) {
  await context.route(/^https?:\/\/([^/]*\.)?evil\.example/, (route) => route.fulfill({ status: 200, contentType: "text/html", body: "<h1>off-site</h1>" }));
}

/** Values for `?next=` that a browser would resolve to another site if they were used as a redirect target. */
const OFF_SITE_NEXT = [
  "/%09/evil.example", // the audit finding: a tab after the first slash
  "/%0A/evil.example",
  "/%0D/evil.example",
  "//evil.example",
  "/%5Cevil.example",
  "%5C%5Cevil.example",
  "/.//evil.example",
  "%20//evil.example",
  "https://evil.example",
  "/%252F/evil.example", // decodes to /%2F/evil.example: on the site, but refused all the same
];

test.describe("redirect targets", () => {
  test("the login and signup pages replace an off-site destination with the app home", async ({ request }) => {
    for (const page of ["/login", "/signup"]) {
      for (const next of OFF_SITE_NEXT) {
        const response = await request.get(`${page}?next=${next}`);
        expect(response.status(), `${page} ${next}`).toBe(200);
        const html = await response.text();
        expect(html, `${page} ${next}`).toMatch(/<input[^>]*name="next"[^>]*value="\/app"/);
        // The link to the other form carries the destination on; it must be the replaced one.
        expect(html, `${page} ${next}`).toMatch(/href="\/(login|signup)\?next=%2Fapp"/);
        expect(html, `${page} ${next}`).not.toMatch(/(value|href)="[^"]*evil\.example/);
      }
      // A repeated parameter reaches the page as a list, which must not break it.
      const repeated = await request.get(`${page}?next=/app/tracker&next=//evil.example`);
      expect(repeated.status(), page).toBe(200);
      expect(await repeated.text(), page).toMatch(/<input[^>]*name="next"[^>]*value="\/app"/);
      // A same-site destination is kept.
      expect(await (await request.get(`${page}?next=/app/tracker?x=1`)).text(), page).toMatch(/<input[^>]*name="next"[^>]*value="\/app\/tracker\?x=1"/);
    }
  });

  test("signing in from a crafted link stays on the site", async ({ page, context, baseURL }) => {
    await trapOffSite(context);
    const email = await signUp(page, "next");
    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.goto("/login?next=/%09/evil.example");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
    expect(page.url()).toBe(`${baseURL}/app`);
  });

  test("the sign-in action checks the destination itself, whatever the form sends", async ({ page, context, baseURL }) => {
    await trapOffSite(context);
    const email = await signUp(page, "nextform");
    for (const next of ["/\t/evil.example", "/\n/evil.example", "//evil.example", "/\\evil.example", "/.//evil.example", "https://evil.example"]) {
      await page.getByRole("button", { name: "Log out", exact: true }).click();
      await expect(page).toHaveURL(/\/$/);
      await page.goto("/login");
      await page.getByLabel("Email").fill(email);
      await page.getByLabel("Password").fill(PASSWORD);
      await page.locator('input[name="next"]').evaluate((input, value) => ((input as HTMLInputElement).value = value), next);
      await page.getByRole("button", { name: "Log in" }).click();
      await expect(page.getByRole("button", { name: "Log out", exact: true }), JSON.stringify(next)).toBeVisible();
      expect(page.url(), JSON.stringify(next)).toBe(`${baseURL}/app`);
    }
  });
});

/** Ways to name a path the bridge must not forward. Each is sent exactly as written. */
const BRIDGE_BYPASSES = [
  "v1/me%2F..%2Fadmin%2Fusers", // encoded slash (the audit finding)
  "v1/me/..%2Fadmin/users", // one encoded slash among plain ones
  "v1/me/%252e%252e/admin/users", // double-encoded dots
  "v1/me/%252E%252E%252Fadmin%252Fusers", // double-encoded dots and slashes
  "v1/me/..%5Cadmin/users", // backslash
  "v1/me%5C..%5Cadmin%5Cusers",
  "v1/community%2F..%2Fadmin%2Fusers",
  "v1/flags%2F..%2F..%2Fhealth", // out of /v1 altogether
  "v1/flags/%252e%252e/%252e%252e/health",
  "v1/me%2F..%2Fauth%2Flogin", // the sign-in route
  "v1/me%3F/../admin/users", // an encoded question mark
  "v1%2Fadmin%2Fusers",
];

test.describe("API bridge allow-list", () => {
  test("no encoding of a path gets an administrator's browser to a route that is not listed", async ({ page, request }) => {
    await adminSignIn(page);
    // The session really is an administrator's: the API itself would answer these.
    const token = (await page.context().cookies()).find((cookie) => cookie.name === SESSION_COOKIE)?.value ?? "";
    expect((await request.get(`${API}/v1/admin/users`, { headers: { authorization: `Bearer ${token}` } })).status()).toBe(200);

    for (const path of BRIDGE_BYPASSES) {
      const read = await page.request.get(`/api/ov/${path}`);
      expect(read.status(), `GET ${path}`).toBe(404);
      // The bridge's own answer, not the API's: nothing was forwarded.
      expect((await read.json()).error, `GET ${path}`).toEqual({ code: "not_found", message: "Unknown route." });
    }
    for (const path of ["v1/me%2F..%2Fadmin%2Fflags%2Fcommunity", "v1/me/%252e%252e/admin/flags/community", "v1/me/..%5Cadmin/flags/community"]) {
      // Writes the value the flag already has, so a forwarded call would change nothing either.
      const write = await page.request.put(`/api/ov/${path}`, { data: { enabled: false } });
      expect(write.status(), `PUT ${path}`).toBe(404);
      expect((await write.json()).error, `PUT ${path}`).toEqual({ code: "not_found", message: "Unknown route." });
    }
    const signIn = await page.request.post("/api/ov/v1/me%2F..%2Fauth%2Flogin", { data: { email: "demo@oddvex.test", password: "wrong-password-0000" } });
    expect(signIn.status()).toBe(404);
    expect((await signIn.json()).error).toEqual({ code: "not_found", message: "Unknown route." });

    // Listed paths still work, with an encoded character in a segment or not.
    expect((await page.request.get("/api/ov/v1/me")).status()).toBe(200);
    expect((await page.request.get("/api/ov/v1/%6De")).status()).toBe(200);
    expect((await page.request.get("/api/ov/v1/events?status=upcoming")).status()).toBe(200);
  });
});

/** Every file under the running server's build output, which is where Next.js stores rendered pages. */
function serverFiles(): string[] {
  const root = path.resolve(__dirname, "..", ".next", "standalone", "apps", "web", ".next");
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else out.push(path.relative(root, full));
    }
  };
  walk(root);
  return out.sort();
}

test.describe("addresses that do not exist", () => {
  test("an unknown blog post is a 404 that is neither cached nor written to disk", async ({ request }) => {
    const before = serverFiles();
    const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    for (const slug of [`no-such-post-${stamp}`, `no-such-post-${stamp}-2`, `no-such-post-${stamp}-${"x".repeat(200)}`, "removing-the-vig-2", "Removing-The-Vig"]) {
      for (let attempt = 0; attempt < 2; attempt++) {
        const response = await request.get(`/blog/${slug}`);
        expect(response.status(), slug).toBe(404);
        const headers = response.headers();
        expect(headers["cache-control"] ?? "", slug).toContain("no-store");
        expect(headers["cache-control"] ?? "", slug).not.toMatch(/s-maxage|public/);
        // The prerendered not-found page is a hit. A miss is a page rendered and stored just now.
        expect(headers["x-nextjs-cache"], slug).not.toBe("MISS");
        expect(await response.text(), slug).toContain("off the board");
      }
    }
    // The same address asked for as page data, the way the router fetches and prefetches it.
    const dataRequests: Record<string, string>[] = [{ rsc: "1" }, { rsc: "1", "next-router-prefetch": "1" }, { rsc: "1", "next-router-prefetch": "1", "next-router-segment-prefetch": "/_tree" }];
    for (const headers of dataRequests) {
      const response = await request.get(`/blog/no-such-post-${stamp}-data`, { headers });
      expect(response.status(), JSON.stringify(headers)).toBe(404);
      expect(response.headers()["x-nextjs-cache"], JSON.stringify(headers)).not.toBe("MISS");
    }
    expect((await request.get(`/blog/no-such-post-${stamp}.rsc`)).status()).toBe(404);
    expect(serverFiles(), "files under the server's build output").toEqual(before);
    // The posts that exist are still there.
    expect((await request.get("/blog/removing-the-vig")).status()).toBe(200);
    expect((await request.get("/blog")).status()).toBe(200);
  });

  test("no other public address with a made-up id is stored either", async ({ request }) => {
    const before = serverFiles();
    const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    for (const address of [
      `/app/games/no-such-game-${stamp}`,
      `/app/props/no-such-player-${stamp}`,
      `/app/community/picks/no-such-pick-${stamp}`,
      `/app/community/profiles/no_such_handle_${stamp}`,
      `/no-such-page-${stamp}`,
      `/app/no-such-screen-${stamp}`,
      `/help/no-such-topic-${stamp}`,
      `/blog/removing-the-vig/no-such-part-${stamp}`,
      `/login?next=/app/x-${stamp}`,
      `/?made-up=${stamp}`,
    ]) {
      // A miss is a page that was just rendered and put into the cache.
      expect((await request.get(address)).headers()["x-nextjs-cache"], address).not.toBe("MISS");
    }
    expect(serverFiles(), "files under the server's build output").toEqual(before);
  });

  test("the not-found page of an unknown blog post runs under the policy", async ({ page }) => {
    expect((await page.goto(`/blog/no-such-post-${Date.now()}`))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    await expect
      .poll(() => page.evaluate(() => Object.keys(document.querySelector("h1") ?? {}).some((key) => key.startsWith("__react"))), { message: "hydrated" })
      .toBe(true);
    // The auto fixture fails this test if the page logged a Content-Security-Policy violation.
  });
});

/** Ends every session of the signed-in account at the API, as logging out on another device does. The browser keeps its cookie. */
async function revokeElsewhere(page: Page, request: APIRequestContext): Promise<string> {
  const token = (await page.context().cookies()).find((cookie) => cookie.name === SESSION_COOKIE)?.value ?? "";
  expect(token).not.toBe("");
  expect((await request.post(`${API}/v1/auth/logout`, { headers: { authorization: `Bearer ${token}` } })).ok()).toBe(true);
  expect((await request.get(`${API}/v1/me`, { headers: { authorization: `Bearer ${token}` } })).status()).toBe(401);
  return token;
}

const sessionCookie = async (page: Page) => (await page.context().cookies()).find((cookie) => cookie.name === SESSION_COOKIE)?.value;

test.describe("a session the API has ended", () => {
  test("the assistant still answers, and the dead cookie is cleared", async ({ page, request }) => {
    await signUp(page, "dead-assistant");
    await page.goto("/app/assistant");
    await revokeElsewhere(page, request);

    await page.getByRole("button", { name: "What is expected value?" }).click();
    await expect(page.getByText("OddVex AI answered:")).toBeAttached();
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    await expect(page.getByText("The access token is invalid or has expired")).toHaveCount(0);
    expect(await sessionCookie(page)).toBeUndefined();
  });

  test("the bridge clears the cookie and answers a public route as signed out", async ({ page, request }) => {
    await signUp(page, "dead-bridge");
    await revokeElsewhere(page, request);

    const asked = await page.request.post("/api/ov/v1/assistant/query", { data: { message: "What is expected value?" } });
    expect(asked.status()).toBe(200);
    expect((await asked.json()).answer).toBeTruthy();
    expect(asked.headers()["set-cookie"]).toMatch(/^ov_session=;/);
    expect(await sessionCookie(page)).toBeUndefined();

    // Signed out now: a route that needs an account says so, and a public one works.
    const bets = await page.request.get("/api/ov/v1/bets");
    expect(bets.status()).toBe(401);
    expect((await bets.json()).error.code).toBe("not_authenticated");
    expect((await page.request.get("/api/ov/v1/events")).status()).toBe(200);
  });

  test("a route that needs an account answers as signed out and clears the cookie", async ({ page, request }) => {
    await signUp(page, "dead-bets");
    await revokeElsewhere(page, request);
    const bets = await page.request.get("/api/ov/v1/bets");
    expect(bets.status()).toBe(401);
    expect((await bets.json()).error.code).toBe("not_authenticated");
    expect(await sessionCookie(page)).toBeUndefined();
  });

  test("a page comes back to the same address, signed out, with the cookie cleared", async ({ page, request, baseURL }) => {
    await signUp(page, "dead-page");
    await revokeElsewhere(page, request);

    const address = "/app/games?league=nba&q=a+b";
    const response = await page.goto(address);
    expect(response?.status()).toBe(200);
    expect(page.url()).toBe(`${baseURL}${address}`);
    expect(response?.request().redirectedFrom()?.url()).toContain("/api/session/ended?next=");
    // One trip there and back, and no more.
    expect(response?.request().redirectedFrom()?.redirectedFrom()?.url()).toBe(`${baseURL}${address}`);
    expect(response?.request().redirectedFrom()?.redirectedFrom()?.redirectedFrom()).toBeNull();
    await expect(page.getByRole("banner").getByRole("link", { name: "Log in", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toHaveCount(0);
    expect(await sessionCookie(page)).toBeUndefined();

    // Public screens keep working, and so does the assistant.
    await page.goto("/app/assistant");
    await page.getByRole("button", { name: "What is expected value?" }).click();
    await expect(page.getByText("OddVex AI answered:")).toBeAttached();
  });

  test("a page with a very long address still opens, signed out", async ({ page, request, baseURL }) => {
    await signUp(page, "dead-long");
    const token = await revokeElsewhere(page, request);

    // Carried in ?next= this query would be three times as long, more than a server accepts
    // in a request (431). The page is shown signed out instead, without the trip.
    const address = `/app/games?league=nba&q=${"%2F".repeat(3400)}`;
    const response = await page.goto(address);
    expect(response?.status()).toBe(200);
    expect(response?.request().redirectedFrom()).toBeNull();
    expect(page.url()).toBe(`${baseURL}${address}`);
    await expect(page.getByRole("banner").getByRole("link", { name: "Log in", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toHaveCount(0);
    expect(await sessionCookie(page)).toBe(token);

    // The next ordinary request clears the cookie.
    await page.goto("/app/tools");
    await expect(page).toHaveURL(/\/app\/tools$/);
    expect(await sessionCookie(page)).toBeUndefined();
  });

  test("moving to another screen inside the app clears the cookie too", async ({ page, request }) => {
    await signUp(page, "dead-nav");
    await page.goto("/app");
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
    await revokeElsewhere(page, request);

    await openMoreOnPhone(page);
    await page.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Tracker", exact: true }).filter({ visible: true }).first().click();
    await expect(page.getByText("Log in to track your bets")).toBeVisible();
    await expect(page).toHaveURL(/\/app\/tracker$/);
    expect(await sessionCookie(page)).toBeUndefined();
  });

  test("opening a game or a player from a list clears the cookie too", async ({ page, request }) => {
    const email = await signUp(page, "dead-detail");
    for (const [list, detail] of [
      ["/app/games", /\/app\/games\/[^/?]+$/],
      ["/app/props", /\/app\/props\/[^/?]+/],
    ] as const) {
      await page.goto(list);
      await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
      await revokeElsewhere(page, request);
      await page.getByRole("main").locator(`a[href^="${list}/"]`).first().click();
      await expect(page, list).toHaveURL(detail);
      await expect(page.getByRole("banner").getByRole("link", { name: "Log in", exact: true }), list).toBeVisible();
      expect(await sessionCookie(page), list).toBeUndefined();
      await logIn(page, email, PASSWORD);
    }
  });

  test("a form sent with a dead cookie clears it", async ({ page, request }) => {
    await signUp(page, "dead-form");
    await page.goto("/app/settings");
    await revokeElsewhere(page, request);

    await page.getByLabel("Current password").fill(PASSWORD);
    await page.getByLabel("New password", { exact: true }).fill("another-horse-battery");
    await page.getByRole("button", { name: "Change password" }).click();
    await expect.poll(() => sessionCookie(page)).toBeUndefined();
    await page.goto("/app/settings");
    await expect(page.getByText("You are not logged in.")).toBeVisible();
  });

  test("the admin section answers 404 and clears the cookie", async ({ page, request }) => {
    await signUp(page, "dead-admin");
    await revokeElsewhere(page, request);
    expect((await page.goto("/app/admin/users"))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    expect(await sessionCookie(page)).toBeUndefined();
  });

  test("the session-ended address leaves a working session alone and never leaves the site", async ({ page, context, request, baseURL }) => {
    await trapOffSite(context);
    await signUp(page, "alive");
    const token = await sessionCookie(page);

    await page.goto("/api/session/ended?next=/app/settings");
    await expect(page).toHaveURL(/\/app\/settings$/);
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
    for (const next of OFF_SITE_NEXT) {
      await page.goto(`/api/session/ended?next=${next}`);
      expect(page.url(), next).toBe(`${baseURL}/app`);
    }
    expect(await sessionCookie(page)).toBe(token);

    // Signed out: back to the page that was named, or to the login page.
    const back = await request.get("/api/session/ended?next=/app/tools", { maxRedirects: 0 });
    expect(back.status()).toBe(307);
    expect(back.headers().location).toBe("/app/tools");
    for (const next of OFF_SITE_NEXT) {
      const refused = await request.get(`/api/session/ended?next=${next}`, { maxRedirects: 0 });
      expect(refused.status(), next).toBe(307);
      expect(refused.headers().location, next).toBe("/login");
    }
    expect((await request.get("/api/session/ended", { maxRedirects: 0 })).headers().location).toBe("/login");

    // Asked for with fetch, as the router does on a move inside the app: no redirect to follow, so the router loads it as a page.
    const fetched = await page.request.get("/api/session/ended?next=/app/tools", { headers: { "sec-fetch-dest": "empty" }, maxRedirects: 0 });
    expect(fetched.status()).toBe(200);
    expect(fetched.headers()["content-type"]).toContain("text/plain");
    expect(fetched.headers()["set-cookie"]).toBeUndefined();
    expect(await sessionCookie(page)).toBe(token);
  });
});
