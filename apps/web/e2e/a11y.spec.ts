import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const API = "http://localhost:8210";

/**
 * Automated accessibility checks (WCAG 2.2 A and AA rules that axe can evaluate).
 * This catches contrast, naming and structure regressions. It does not replace a manual screen reader pass.
 */
async function audit(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

const STATIC = ["/", "/pricing", "/methodology", "/help", "/login", "/signup", "/design", "/app/tools", "/app/parlay", "/app/tracker", "/app/assistant", "/app/settings"];

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
