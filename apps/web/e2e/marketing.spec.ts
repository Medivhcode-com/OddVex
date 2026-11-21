import { expect, test } from "./fixtures";

const HELPLINE = "1-800-MY-RESET (1-800-697-3738)";
const SHORT_LINE = `21+. OddVex does not take wagers. Gambling problem? Call ${HELPLINE}.`;
/** The number the site used to give, as a word and in digits. Written in halves so a search of the source finds only the page that explains it. */
const OLD_NUMBER = new RegExp(`${"GAMB"}${"LER"}|426-?2537`, "i");

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
      const footer = page.getByRole("contentinfo");
      await expect(footer.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
      // The number the site gave before is named on one page only, as the New Jersey council's line.
      const body = await page.locator("body").innerText();
      if (path !== "/responsible-gambling") expect(body).not.toMatch(OLD_NUMBER);
      expect(body).not.toMatch(/call or text 1-800/i);
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

  test("features and methodology describe the value screen and tracker analytics without overclaiming", async ({ page }) => {
    await page.goto("/features");
    for (const name of ["Value screen", "Tracker analytics"]) {
      const item = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name, exact: true }) });
      await expect(item.getByText("In the preview")).toBeVisible();
    }
    await page.goto("/methodology");
    await expect(page.getByRole("heading", { name: "Edge vs consensus" })).toBeVisible();
    const text = (await page.locator("main").innerText()).toLowerCase();
    expect(text).toContain("edge       = consensus × decimal_best − 1");
    expect(text).toContain("not proof of an edge");
    expect(text).toContain("can be wrong");
    for (const banned of ["risk-free", "guaranteed", "free money", "sure thing", "best bet"]) expect(text).not.toContain(banned);
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

  test("privacy policy describes what is stored, what the export holds and what deletion keeps", async ({ page }) => {
    await page.goto("/privacy");
    const main = page.locator("main");
    await expect(main.getByText("Preview draft")).toBeVisible();
    for (const text of ["Watchlist:", "Alerts and notifications:", "Weekly staking reminder:", "Security log:", "ov_session", "ov_odds"]) {
      await expect(main.getByText(text, { exact: false }).first()).toBeVisible();
    }
    const text = (await main.innerText()).replace(/\s+/g, " ");
    // What a security log entry really holds, details included.
    expect(text).toContain("the action taken, the ID of the item it concerned, the IP address the request came from, a request ID and, for some actions, a short detail");
    // The export is described by what it contains and what it leaves out.
    expect(text).toContain("It does not contain your password or its hash");
    expect(text).toContain("your own security log entries");
    // Deletion: what goes, what stays, and for how long where that is known.
    expect(text).toContain("Security log entries are kept after an account is deleted");
    expect(text).toContain("A copy made before you deleted your account still holds the account, your email address included, until that copy is removed.");
    expect(text).toContain("its community handle stays reserved");
    expect(text).toContain("No email address, and no fingerprint of one, is kept");
    expect(text).toContain("If you cannot sign in");
    expect(text).toContain("The retention period is to be confirmed before launch.");
    // The old page promised more than the API does.
    expect(text).not.toContain("a copy of what your account holds");
    expect(text).not.toMatch(/stored account messages immediately/);
    expect(text).not.toContain("Each entry holds the time, the internal ID of the account, the IP address the request came from and a request ID.");
  });

  test("contact page tells someone who cannot sign in how to have an account deleted", async ({ page }) => {
    await page.goto("/contact");
    const main = page.locator("main");
    const text = (await main.innerText()).replace(/\s+/g, " ");
    expect(text).toContain("If you cannot sign in");
    expect(text).not.toContain("It takes effect immediately.");
    await expect(main.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
  });

  test("responsible gambling gives the verified helpline facts first and marks only the commitments as draft", async ({ page }) => {
    await page.goto("/responsible-gambling");
    const main = page.locator("main");
    await expect(main.getByRole("link", { name: "1-800-MY-RESET", exact: true })).toHaveAttribute("href", "tel:+18006973738");
    await expect(main.getByRole("link", { name: "800GAM", exact: true })).toHaveAttribute("href", "sms:800426");
    await expect(main.getByRole("link", { name: "988", exact: true })).toHaveAttribute("href", "tel:988");
    await expect(main.getByRole("link", { name: "911", exact: true })).toHaveAttribute("href", "tel:911");
    await expect(main.getByRole("link", { name: "ncpgambling.org" })).toHaveAttribute("href", "https://www.ncpgambling.org");
    const text = (await main.innerText()).replace(/\s+/g, " ");
    expect(text).toContain("Call 1-800-MY-RESET (1-800-697-3738), the National Problem Gambling Helpline, or text 800GAM (800426).");
    expect(text).toContain("It is confidential and answers 24 hours a day, every day.");
    expect(text).toContain("The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide and Crisis Lifeline) or call 911.");
    expect(text).toContain("since January 29, 2026");
    expect(text).toContain("Some states publish their own helpline.");
    expect(text).toContain("checked on November 19, 2026");
    // The old number appears once, as the New Jersey council's line, and is never called national.
    const old = text.match(new RegExp(OLD_NUMBER.source, "gi")) ?? [];
    expect(old).toHaveLength(1);
    expect(text).toMatch(new RegExp(`1-800-${"GAMB"}${"LER"} is a different line, run by the Council on Compulsive Gambling of New Jersey\\.`));
    // Claims the project has not verified are gone.
    expect(text).not.toMatch(/(^|[^-\w])free\b/i);
    expect(text).not.toMatch(/open 24\/7/i);
    const order = await main.evaluate((el) => {
      const content = el.textContent ?? "";
      return [content.indexOf("Get help now"), content.indexOf("What OddVex commits to"), content.indexOf("Preview draft")];
    });
    expect(order[0]).toBeGreaterThan(-1);
    expect(order[1]).toBeGreaterThan(order[0]);
    expect(order[2]).toBeGreaterThan(order[1]);
    await expect(main.getByText("Preview draft")).toHaveCount(1);
  });

  test("login and signup carry the short 21+ line with the helpline as a phone link", async ({ page }) => {
    for (const path of ["/login", "/signup"]) {
      await page.goto(path);
      const footer = page.getByRole("contentinfo");
      await expect(footer).toHaveText(SHORT_LINE);
      await expect(footer.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
    }
  });

  test("pricing says the preview is free and that paid plans are undecided, with no plan table", async ({ page }) => {
    await page.goto("/pricing");
    const main = page.locator("main");
    const text = (await main.innerText()).replace(/\s+/g, " ");
    expect(text).toContain("Everything in the preview is free to use");
    expect(text).toContain("Paid plans are planned");
    expect(text).toContain("What they will include and what they will cost has not been decided");
    for (const claim of [/premium/i, /\$\s?\d/, /will remain available without paying/i, /stays free/i, /longer odds history/i, /advanced prop filters/i, /higher assistant limits/i, /no trial clock/i]) {
      expect(text, String(claim)).not.toMatch(claim);
    }
    await expect(main.getByRole("list")).toHaveCount(0);
    await expect(main.getByRole("table")).toHaveCount(0);
    await expect(main.getByRole("heading", { level: 2 })).toHaveCount(0);
  });

  test("methodology and help say what the parlay tool shows and promise no combined probability", async ({ page }) => {
    await page.goto("/methodology");
    const method = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    expect(method).toContain("The parlay tool shows the combined price, the payout and the break-even rate.");
    expect(method).toContain("It does not show a chance that every leg wins.");
    expect(method).toContain("planned and not built");
    expect(method).not.toMatch(/combined probability is only shown/i);
    expect(method).not.toMatch(/labelled as assuming independence/i);
    await page.goto("/help");
    await page.getByText("Does the parlay tool show the chance that every leg wins?").click();
    await expect(page.getByText("No. It shows the combined price, the payout and the break-even rate", { exact: false })).toBeVisible();
    const help = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    expect(help).not.toMatch(/for some parlays/i);
    await page.getByText("How do I delete my data?").click();
    await expect(page.getByText("If you cannot sign in", { exact: false })).toBeVisible();
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
