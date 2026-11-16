import { expect, test } from "./fixtures";
import { API, logIn, openMoreOnPhone, sidewaysOverflow, signUp } from "./helpers";

/** Wording the value screen must never use, anywhere on the page (brand voice, banned claims). */
const BANNED = [/guarantee/i, /free money/i, /\blocks?\b/i, /risk[- ]free/i, /\+\s?ev pick/i, /best bets?\b/i, /sure thing/i, /can[’']t lose/i, /top picks?/i];
/** Wording the analytics must never use about a person's results. */
const CELEBRATORY = [/congrat/i, /hot streak/i, /on fire/i, /heater/i, /crush/i, /well done/i, /nice work/i, /!/];

test.describe("value screen", () => {
  test("shows the method and the caveat, keeps filters in the URL and never promises anything", async ({ page, request }) => {
    const leagues = await (await request.get(`${API}/v1/leagues`)).json();
    expect((await page.goto("/app/value"))?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "Value" })).toBeVisible();
    const main = page.getByRole("main");

    // The API's caveat and method are on the page, above the results.
    const screen = await (await request.get(`${API}/v1/value`)).json();
    await expect(main.getByText(screen.caveat, { exact: false })).toBeVisible();
    await expect(main.getByText(screen.method, { exact: false })).toBeVisible();
    await expect(main.getByText("Read this first")).toBeVisible();
    await expect(main.getByText("no row here reflects a real edge", { exact: false })).toBeVisible();

    // Synthetic value rows come and go, so either the rows or the explained empty state is right.
    const panel = page.getByRole("region", { name: "Prices above the consensus" });
    const empty = panel.getByText("Nothing qualifies right now");
    const edges = panel.getByText("Edge vs consensus").filter({ visible: true }).first();
    await expect(empty.or(edges)).toBeVisible();
    if (await empty.isVisible()) {
      await expect(panel.getByText("On many slates no price sits above the consensus", { exact: false })).toBeVisible();
    } else {
      const visible = panel.locator("li, tbody tr").filter({ visible: true }).first();
      await expect(visible).toContainText(/Consensus of \d+ other books?/);
      await expect(visible).toContainText(/\+\d+\.\d{2}%/); // the edge, signed
      await expect(visible).toContainText(/Break-even at the best price|\d+\.\d%/);
      await expect(visible.getByRole("link").first()).toHaveAttribute("href", /\/app\/games\/[^?]+\?market=(moneyline|spread|total)$/);
      // Signed out: no tracking action.
      await expect(panel.getByRole("link", { name: /Track this/ })).toHaveCount(0);
    }
    const text = await page.locator("body").innerText();
    for (const banned of BANNED) expect(text, String(banned)).not.toMatch(banned);
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);

    // Filters live in the URL and survive a reload.
    await page.getByRole("navigation", { name: "League" }).getByRole("link", { name: leagues[0].name, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`league=${leagues[0].key}`));
    await page.getByRole("navigation", { name: "Market" }).getByRole("link", { name: "Spread", exact: true }).click();
    await expect(page).toHaveURL(/market=spread/);
    await page.getByRole("navigation", { name: "Minimum edge" }).getByRole("link", { name: "1% or more", exact: true }).click();
    await expect(page).toHaveURL(/min_edge=0\.01/);
    await expect(page).toHaveURL(new RegExp(`league=${leagues[0].key}`));
    await expect(page).toHaveURL(/market=spread/);
    await page.reload();
    await expect(page.getByRole("navigation", { name: "League" }).getByRole("link", { name: leagues[0].name, exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("navigation", { name: "Market" }).getByRole("link", { name: "Spread", exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("navigation", { name: "Minimum edge" }).getByRole("link", { name: "1% or more", exact: true })).toHaveAttribute("aria-current", "page");
    await expect(empty.or(edges)).toBeVisible();
    const filteredText = await page.locator("body").innerText();
    for (const banned of BANNED) expect(filteredText, String(banned)).not.toMatch(banned);
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);

    // A filter value the API does not know falls back instead of failing.
    await page.goto("/app/value?league=nope&market=nope&min_edge=7");
    await expect(page.getByRole("navigation", { name: "League" }).getByRole("link", { name: "All leagues" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("navigation", { name: "Minimum edge" }).getByRole("link", { name: "Any edge" })).toHaveAttribute("aria-current", "page");
  });

  test("is in the navigation and linked from the odds page", async ({ page }) => {
    await page.goto("/app/odds?league=nhl&market=total");
    await page.getByRole("link", { name: "Compare the best prices with the consensus of the other books" }).click();
    await expect(page).toHaveURL(/\/app\/value\?league=nhl&market=total$/);
    await expect(page.getByRole("heading", { level: 1, name: "Value" })).toBeVisible();
    await openMoreOnPhone(page);
    const link = page.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Value", exact: true }).filter({ visible: true });
    await expect(link).toHaveAttribute("aria-current", "page");
  });

  test("a signed-in visitor can go from a row to the game's tracker panel", async ({ page }) => {
    await signUp(page, "value");
    await page.goto("/app/value");
    const panel = page.getByRole("region", { name: "Prices above the consensus" });
    const empty = panel.getByText("Nothing qualifies right now");
    const track = panel.getByRole("link", { name: /Track this/ }).filter({ visible: true }).first();
    await expect(empty.or(track)).toBeVisible();
    if (await empty.isVisible()) return; // nothing qualifies on this slate; the empty state is covered above
    await track.click();
    await expect(page).toHaveURL(/\/app\/games\/[^?]+\?market=\w+#quickbet-heading$/);
    await expect(page.getByRole("region", { name: "Track a bet on this game" })).toBeVisible();
  });
});

test.describe("tracker analytics", () => {
  test("signed-out visitors are asked to log in", async ({ page }) => {
    await page.goto("/app/tracker/analytics");
    await expect(page.getByRole("heading", { level: 1, name: "Tracker analytics" })).toBeVisible();
    await expect(page.getByText("Log in to see your analytics")).toBeVisible();
  });

  test("a new account reaches it from the tracker and sees the empty state", async ({ page }) => {
    await signUp(page, "analytics");
    await page.getByRole("main").getByRole("link", { name: "Analytics", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/tracker\/analytics$/);
    await expect(page.getByText("No settled bets yet")).toBeVisible();
    await expect(page.getByText("Analytics use settled bets only", { exact: false })).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);
  });

  test("the demo account sees bands, weekdays, months, streaks, CLV and stake sizes", async ({ page, request }) => {
    const login = await request.post(`${API}/v1/auth/login`, { data: { email: "demo@oddvex.test", password: "oddvex-demo-2026" } });
    const data = await (await request.get(`${API}/v1/bets/analytics`, { headers: { authorization: `Bearer ${(await login.json()).access_token}` } })).json();
    expect(data.settled_count).toBeGreaterThan(0);

    await logIn(page, "demo@oddvex.test", "oddvex-demo-2026", "/app/tracker/analytics");
    await expect(page.getByRole("heading", { level: 1, name: "Tracker analytics" })).toBeVisible();
    const main = page.getByRole("main");

    const bands = page.getByRole("region", { name: "By odds band" });
    await expect(bands.getByRole("table")).toBeVisible();
    await expect(bands.getByRole("rowheader")).toHaveCount(data.by_odds_band.length);
    await expect(bands.getByRole("rowheader", { name: "−199 to −110" })).toBeVisible(); // a true minus sign
    // Every bar repeats a number that is also written out.
    const band = data.by_odds_band.find((row: { bets: number }) => row.bets > 0);
    await expect(bands.getByRole("meter").first()).toHaveAttribute("aria-label", /: \d+ of \d+ bets$/);
    await expect(bands.getByRole("row").filter({ hasText: band.label.replace(/-(?=\d)/g, "−") })).toContainText(String(band.bets));

    await expect(page.getByRole("region", { name: "By weekday" }).getByRole("rowheader")).toHaveCount(7);
    await expect(page.getByRole("region", { name: "By month" }).getByRole("rowheader")).toHaveCount(data.by_month.length);

    const streaks = page.getByRole("region", { name: "Streaks" });
    await expect(streaks.getByText("Longest run of wins")).toBeVisible();
    await expect(streaks.getByText("Longest run of losses")).toBeVisible();
    await expect(streaks.getByText("Current run")).toBeVisible();
    if (data.streak_note) await expect(streaks.getByText(data.streak_note, { exact: false })).toBeVisible();

    if (data.sample_note) await expect(main.getByText(data.sample_note, { exact: false })).toBeVisible();
    else await expect(main.getByText("Small sample")).toHaveCount(0);

    const clv = page.getByRole("region", { name: "Closing line value" });
    if (data.clv.sample > 0) {
      await expect(clv.getByText("Average CLV")).toBeVisible();
      await expect(clv.getByRole("rowheader")).toHaveCount(data.clv.buckets.length);
    }
    await expect(page.getByRole("region", { name: "Stake sizes" }).getByRole("rowheader")).toHaveCount(data.stake_distribution.length);
    await expect(main.getByText(data.note, { exact: false })).toBeVisible();
    await expect(page.getByRole("region", { name: "Overview" }).getByText("Average stake")).toBeVisible();

    const text = await main.innerText();
    for (const banned of CELEBRATORY) expect(text, String(banned)).not.toMatch(banned);
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);
  });
});

test.describe("account status in settings", () => {
  test("shows the plan and the verification status, and queues a new link without claiming it was sent", async ({ page, request }) => {
    const email = await signUp(page, "status");
    await page.goto("/app/settings");
    const account = page.getByRole("region", { name: "Account" });
    await expect(account.getByText("Plan", { exact: true })).toBeVisible();
    await expect(account.getByText("Free", { exact: true })).toBeVisible();
    await expect(account.getByText("Preview: every feature is included")).toBeVisible();
    await expect(account.getByText("Email not verified")).toBeVisible();

    await account.getByRole("button", { name: "Send a new verification link" }).click();
    await expect(account.getByText("A new confirmation link has been queued", { exact: false })).toBeVisible();
    await expect(account.getByText("no email is actually sent", { exact: false })).toBeVisible();

    // The queued link works; afterwards the status flips and the button is gone.
    let token = "";
    await expect
      .poll(async () => {
        const response = await request.get(`${API}/v1/dev/email-outbox/latest?to=${encodeURIComponent(email)}&template=verify_email`);
        token = response.ok() ? ((await response.json()).token ?? "") : "";
        return token;
      })
      .not.toBe("");
    await page.goto(`/verify-email?token=${encodeURIComponent(token)}`);
    await page.getByRole("button", { name: "Confirm email address" }).click();
    await expect(page.getByText("Email address confirmed.")).toBeVisible();
    await page.goto("/app/settings");
    await expect(account.getByText("Email verified", { exact: true })).toBeVisible();
    await expect(account.getByRole("button", { name: "Send a new verification link" })).toHaveCount(0);
  });

  test("an expired confirmation link offers a new one to a signed-in visitor, and a way in to everyone else", async ({ page }) => {
    await page.goto("/verify-email?token=not-a-real-token-0000");
    await page.getByRole("button", { name: "Confirm email address" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("expired or was already used");
    await expect(page.getByRole("button", { name: "Send a new verification link" })).toHaveCount(0);
    await expect(page.getByRole("main").getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login?next=/app/settings");

    await signUp(page, "relink");
    await page.goto("/verify-email?token=not-a-real-token-0000");
    await page.getByRole("button", { name: "Confirm email address" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("expired or was already used");
    await page.getByRole("button", { name: "Send a new verification link" }).click();
    await expect(page.getByText("A new confirmation link has been queued", { exact: false })).toBeVisible();
    await expect(page.getByText("no email is actually sent", { exact: false })).toBeVisible();
  });

  test("the login page explains a suspended account only when asked to", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("This account is suspended")).toHaveCount(0);
    await page.goto("/login?suspended=1");
    await expect(page.getByText("This account is suspended")).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "/contact");
    // The page that ends a session never signs out a working one.
    await signUp(page, "ended");
    await page.goto("/api/session/ended");
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  });
});
