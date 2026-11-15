import { expect, test } from "@playwright/test";

const PAGES = [
  "/", "/features", "/odds-comparison", "/player-props", "/bet-tracking", "/ai", "/pricing", "/about", "/blog",
  "/blog/removing-the-vig", "/contact", "/help", "/privacy", "/terms", "/responsible-gambling", "/methodology", "/download",
];

test.describe("marketing site", () => {
  for (const path of PAGES) {
    test(`${path} renders with one h1 and no horizontal overflow`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(String(error)));
      const response = await page.goto(path);
      expect(response?.status()).toBe(200);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.getByRole("contentinfo")).toContainText("1-800-GAMBLER");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(1);
      expect(errors).toEqual([]);
    });
  }

  test("home never promises outcomes", async ({ page }) => {
    await page.goto("/");
    const text = (await page.locator("main").innerText()).toLowerCase();
    for (const banned of ["risk-free", "guaranteed win", "sure thing", "can't lose"]) expect(text).not.toContain(banned);
    await expect(page.getByText("OddVex never takes a wager", { exact: false })).toBeVisible();
  });

  test("sample board marks the best price and switches odds format", async ({ page }) => {
    await page.goto("/");
    const board = page.getByRole("table", { name: /sample moneyline/i });
    await expect(board.getByText("Best")).toHaveCount(2);
    await expect(board.getByText("+142")).toBeVisible();
    await page.getByRole("button", { name: "Decimal" }).click();
    await expect(board.getByText("2.42")).toBeVisible();
    await expect(board.getByText("Suspended")).toBeVisible();
  });

  test("theme choice persists across reloads", async ({ page }) => {
    await page.goto("/about");
    await page.evaluate(() => localStorage.setItem("ov-theme", "light"));
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("unknown pages return a helpful 404", async ({ page }) => {
    const response = await page.goto("/no-such-page");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
  });

  test("robots and sitemap exist and keep the app out of the index", async ({ request }) => {
    const robots = await (await request.get("/robots.txt")).text();
    expect(robots).toContain("Disallow: /app/");
    const sitemap = await (await request.get("/sitemap.xml")).text();
    expect(sitemap).toContain("/methodology");
    expect(sitemap).not.toContain("/app");
  });
});
