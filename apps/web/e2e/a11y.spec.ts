import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";
import { adminSignIn, logIn } from "./helpers";

const API = "http://localhost:8210";

/**
 * Automated accessibility checks (WCAG 2.2 A and AA rules that axe can evaluate).
 * This catches contrast, naming and structure regressions. It does not replace a manual screen reader pass.
 */
async function audit(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

const STATIC = [
  "/", "/pricing", "/features", "/methodology", "/help", "/privacy", "/terms", "/responsible-gambling", "/login", "/signup", "/forgot-password",
  "/reset-password?token=not-a-real-token-0000", "/verify-email?token=not-a-real-token-0000", "/login?suspended=1", "/design",
  "/app/tools", "/app/parlay", "/app/tracker", "/app/assistant", "/app/settings", "/app/alerts",
  "/app/value", "/app/value?league=nba&market=spread&min_edge=0.05", "/app/tracker/analytics",
];

for (const theme of ["dark", "light"] as const) {
  test.describe(`accessibility, ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => {
        try {
          localStorage.setItem("ov-theme", value);
          localStorage.setItem("ov-autorefresh", "off");
        } catch {}
      }, theme);
    });

    for (const path of STATIC) {
      test(`${path} has no detectable WCAG A/AA violations`, async ({ page }) => {
        await page.goto(path);
        expect(await audit(page)).toEqual([]);
      });
    }

    test("signed-in value, analytics and settings have no detectable WCAG A/AA violations", async ({ page }) => {
      // The demo account has settled bets, so every analytics table and bar is on the page.
      await logIn(page, "demo@oddvex.test", "oddvex-demo-2026", "/app/tracker/analytics");
      for (const path of ["/app/tracker/analytics", "/app/value", "/app/tracker", "/app/settings"]) {
        await page.goto(path);
        await expect(page.locator("h1")).toHaveCount(1);
        expect(await audit(page), path).toEqual([]);
      }
    });

    test("admin tabs have no detectable WCAG A/AA violations", async ({ page }) => {
      await adminSignIn(page);
      for (const path of ["/app/admin", "/app/admin/users", "/app/admin/flags", "/app/admin/audit", "/app/admin/outbox"]) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
        expect(await audit(page), path).toEqual([]);
      }
      // The confirm steps, open: a flag with a warning, and a suspension with its reason field.
      await page.goto("/app/admin/flags");
      await page.getByRole("button", { name: "Turn on community", exact: true }).click();
      await expect(page.getByText("Review required first")).toBeVisible();
      expect(await audit(page), "flag confirm step").toEqual([]);
      await page.goto("/app/admin/users?q=demo@oddvex.test");
      await page.getByRole("button", { name: /^Suspend/ }).click();
      await expect(page.getByLabel("Reason")).toBeVisible();
      expect(await audit(page), "suspend confirm step").toEqual([]);
    });

    test("data screens have no detectable WCAG A/AA violations", async ({ page, request }) => {
      const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
      const props = await (await request.get(`${API}/v1/props`)).json();
      for (const path of ["/app", "/app/games", `/app/games/${events[0].id}`, `/app/games/${events[0].id}?market=spread`, "/app/odds", "/app/props", `/app/props/${props[0].player.id}`]) {
        await page.goto(path);
        expect(await audit(page), path).toEqual([]);
      }
    });
  });
}
