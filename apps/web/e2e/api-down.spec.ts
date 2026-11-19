import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { expect, test } from "./fixtures";

/**
 * What a visitor sees while the API is down. The suite's own web server talks to a running
 * API, so this spec starts a second copy of the same production build that points at an
 * address where nothing listens. It must be the production build: a development render sends
 * the browser the error's name and message, which a production render never does.
 */
const PORT = 3211;
const SITE = `http://localhost:${PORT}`;
const UNREACHABLE_API = "http://127.0.0.1:1";
const WEB_ROOT = path.resolve(__dirname, "..");
const SESSION_COOKIE = "ov_session";

let server: ChildProcess | undefined;

test.describe("with the API unreachable", () => {
  test.beforeAll(async () => {
    // A copy left over from an interrupted run would be an older build answering in its place.
    expect(await fetch(`${SITE}/login`).then(() => true, () => false), `nothing is listening on port ${PORT} yet`).toBe(false);
    server = spawn("node", [path.join(".next", "standalone", "apps", "web", "server.js")], {
      cwd: WEB_ROOT,
      env: { ...process.env, NODE_ENV: "production", PORT: String(PORT), HOSTNAME: "localhost", ODDVEX_API_URL: UNREACHABLE_API, ODDVEX_INSECURE_COOKIES: "true" },
      stdio: "ignore",
    });
    await expect
      .poll(() => fetch(`${SITE}/login`).then((response) => response.status, () => 0), { message: "second web server is up", timeout: 30_000 })
      .toBe(200);
  });

  test.afterAll(async () => {
    // Wait until the process is gone: a retry starts by checking that the port is free.
    const running = server;
    server = undefined;
    if (!running || running.exitCode !== null || running.signalCode !== null) return;
    const gone = new Promise<void>((resolve) => running.once("exit", () => resolve()));
    running.kill();
    await gone;
  });

  test("an app screen says it can't reach the data service, with the request id as the reference", async ({ page }) => {
    await page.setExtraHTTPHeaders({ "x-request-id": "e2e-api-down-0001" });
    await page.goto(`${SITE}/app/games`);
    const alert = page.getByRole("main").getByRole("alert");
    await expect(alert.getByRole("heading", { level: 1 })).toHaveText("OddVex can't reach its data service");
    await expect(alert).toContainText("Nothing is wrong with your account. The data service is not responding, so there are no prices to show.");
    await expect(alert.getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(alert.getByText("Reference e2e-api-down-0001", { exact: true })).toBeVisible();
    await expect(page.getByText("This screen failed to load")).toHaveCount(0);
  });

  test("every public app screen shows the same message", async ({ page }) => {
    for (const screen of ["/app/games", "/app/odds", "/app/props", "/app/parlay"]) {
      await page.goto(`${SITE}${screen}`);
      await expect(page.getByRole("heading", { level: 1 }), screen).toHaveText("OddVex can't reach its data service");
    }
  });

  test("nothing about the failure but its kind and the request id is sent to the browser", async ({ request }) => {
    const response = await request.get(`${SITE}/app/games`, { headers: { "x-request-id": "e2e-api-down-0002" } });
    const html = await response.text();
    expect(html).toContain("api_unavailable:e2e-api-down-0002");
    expect(html).not.toContain("ApiUnavailableError");
    expect(html).not.toMatch(/not reachable/i);
    expect(html).not.toContain("127.0.0.1");
    expect(html).not.toMatch(/ECONNREFUSED|fetch failed|node:internal|\.next\/server/);
  });

  test("a visitor sent to have a dead session cleared ends on the login page, not in a circle", async ({ page, request }) => {
    // A page sends a visitor to /api/session/ended?next=<itself> when the API rejects the
    // token. If that route cannot get an answer it must not send them back with the cookie
    // still set: the page would send them here again.
    const cookie = `${SESSION_COOKIE}=a-token-nobody-can-check`;
    const hop = await request.get(`${SITE}/api/session/ended?next=/app/tools`, { headers: { cookie }, maxRedirects: 0 });
    expect(hop.status()).toBe(307);
    expect(hop.headers().location).toBe("/login");
    expect(hop.headers()["set-cookie"]).toBeUndefined();

    await page.context().addCookies([{ name: SESSION_COOKIE, value: "a-token-nobody-can-check", url: SITE }]);
    await page.goto(`${SITE}/api/session/ended?next=/app/tools`);
    await expect(page).toHaveURL(`${SITE}/login`);
    await expect(page.getByRole("heading", { level: 1, name: "Log in" })).toBeVisible();
    // The session was not ended on a guess: the cookie is still there.
    expect((await page.context().cookies(SITE)).find((entry) => entry.name === SESSION_COOKIE)?.value).toBe("a-token-nobody-can-check");
  });

  test("the bridge answers 503 with the same wording", async ({ request }) => {
    const response = await request.get(`${SITE}/api/ov/v1/events`);
    expect(response.status()).toBe(503);
    expect((await response.json()).error).toEqual({ code: "api_unavailable", message: "OddVex can't reach its data service right now. Try again in a moment." });
  });
});
