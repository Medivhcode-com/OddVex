import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8210";

async function signUp(page: Page, tag: string) {
  const email = `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@oddvex.test`;
  await page.goto("/signup?next=/app/tracker");
  await page.getByLabel("Name").fill("Casey Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  // The signup URL also ends in /app/tracker (its ?next= value), so wait for a signed-in signal too.
  await expect(page).toHaveURL(/^[^?]*\/app\/tracker$/);
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  return email;
}

test.describe("research screens (signed out)", () => {
  test("dashboard labels synthetic data and lists games", async ({ page }) => {
    await page.goto("/app");
    await expect(page.getByText(/synthetic data/i).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Tonight's board");
    await expect(page.locator('a[href^="/app/games/evt_"]').first()).toBeVisible();
  });

  test("games filter by league and open a game with an odds table", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming&league=nba`)).json();
    await page.goto("/app/games?league=nba&status=upcoming");
    await expect(page.getByRole("navigation", { name: "League" }).locator('[aria-current="page"]')).toContainText(/basketball/i);
    await page.goto(`/app/games/${events[0].id}`);
    const table = page.getByRole("table", { name: /prices by sportsbook/i });
    await expect(table).toBeVisible();
    await expect(table.getByText("Best").first()).toBeVisible();
    await expect(table.getByText("No-vig consensus")).toBeVisible();
    await expect(page.getByRole("img", { name: /line movement/i })).toBeVisible();
  });

  test("best price is never on a stale or closed book", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    let checked = 0;
    for (const event of events.slice(0, 8)) {
      const odds = await (await request.get(`${API}/v1/events/${event.id}/odds?market=moneyline`)).json();
      if (!odds.books.some((b: { is_stale: boolean; status: string }) => b.is_stale || b.status !== "open")) continue;
      await page.goto(`/app/games/${event.id}`);
      const rows = page.getByRole("table", { name: /prices by sportsbook/i }).locator("tbody tr");
      for (const row of await rows.all()) {
        const text = await row.innerText();
        if (/stale|suspended|not offered/i.test(text)) expect(text).not.toMatch(/\bBest\b/);
      }
      checked += 1;
    }
    expect(checked).toBeGreaterThan(0);
  });

  test("odds format toggle changes prices and persists", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    await page.goto(`/app/games/${events[0].id}`);
    const firstPrice = page.getByRole("table", { name: /prices by sportsbook/i }).locator("tbody .num.font-medium").first();
    await expect(firstPrice).toHaveText(/^[+−]\d+$/);
    await page.getByRole("button", { name: "Decimal" }).click();
    await expect(firstPrice).toHaveText(/^\d+\.\d{2}$/);
    await page.reload();
    await expect(firstPrice).toHaveText(/^\d+\.\d{2}$/);
  });

  test("prop analyzer shows sample size, a range and the caveat", async ({ page, request }) => {
    const board = await (await request.get(`${API}/v1/props?league=nba`)).json();
    await page.goto("/app/props?league=nba");
    await expect(page.getByRole("table", { name: /props board/i })).toBeVisible();
    await page.goto(`/app/props/${board[0].player.id}?market=${board[0].market}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(board[0].player.name);
    await expect(page.getByText(/of \d+ games/)).toBeVisible();
    await expect(page.getByText("95% range")).toBeVisible();
    await expect(page.getByText("A record, not a forecast")).toBeVisible();
    await page.getByRole("navigation", { name: "Games" }).getByRole("link", { name: "Last 20" }).click();
    await expect(page).toHaveURL(/window=20/);
  });

  test("expected value calculator matches the documented example", async ({ page }) => {
    await page.goto("/app/tools");
    const ev = page.locator("#ev");
    await ev.getByLabel("Odds", { exact: true }).fill("+150");
    await ev.getByLabel(/win probability/i).fill("45");
    await ev.getByLabel(/stake/i).fill("100");
    await ev.getByRole("button", { name: "Calculate" }).click();
    await expect(ev.getByText("+12.50%", { exact: true })).toBeVisible();
    await expect(ev.getByText("+$12.50", { exact: true })).toBeVisible();
    await expect(ev.getByText("40.00%", { exact: true })).toBeVisible();
  });

  test("no-vig calculator: -110 both sides is 50/50 with 4.76% overround", async ({ page }) => {
    await page.goto("/app/tools");
    const calc = page.locator("#no-vig");
    await calc.getByRole("button", { name: "Remove the vig" }).click();
    await expect(calc.getByRole("table").getByText("50.00%", { exact: true })).toHaveCount(2);
    await expect(calc.getByText("4.76%", { exact: true })).toBeVisible();
  });

  test("calculator rejects impossible odds with a clear message", async ({ page }) => {
    await page.goto("/app/tools");
    const calc = page.locator("#convert");
    await calc.getByLabel("Odds", { exact: true }).fill("-50");
    await calc.getByRole("button", { name: "Convert" }).click();
    await expect(calc.getByRole("alert")).toBeVisible();
  });

  test("parlay with two legs from one game warns and shows no probability", async ({ page }) => {
    await page.goto("/app/parlay");
    const select = page.getByLabel("From tonight's board");
    const values = await select.locator("option").evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
    const first = values[0];
    const sameGame = values.find((v) => v !== first && v.split(":")[0] === first.split(":")[0])!;
    await select.selectOption(first);
    await page.getByRole("button", { name: "Add leg", exact: true }).click();
    await select.selectOption(sameGame);
    await page.getByRole("button", { name: "Add leg", exact: true }).click();
    await page.getByRole("button", { name: "Calculate parlay" }).click();
    await expect(page.getByText("These legs are correlated")).toBeVisible();
    await expect(page.getByText("Not shown")).toBeVisible();
  });

  test("assistant answers from data, cites sources and declines what it can't know", async ({ page }) => {
    await page.goto("/app/assistant");
    await page.getByRole("button", { name: /best price on/i }).click();
    await expect(page.getByText(/Sources:/)).toBeVisible();
    await expect(page.getByText(/synthetic data, updated/)).toBeVisible();
    await page.getByLabel("Ask OddVex AI").fill("Who will win the championship next year?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText(/No data was used for this answer|can't|cannot|don't/i).last()).toBeVisible();
  });

  test("tracker asks signed-out visitors to log in", async ({ page }) => {
    await page.goto("/app/tracker");
    await expect(page.getByText("Log in to track your bets")).toBeVisible();
  });
});

test.describe("accounts and tracking", () => {
  test("signup requires the 21+ confirmation", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel("Name").fill("No Age");
    await page.getByLabel("Email").fill(`noage-${Date.now()}@oddvex.test`);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("You must be 21 or over to use OddVex.")).toBeVisible();
    await expect(page).toHaveURL(/\/signup/);
  });

  test("login rejects a wrong password without leaking which part was wrong", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("demo@oddvex.test");
    await page.getByLabel("Password").fill("definitely-wrong-password");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("log a bet, settle it as won, then delete it", async ({ page }) => {
    await signUp(page, "bet");
    await expect(page.getByText("No open bets")).toBeVisible();
    await page.getByLabel("Pick").fill("Harbor City Tides ML");
    await page.getByLabel("Odds", { exact: true }).fill("+150");
    await page.getByLabel("Stake ($)").fill("20");
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("Bet saved.")).toBeVisible();

    const open = page.getByRole("region", { name: "Open bets" });
    await expect(open.getByText("Harbor City Tides ML", { exact: true })).toBeVisible();
    await expect(open.getByText("$50.00", { exact: true })).toBeVisible(); // stake 20 at +150 returns 50

    await open.getByRole("button", { name: "Settle", exact: true }).click();
    const settled = page.getByRole("region", { name: "Settled bets" });
    await expect(settled.getByText("Harbor City Tides ML", { exact: true })).toBeVisible();
    await expect(settled.getByText("+$30.00", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Performance" }).getByText("1-0-0")).toBeVisible();

    await settled.getByRole("button", { name: /^Delete Harbor/ }).click();
    await settled.getByRole("button", { name: "Delete bet" }).click();
    await expect(page.getByText("Nothing settled yet")).toBeVisible();
  });

  test("edit an open bet and record closing odds for CLV", async ({ page }) => {
    await signUp(page, "edit");
    await page.getByLabel("Pick").fill("Granite Peak Rams ML");
    await page.getByLabel("Odds", { exact: true }).fill("+150");
    await page.getByLabel("Stake ($)").fill("20");
    await page.getByRole("button", { name: "Save bet" }).click();
    const open = page.getByRole("region", { name: "Open bets" });
    await open.getByRole("button", { name: /^Edit Granite/ }).click();
    await open.getByLabel("Stake ($)").fill("40");
    await open.getByLabel("Closing odds (American)").fill("+120");
    await open.getByLabel("Notes").fill("Took the early number");
    await open.getByRole("button", { name: "Save changes" }).click();
    await expect(open.getByText("$100.00", { exact: true })).toBeVisible(); // 40 at +150 returns 100
    await expect(open.getByText("Note: Took the early number")).toBeVisible();
    // 2.50 taken against 2.20 at the close is +13.6%.
    await expect(open.getByText("+13.6%", { exact: true })).toBeVisible();
  });

  test("settle a parlay leg by leg: a pushed leg drops out", async ({ page }) => {
    await signUp(page, "legs");
    await page.getByLabel("Bet type").selectOption("parlay");
    await page.getByLabel("Pick").nth(0).fill("Leg one wins");
    await page.getByLabel("Odds", { exact: true }).nth(0).fill("+100");
    await page.getByLabel("Pick").nth(1).fill("Leg two pushes");
    await page.getByLabel("Odds", { exact: true }).nth(1).fill("+100");
    await page.getByLabel("Stake ($)").fill("10");
    await page.getByRole("button", { name: "Save bet" }).click();
    const open = page.getByRole("region", { name: "Open bets" });
    await expect(open.getByText("$40.00", { exact: true })).toBeVisible(); // 2.0 x 2.0 on 10
    await open.getByRole("button", { name: "Settle by leg" }).click();
    await open.getByLabel("Leg two pushes").selectOption("push");
    await open.getByRole("button", { name: "Settle parlay" }).click();
    const settled = page.getByRole("region", { name: "Settled bets" });
    // With the pushed leg removed it pays as a single +100 bet: 10 profit, not 30.
    await expect(settled.getByText("+$10.00", { exact: true })).toBeVisible();
  });

  test("one account cannot see another account's bets", async ({ browser }) => {
    const a = await browser.newContext();
    const pageA = await a.newPage();
    await signUp(pageA, "iso-a");
    await pageA.getByLabel("Pick").fill("Private pick of account A");
    await pageA.getByLabel("Odds", { exact: true }).fill("-110");
    await pageA.getByLabel("Stake ($)").fill("11");
    await pageA.getByRole("button", { name: "Save bet" }).click();
    await expect(pageA.getByRole("region", { name: "Open bets" }).getByText("Private pick of account A", { exact: true })).toBeVisible();

    const b = await browser.newContext();
    const pageB = await b.newPage();
    await signUp(pageB, "iso-b");
    await expect(pageB.getByText("No open bets")).toBeVisible();
    await expect(pageB.getByText("Private pick of account A")).toHaveCount(0);
    await a.close();
    await b.close();
  });

  test("follow a game and a team, see them on the dashboard, then unfollow", async ({ page, request }) => {
    await signUp(page, "watch");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    const event = events[0];
    await page.goto(`/app/games/${event.id}`);
    await page.getByRole("button", { name: "Follow this game" }).click();
    await expect(page.getByRole("button", { name: "Following this game" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: `Follow ${event.home_team.name}` }).click();
    await expect(page.getByRole("button", { name: `Following ${event.home_team.name}` })).toBeVisible();

    await page.goto("/app");
    const watch = page.getByRole("region", { name: "Your watchlist" });
    await expect(watch.locator(`a[href="/app/games/${event.id}"]`)).toBeVisible();

    await page.goto(`/app/games/${event.id}`);
    await page.getByRole("button", { name: "Following this game" }).click();
    await page.getByRole("button", { name: `Following ${event.home_team.name}` }).click();
    await expect(page.getByRole("button", { name: "Follow this game" })).toBeVisible();
    await page.goto("/app");
    await expect(page.getByText("Nothing followed yet")).toBeVisible();
  });

  test("signed-out follow sends you to log in", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    await page.goto(`/app/games/${events[0].id}`);
    await page.getByRole("button", { name: "Follow this game" }).click();
    await expect(page).toHaveURL(/\/login\?next=/);
  });

  test("track a bet from a game page; it is tied to the game", async ({ page, request }) => {
    await signUp(page, "quick");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    await page.goto(`/app/games/${events[0].id}`);
    const panel = page.getByRole("region", { name: "Track a bet on this game" });
    await panel.getByLabel("Stake ($)").fill("15");
    await panel.getByRole("button", { name: "Add to tracker" }).click();
    await expect(panel.getByText(/Bet saved\./)).toBeVisible();
    await page.goto("/app/tracker");
    const open = page.getByRole("region", { name: "Open bets" });
    await expect(open.getByText("Tied to a game")).toBeVisible();
    await expect(open.getByText("$15.00", { exact: true })).toBeVisible();
    // The game has not been played, so nothing can be settled yet.
    await open.getByRole("button", { name: "Settle from final scores" }).click();
    await expect(open.getByText(/0 bets settled from final scores\. Left open: 1 game not finished\./)).toBeVisible();
  });

  test("a bet on a finished game settles itself from the final score", async ({ page, request }) => {
    await signUp(page, "auto");
    const finals = await (await request.get(`${API}/v1/events?status=final`)).json();
    const event = finals.find((e: { score: { home: number; away: number } | null }) => e.score && e.score.home !== e.score.away);
    const winner = event.score.home > event.score.away ? "home" : "away";
    const created = await page.request.post("/api/ov/v1/bets", {
      data: {
        bet_type: "straight",
        stake: 10,
        sportsbook: "Northline",
        legs: [{ selection: "Winner ML", market: "moneyline", league: event.league, event_id: event.id, outcome_key: winner, odds: "+100", odds_format: "american" }],
      },
    });
    expect(created.status()).toBe(201);
    await page.reload();
    const open = page.getByRole("region", { name: "Open bets" });
    await open.getByRole("button", { name: "Settle from final scores" }).click();
    const settled = page.getByRole("region", { name: "Settled bets" });
    await expect(settled.getByText("Settled from final score")).toBeVisible();
    await expect(settled.getByText("+$10.00", { exact: true })).toBeVisible();
    await expect(settled.getByText("Won", { exact: true })).toBeVisible();
  });

  test("change password: the new one works and the old one stops working", async ({ page }) => {
    const email = await signUp(page, "pw");
    await page.goto("/app/settings");
    await page.getByLabel("Current password").fill("correct-horse-battery");
    await page.getByLabel("New password").fill("an-even-better-passphrase");
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(page.getByText("Password changed.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible(); // this session stays signed in
    await page.getByRole("button", { name: "Log out" }).click();

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    // Start from a fresh form: React resets the fields when the failed attempt finishes.
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("an-even-better-passphrase");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  });

  test("export downloads my data without any password material", async ({ page }) => {
    const email = await signUp(page, "export");
    await page.goto("/app/settings");
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my data" }).click()]);
    expect(download.suggestedFilename()).toMatch(/^oddvex-export-\d{4}-\d{2}-\d{2}\.json$/);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(chunk as Buffer);
    const text = Buffer.concat(chunks).toString("utf8");
    const data = JSON.parse(text);
    expect(data.user.email).toBe(email);
    expect(Array.isArray(data.bets)).toBe(true);
    expect(text.toLowerCase()).not.toContain("password_hash");
    expect(text).not.toContain("correct-horse-battery");
  });

  test("mock sportsbook sync imports bets once and deletes them on disconnect", async ({ page }) => {
    await signUp(page, "sync");
    const sync = page.getByRole("region", { name: "Sportsbook sync" });
    await expect(sync.getByText("Demonstration only")).toBeVisible();
    await sync.getByRole("button", { name: /^Connect / }).click();
    await sync.getByRole("button", { name: "Sync now" }).click();
    await expect(sync.getByText(/Sync finished\. [1-9]\d* new bets? imported/)).toBeVisible();
    await expect(page.getByText("Synced", { exact: true }).first()).toBeVisible();
    // The mock account gains a couple of bets after the first sync. Earlier ones must be recognized, not duplicated.
    await sync.getByRole("button", { name: "Sync now" }).click();
    await expect(sync.getByText(/, [1-9]\d* already here\./)).toBeVisible();
    // With nothing new on the account, a further sync imports nothing.
    await sync.getByRole("button", { name: "Sync now" }).click();
    await expect(sync.getByText(/Sync finished\. 0 new bets imported/)).toBeVisible();
    await sync.getByRole("button", { name: /^Disconnect / }).click();
    await expect(sync.getByText(/Disconnected\. [1-9]\d* synced bets? deleted/)).toBeVisible();
    await expect(page.getByText("Synced", { exact: true })).toHaveCount(0);
  });

  test("delete account removes access", async ({ page }) => {
    const email = await signUp(page, "del");
    await page.goto("/app/settings");
    await page.getByLabel("Type DELETE to confirm").fill("DELETE");
    await page.getByRole("button", { name: "Delete account and data" }).click();
    await expect(page).toHaveURL(/\/\?account=deleted$/);
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
  });

  test("session cookie is HttpOnly and the proxy blocks cross-origin writes", async ({ page, request }) => {
    await signUp(page, "sec");
    const cookie = (await page.context().cookies()).find((c) => c.name === "ov_session");
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("Lax");
    const response = await request.post("/api/ov/v1/quant/convert", { headers: { origin: "https://evil.example" }, data: { odds: "-110" } });
    expect(response.status()).toBe(403);
    expect((await request.get("/api/ov/v1/admin/overview")).status()).toBe(404);
  });
});

test.describe("admin", () => {
  test("ordinary accounts and signed-out visitors see the not-found page", async ({ page }) => {
    // The page streams, so the status is 200; what matters is that no admin data is rendered.
    await page.goto("/app/admin");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    await expect(page.getByText("Recent audit log")).toHaveCount(0);
    await signUp(page, "notadmin");
    await page.goto("/app/admin");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    await expect(page.getByText("Recent audit log")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  });

  test("an admin account sees the service overview and audit log", async ({ page }) => {
    // The API grants the admin role to this address through configuration, never through the client.
    await page.goto("/signup?next=/app/admin");
    await page.getByLabel("Name").fill("Ops Admin");
    await page.getByLabel("Email").fill("e2e-admin@oddvex.test");
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Create account" }).click();
    if (await page.getByRole("alert").isVisible().catch(() => false)) {
      // The account already exists from the other viewport's run: log in instead.
      await page.goto("/login?next=/app/admin");
      await page.getByLabel("Email").fill("e2e-admin@oddvex.test");
      await page.getByLabel("Password").fill("correct-horse-battery");
      await page.getByRole("button", { name: "Log in" }).click();
    }
    await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Service" }).getByText("Accounts")).toBeVisible();
    await expect(page.getByRole("table", { name: /audit log/i })).toBeVisible();
  });
});

test.describe("design system", () => {
  test("showcase matches the visual baseline @desktop-only", async ({ page }) => {
    await page.goto("/design");
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("design-dark.png", { fullPage: true });
    await page.evaluate(() => (document.documentElement.dataset.theme = "light"));
    await expect(page).toHaveScreenshot("design-light.png", { fullPage: true });
  });
});
