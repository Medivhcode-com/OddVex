import { expect, test } from "./fixtures";

const API = "http://localhost:8210";

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
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
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
