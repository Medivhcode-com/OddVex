import { expect, test } from "./fixtures";

const PAGES = [
  "/", "/features", "/odds-comparison", "/player-props", "/bet-tracking", "/ai", "/pricing", "/about", "/blog",
  "/blog/removing-the-vig", "/contact", "/help", "/privacy", "/terms", "/responsible-gambling", "/methodology", "/download",
  "/forgot-password", "/reset-password", "/verify-email",
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

  test("privacy policy describes what is stored and what deletion keeps", async ({ page }) => {
    await page.goto("/privacy");
    const main = page.locator("main");
    await expect(main.getByText("Preview draft")).toBeVisible();
    for (const text of ["Watchlist:", "Alerts and notifications:", "Weekly staking reminder:", "Security log:", "ov_session", "ov_odds"]) {
      await expect(main.getByText(text, { exact: false }).first()).toBeVisible();
    }
    await expect(main.getByText("The retention period is to be confirmed before launch.", { exact: false })).toBeVisible();
  });

  test("responsible gambling keeps the helpline first and marks only the commitments as draft", async ({ page }) => {
    await page.goto("/responsible-gambling");
    const main = page.locator("main");
    await expect(main.getByRole("link", { name: "1-800-GAMBLER" })).toHaveAttribute("href", "tel:18004262537");
    const order = await main.evaluate((el) => {
      const text = el.textContent ?? "";
      return [text.indexOf("Get help now"), text.indexOf("What OddVex commits to"), text.indexOf("Preview draft")];
    });
    expect(order[0]).toBeGreaterThan(-1);
    expect(order[1]).toBeGreaterThan(order[0]);
    expect(order[2]).toBeGreaterThan(order[1]);
    await expect(main.getByText("Preview draft")).toHaveCount(1);
  });

  test("help center covers alerts, the staking reminder, following and settling, in the page and in JSON-LD", async ({ page }) => {
    await page.goto("/help");
    await page.getByText("How do alerts work?").click();
    await expect(page.getByText("nothing is sent by push or email", { exact: false })).toBeVisible();
    await page.getByText("What is the weekly staking reminder?").click();
    await expect(page.getByText("It is a reminder, not a limit", { exact: false })).toBeVisible();
    const faq = JSON.parse((await page.locator('script[type="application/ld+json"]').textContent()) ?? "{}");
    const questions = faq.mainEntity.map((entry: { name: string }) => entry.name);
    for (const question of ["How do alerts work?", "What is the weekly staking reminder?", "How do I follow a team, player or game?", "How does settling from final scores work?"]) {
      expect(questions).toContain(question);
    }
  });

  test("robots and sitemap exist and keep the app out of the index", async ({ request }) => {
    const robots = await (await request.get("/robots.txt")).text();
    expect(robots).toContain("Disallow: /app/");
    const sitemap = await (await request.get("/sitemap.xml")).text();
    expect(sitemap).toContain("/methodology");
    expect(sitemap).not.toContain("/app");
  });
});
