import { expect, test } from "./fixtures";
import { adminSignIn, signUp } from "./helpers";

const API = "http://localhost:8210";
const HELPLINE = "1-800-MY-RESET (1-800-697-3738)";
const SHORT_LINE = `21+. OddVex does not take wagers. Gambling problem? Call ${HELPLINE}.`;

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

  test("moneyline line movement is drawn by implied probability and labelled with American prices", async ({ page, request }) => {
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    const event = events[0];
    await page.goto(`/app/games/${event.id}`);
    const panel = page.getByRole("region", { name: "Line movement" });
    await expect(panel.getByText("Implied probability of each price, bookmaker margin included. Higher on the chart is a shorter price.")).toBeVisible();
    const chart = panel.getByRole("img", { name: /line movement/i });
    // The axis carries percentages. An American price on a straight axis can land between −100 and +100, where no price exists.
    const ticks = await chart.locator('text[data-axis="value"]').allTextContents();
    expect(ticks).toHaveLength(3);
    for (const tick of ticks) expect(tick).toMatch(/^\d{1,2}\.\d%$/);
    // Every charted point is labelled with an American price: book, price, time.
    // Only the page is read here. Prices move every few seconds, so a second read of the API
    // would not match the one the page was built from. That each label is the API's own
    // American price for the point is proved in src/lib/line-history.test.ts.
    const titles = await chart.locator("title").allTextContents();
    expect(titles.length).toBeGreaterThan(1);
    expect(titles).toHaveLength(await chart.locator("g[data-mark]").count());
    for (const title of titles) expect(title).toMatch(/^.+: [+−]\d{3,}, (Latest|\d+h earlier)$/);
    // The legend names every charted book once, with the price of that book's latest point.
    const legend = await panel.locator("figcaption [data-legend]").evaluateAll((entries) =>
      entries.map((entry) => ({ name: entry.querySelector(":scope > span")?.textContent ?? "", price: entry.querySelector(":scope > span.num")?.textContent ?? "" })),
    );
    expect(legend.length).toBeGreaterThan(0);
    expect(new Set(legend.map((entry) => entry.name)).size).toBe(legend.length);
    for (const entry of legend) {
      expect(entry.price, entry.name).toMatch(/^[+−]\d{3,}$/);
      const own = titles.filter((title) => title.startsWith(`${entry.name}: `));
      expect(own.length, entry.name).toBeGreaterThan(0);
      expect(own[own.length - 1].startsWith(`${entry.name}: ${entry.price}, `), `${entry.name}: the legend gives the latest point's price`).toBe(true);
    }
    expect(titles.every((title) => legend.some((entry) => title.startsWith(`${entry.name}: `)))).toBe(true);
    // The spread chart still plots the line.
    const detail = await (await request.get(`${API}/v1/events/${event.id}`)).json();
    if (detail.available_markets.includes("spread")) {
      await page.goto(`/app/games/${event.id}?market=spread`);
      const spread = page.getByRole("region", { name: "Line movement" });
      await expect(spread.getByText("Spread, in points.")).toBeVisible();
      for (const tick of await spread.locator('text[data-axis="value"]').allTextContents()) expect(tick).toMatch(/^([+−]\d+(\.5)?|PK)$/);
    }
  });

  test("the app shell shows the 21+ line and the helpline at every width", async ({ page }) => {
    for (const path of ["/app", "/app/odds", "/app/tracker", "/app/settings"]) {
      await page.goto(path);
      const wide = (page.viewportSize()?.width ?? 0) >= 1024;
      const shown = page.getByTestId(wide ? "shell-help-sidebar" : "shell-help-footer");
      const hidden = page.getByTestId(wide ? "shell-help-footer" : "shell-help-sidebar");
      await expect(shown, path).toBeVisible();
      await expect(hidden, path).toBeHidden();
      await expect(shown).toContainText(SHORT_LINE);
      await expect(shown.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
      await expect(shown.getByRole("link", { name: "Help and limits" })).toHaveAttribute("href", "/responsible-gambling");
      if (!wide) {
        // The fixed bottom bar must not sit on top of the line once the page is scrolled to its end.
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        const line = await shown.boundingBox();
        const bar = await page.getByRole("navigation", { name: "App" }).boundingBox();
        expect(line && bar && line.y + line.height <= bar.y, `${path}: the line is clear of the bottom bar`).toBe(true);
      }
    }
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
    const result = page.getByRole("region", { name: "Result" });
    await expect(result.getByText("Legs from the same game")).toBeVisible();
    await expect(result.getByText("their results are linked", { exact: false })).toBeVisible();
    await expect(result.getByText("Combined odds", { exact: true })).toBeVisible();
    await expect(result.getByText("Combined probability")).toHaveCount(0);
    await expect(result.getByText("Not shown")).toHaveCount(0);
    await expect(result.getByText(/not computed|event_id|same event \(/)).toHaveCount(0);
  });

  test("parlay with legs from different games shows price, payout and break-even, and asks for nothing it can't take", async ({ page }) => {
    await page.goto("/app/parlay");
    const select = page.getByLabel("From tonight's board");
    const values = await select.locator("option").evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
    const first = values[0];
    const otherGame = values.find((v) => v.split(":")[0] !== first.split(":")[0])!;
    await select.selectOption(first);
    await page.getByRole("button", { name: "Add leg", exact: true }).click();
    await select.selectOption(otherGame);
    await page.getByRole("button", { name: "Add leg", exact: true }).click();
    await page.getByRole("button", { name: "Calculate parlay" }).click();
    const result = page.getByRole("region", { name: "Result" });
    await expect(result.getByText("Combined odds", { exact: true })).toBeVisible();
    await expect(result.getByText("Payout", { exact: true })).toBeVisible();
    await expect(result.getByText("Break-even", { exact: true })).toBeVisible();
    // No dead stat, no API note asking for a win probability the form has no field for, no warning.
    await expect(result.getByText("Combined probability")).toHaveCount(0);
    await expect(result.getByText("Not shown")).toHaveCount(0);
    await expect(result.getByText(/win probability is required|not computed/)).toHaveCount(0);
    await expect(result.getByRole("note")).toHaveCount(0);
  });

  test("parlay with a custom leg says custom legs can't be checked for independence", async ({ page }) => {
    await page.goto("/app/parlay");
    await page.getByRole("button", { name: "Add leg", exact: true }).click();
    await page.getByLabel("Custom leg").fill("Player over 22.5 points");
    await page.getByLabel("American odds").fill("-115");
    await page.getByRole("button", { name: "Add custom leg" }).click();
    await page.getByRole("button", { name: "Calculate parlay" }).click();
    const result = page.getByRole("region", { name: "Result" });
    await expect(result.getByText("Custom legs can't be checked for independence", { exact: false })).toBeVisible();
    await expect(result.getByText("These legs are correlated")).toHaveCount(0);
    await expect(result.getByText(/event_id/)).toHaveCount(0);
    await expect(result.getByText("Combined probability")).toHaveCount(0);
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

  test("a message in crisis gets a calm support card with tappable numbers and no data", async ({ page }) => {
    await page.goto("/app/assistant");
    await page.getByLabel("Ask OddVex AI").fill("I want to kill myself after losing my bankroll, best odds on the Harbor City Tides?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const card = page.getByRole("group", { name: "Help is available now" });
    await expect(card).toBeVisible();
    await expect(card.getByRole("link", { name: "988", exact: true }).first()).toHaveAttribute("href", "tel:988");
    await expect(card.getByRole("link", { name: "911", exact: true })).toHaveAttribute("href", "tel:911");
    await expect(card.getByRole("link", { name: "1-800-697-3738", exact: true })).toHaveAttribute("href", "tel:+18006973738");
    await expect(card.getByText("Sources:")).toHaveCount(0);
    await expect(card.getByText("No data was used for this answer.")).toHaveCount(0);
    // No betting data: no price for the team the message named.
    await expect(card.getByText(/moneyline|Harbor City Tides/i)).toHaveCount(0);
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

  test("a failed login keeps the email, focuses the error, and a second try works on the same page", async ({ page }) => {
    const email = await signUp(page, "retry");
    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await page.goto("/login?next=/app/tracker");
    await page.evaluate(() => ((window as unknown as { __samePage: boolean }).__samePage = true));
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("definitely-wrong-password");
    await page.getByRole("button", { name: "Log in" }).click();
    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(page.locator(":focus").getByRole("alert")).toBeVisible(); // focus is on the error message
    await expect(page.getByLabel("Email")).toHaveValue(email);
    await expect(page.getByLabel("Password")).toHaveValue("");
    // No reload and no navigation happened in between.
    expect(await page.evaluate(() => (window as unknown as { __samePage?: boolean }).__samePage)).toBe(true);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/app\/tracker$/);
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  });

  test("forgot password: neutral answer, then the link sets a new password that works once", async ({ page, request }) => {
    const email = await signUp(page, "reset");
    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot password?" }).click();
    await expect(page).toHaveURL(/\/forgot-password$/);
    await expect(page.getByText("no email is actually sent", { exact: false })).toBeVisible();

    // An address with no account gets exactly the same answer.
    await page.getByLabel("Email").fill(`nobody-${Date.now()}@oddvex.test`);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText("If an account exists for that address, we\u2019ve sent a link", { exact: false })).toBeVisible();

    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText("If an account exists for that address, we\u2019ve sent a link", { exact: false })).toBeVisible();
    await expect(page.getByText("no email is actually sent", { exact: false })).toBeVisible();

    // Nothing is emailed in this build; the test API exposes the outbox so the link can be followed.
    let token = "";
    await expect
      .poll(async () => {
        const response = await request.get(`${API}/v1/dev/email-outbox/latest?to=${encodeURIComponent(email)}&template=password_reset`);
        token = response.ok() ? ((await response.json()).token ?? "") : "";
        return token;
      })
      .not.toBe("");

    await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
    await page.getByLabel("New password").fill("short");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.getByText("Use at least 10 characters.")).toBeVisible();
    await page.getByLabel("New password").fill("a-brand-new-passphrase");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page).toHaveURL(/\/login\?reset=done$/);
    await expect(page.getByText("Password changed. Log in with the new password.")).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("a-brand-new-passphrase");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();

    // The link is single use.
    await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
    await page.getByLabel("New password").fill("yet-another-passphrase");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("expired or was already used");
    await expect(page.getByRole("link", { name: "Request a new reset link" })).toBeVisible();
  });

  test("email confirmation link confirms once and needs a deliberate click", async ({ page, request }) => {
    const email = await signUp(page, "verify");
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
    await page.goto(`/verify-email?token=${encodeURIComponent(token)}`);
    await page.getByRole("button", { name: "Confirm email address" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("expired or was already used");
    await page.goto("/verify-email");
    await expect(page.getByRole("main").getByRole("alert")).toContainText("This link is incomplete");
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

  test("a bet whose answer was lost is saved once when the same form is sent again; an edited form is a new bet", async ({ page }) => {
    await signUp(page, "retry");
    const sent: (string | undefined)[] = [];
    let loseNext = false;
    await page.route(
      (url) => url.pathname === "/api/ov/v1/bets",
      async (route) => {
        if (route.request().method() !== "POST") return route.continue();
        sent.push(JSON.parse(route.request().postData() ?? "{}").client_request_id);
        if (!loseNext) return route.continue();
        // The API stores the bet, and its answer never reaches the browser.
        loseNext = false;
        await route.fetch();
        return route.abort("failed");
      },
    );
    const myBets = async () => ((await (await page.request.get("/api/ov/v1/bets?status=pending")).json()) as { legs: { selection: string }[]; stake: number }[]).filter((bet) => bet.legs[0].selection.startsWith("Retry"));

    // A stake under a cent is refused in the form, before anything is sent.
    await page.getByLabel("Pick").fill("Retry Tides ML");
    await page.getByLabel("Odds", { exact: true }).fill("+150");
    await page.getByLabel("Stake ($)").fill("0.004");
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("Enter a stake of at least $0.01.")).toBeVisible();
    expect(sent).toHaveLength(0);

    // The first answer is lost; the same form sent again carries the same id and is saved once.
    await page.getByLabel("Stake ($)").fill("20");
    loseNext = true;
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("the bet may already be saved", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("Bet saved.")).toBeVisible();
    expect(sent).toHaveLength(2);
    expect(sent[0]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(sent[1]).toBe(sent[0]);
    expect(await myBets()).toHaveLength(1);

    // A lost answer, then an edit: the edited form is another bet with a new id.
    await page.getByLabel("Pick").fill("Retry Rams ML");
    await page.getByLabel("Odds", { exact: true }).fill("+120");
    await page.getByLabel("Stake ($)").fill("10");
    loseNext = true;
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("the bet may already be saved", { exact: false })).toBeVisible();
    await page.getByLabel("Stake ($)").fill("12");
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("Bet saved.")).toBeVisible();
    expect(sent).toHaveLength(4);
    expect(new Set(sent).size).toBe(3);
    expect(sent[3]).not.toBe(sent[2]);
    expect((await myBets()).map((bet) => bet.stake).sort((a, b) => a - b)).toEqual([10, 12, 20]);
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

  test("settled bets are paged: every one can be reached, edited and deleted, and open bets never fall out", async ({ page }) => {
    test.setTimeout(120_000);
    await signUp(page, "paging");
    const DAY = 86_400_000;
    const start = Date.now() - 400 * DAY;
    const leg = (selection: string) => ({ selection, market: "moneyline", odds: "+100", odds_format: "american" });
    // One open bet placed before everything else, then 55 settled bets a day apart: "Paged bet 01" is the oldest.
    const open = await page.request.post("/api/ov/v1/bets", { data: { bet_type: "straight", stake: 5, sportsbook: "Northline", placed_at: new Date(start - DAY).toISOString(), legs: [leg("Oldest open bet")] } });
    expect(open.status()).toBe(201);
    for (let i = 1; i <= 55; i += 1) {
      const name = `Paged bet ${String(i).padStart(2, "0")}`;
      const created = await page.request.post("/api/ov/v1/bets", { data: { bet_type: "straight", stake: 10, sportsbook: "Northline", placed_at: new Date(start + i * DAY).toISOString(), legs: [leg(name)] } });
      expect(created.status(), name).toBe(201);
      const settled = await page.request.post(`/api/ov/v1/bets/${(await created.json()).id}/settle`, { data: { result: i % 2 ? "won" : "lost" } });
      expect(settled.ok(), `${name} settled`).toBe(true);
    }

    await page.goto("/app/tracker");
    const settled = page.getByRole("region", { name: "Settled bets" });
    const openBets = page.getByRole("region", { name: "Open bets" });
    // Counts come from the summary, and the open bet is listed although 55 newer bets exist.
    await expect(page.getByRole("region", { name: "Performance" })).toContainText("55 settled bets");
    await expect(openBets).toContainText("1 open");
    await expect(openBets.getByText("Oldest open bet", { exact: true })).toBeVisible();
    await expect(settled).toContainText("Showing 1 to 50 of 55, most recently placed first");
    await expect(settled.getByRole("listitem").filter({ hasText: /^Paged bet \d\d/ })).toHaveCount(50);
    await expect(settled.getByText("Paged bet 55", { exact: true })).toBeVisible();
    await expect(settled.getByText("Paged bet 06", { exact: true })).toBeVisible();
    await expect(settled.getByText("Paged bet 05", { exact: true })).toHaveCount(0);
    const pages = settled.getByRole("navigation", { name: "Pages of settled bets" });
    await expect(pages).toContainText("Page 1 of 2");
    await expect(pages.getByRole("link", { name: "Newer bets" })).toHaveCount(0);

    // The second page holds the five oldest.
    await pages.getByRole("link", { name: "Older bets" }).click();
    await expect(page).toHaveURL(/\/app\/tracker\?page=2(#settled)?$/);
    await expect(settled).toContainText("Showing 51 to 55 of 55, most recently placed first");
    await expect(settled.getByRole("listitem").filter({ hasText: /^Paged bet \d\d/ })).toHaveCount(5);
    for (const n of ["01", "02", "03", "04", "05"]) await expect(settled.getByText(`Paged bet ${n}`, { exact: true })).toBeVisible();
    await expect(openBets.getByText("Oldest open bet", { exact: true })).toBeVisible();

    // Editing an old bet keeps the place.
    await settled.getByRole("button", { name: "Edit Paged bet 03" }).click();
    await settled.getByLabel("Notes").fill("Reached on page two");
    await settled.getByRole("button", { name: "Save changes" }).click();
    await expect(settled.getByText("Note: Reached on page two")).toBeVisible();
    await expect(page).toHaveURL(/\/app\/tracker\?page=2(#settled)?$/);
    await expect(settled).toContainText("Showing 51 to 55 of 55");

    // So does deleting one; the total follows.
    await settled.getByRole("button", { name: "Delete Paged bet 01" }).click();
    await settled.getByRole("button", { name: "Delete bet" }).click();
    await expect(settled).toContainText("Showing 51 to 54 of 54, most recently placed first");
    await expect(settled.getByText("Paged bet 01", { exact: true })).toHaveCount(0);
    await expect(page).toHaveURL(/\/app\/tracker\?page=2(#settled)?$/);

    // A page past the end goes to the last page that exists; a value that is no page number goes to the first.
    await page.goto("/app/tracker?page=9");
    await expect(page).toHaveURL(/\/app\/tracker\?page=2$/);
    await expect(settled).toContainText("Showing 51 to 54 of 54");
    await page.goto("/app/tracker?page=abc");
    await expect(page).toHaveURL(/\/app\/tracker$/);
    await expect(settled).toContainText("Showing 1 to 50 of 54");
  });

  test("the tracker and the sportsbook sync panel each carry a help link", async ({ page }) => {
    await signUp(page, "helplink");
    for (const id of ["tracker-help", "sync-help"]) {
      const line = page.getByTestId(id);
      await expect(line).toContainText(SHORT_LINE);
      await expect(line.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
      await expect(line.getByRole("link", { name: "Help and limits" })).toHaveAttribute("href", "/responsible-gambling");
    }
    await expect(page.getByRole("region", { name: "Log a bet" }).getByTestId("tracker-help")).toBeVisible();
    await expect(page.getByRole("region", { name: "Sportsbook sync" }).getByTestId("sync-help")).toBeVisible();
  });

  test("settings gives the helpline, the text line and the responsible gambling page", async ({ page }) => {
    await page.goto("/app/settings");
    const panel = page.getByRole("main").locator("section").filter({ hasText: "Play within your limits" });
    await expect(panel).toContainText(`the National Problem Gambling Helpline is confidential and answers 24 hours a day, every day. Call ${HELPLINE} or text 800GAM (800426)`);
    await expect(panel.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
    await expect(panel.getByRole("link", { name: "800GAM" })).toHaveAttribute("href", "sms:800426");
    await expect(panel.getByRole("link", { name: "responsible gambling page" })).toHaveAttribute("href", "/responsible-gambling");
    await expect(panel).not.toContainText(/\bfree\b/i);
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

  test("a quick bet whose answer was lost is saved once when sent again unchanged", async ({ page, request }) => {
    await signUp(page, "quickretry");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    const sent: (string | undefined)[] = [];
    let loseNext = true;
    await page.route(
      (url) => url.pathname === "/api/ov/v1/bets",
      async (route) => {
        if (route.request().method() !== "POST") return route.continue();
        sent.push(JSON.parse(route.request().postData() ?? "{}").client_request_id);
        if (!loseNext) return route.continue();
        // The API stores the bet, and its answer never reaches the browser.
        loseNext = false;
        await route.fetch();
        return route.abort("failed");
      },
    );
    await page.goto(`/app/games/${events[0].id}`);
    const panel = page.getByRole("region", { name: "Track a bet on this game" });
    await panel.getByLabel("Stake ($)").fill("0.004");
    await panel.getByRole("button", { name: "Add to tracker" }).click();
    await expect(panel.getByText("Enter a stake of at least $0.01.")).toBeVisible();
    expect(sent).toHaveLength(0);

    await panel.getByLabel("Stake ($)").fill("17");
    await panel.getByRole("button", { name: "Add to tracker" }).click();
    await expect(panel.getByText("the bet may already be saved", { exact: false })).toBeVisible();
    await panel.getByRole("button", { name: "Add to tracker" }).click();
    await expect(panel.getByText(/Bet saved\./)).toBeVisible();
    expect(sent).toHaveLength(2);
    expect(sent[0]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(sent[1]).toBe(sent[0]);
    const mine = ((await (await page.request.get("/api/ov/v1/bets?status=pending")).json()) as { legs: { event_id: string | null }[]; stake: number }[]).filter((bet) => bet.legs[0].event_id === events[0].id);
    expect(mine.map((bet) => bet.stake)).toEqual([17]);
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
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible(); // this session stays signed in
    await page.getByRole("button", { name: "Log out", exact: true }).click();

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    // Same page, no reload: the email is still there and the rejected password was cleared.
    await expect(page.getByLabel("Email")).toHaveValue(email);
    await expect(page.getByLabel("Password")).toHaveValue("");
    await page.getByLabel("Password").fill("an-even-better-passphrase");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
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

test.describe("layout", () => {
  test("signed-in screens never scroll sideways", async ({ page, request }) => {
    await signUp(page, "layout");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    const props = await (await request.get(`${API}/v1/props`)).json();
    for (const path of ["/app", "/app/games", `/app/games/${events[0].id}`, "/app/odds", "/app/props", `/app/props/${props[0].player.id}`, "/app/tracker", "/app/tracker/analytics", "/app/value", "/app/alerts", "/app/tools", "/app/parlay", "/app/assistant", "/app/settings"]) {
      await page.goto(path);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, path).toBeLessThanOrEqual(1);
    }
  });
});

test.describe("alerts and notifications", () => {
  test("signed-out visitors are asked to log in", async ({ page }) => {
    await page.goto("/app/alerts");
    await expect(page.getByText("Log in to set alerts")).toBeVisible();
  });

  test("a price alert that is already met fires once, can be read, set again and deleted", async ({ page, request }) => {
    await signUp(page, "alert");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    await page.goto(`/app/games/${events[0].id}`);
    const panel = page.getByRole("region", { name: "Set an alert" });
    await panel.getByLabel("Price at or above").fill("-5000"); // far below any real price, so it is met at once
    await panel.getByRole("button", { name: "Save alert" }).click();
    await expect(panel.getByText(/Alert saved\./)).toBeVisible();

    await page.goto("/app/alerts");
    const notifications = page.getByRole("region", { name: "Notifications" });
    await expect(notifications.getByText("1 unread")).toBeVisible();
    await expect(notifications.getByText("New", { exact: true })).toBeVisible();
    await expect(notifications.getByText("Price alert", { exact: true })).toBeVisible();
    await expect(page.getByRole("banner").getByText("1 unread")).toBeAttached();
    // Alert copy reports a fact; it never tells anyone to bet.
    const text = (await notifications.innerText()).toLowerCase();
    for (const banned of ["bet now", "hurry", "don't miss", "lock", "guaranteed", "act fast"]) expect(text).not.toContain(banned);

    // Loading the page again must not notify twice.
    await page.reload();
    await expect(notifications.getByText("1 unread")).toBeVisible();
    await notifications.getByRole("button", { name: /^Mark as read/ }).click();
    await expect(notifications.getByText("All read")).toBeVisible();

    const rules = page.getByRole("region", { name: "Your alerts" });
    await expect(rules.getByText("Triggered", { exact: true })).toBeVisible();
    // Setting it again re-arms it. The price is still above the threshold, so it reports that again, once.
    await rules.getByRole("button", { name: /^Set again/ }).click();
    await expect(notifications.getByText("1 unread")).toBeVisible();
    await expect(notifications.getByText("Price alert", { exact: true })).toHaveCount(2);
    await rules.getByRole("button", { name: /^Delete:/ }).click();
    await rules.getByRole("button", { name: "Delete alert" }).click();
    await expect(page.getByText("No alerts set")).toBeVisible();
  });

  test("game start, final score and line move alerts are saved as active", async ({ page, request }) => {
    await signUp(page, "alertkinds");
    const events = await (await request.get(`${API}/v1/events?status=upcoming&league=nba`)).json();
    const event = events[events.length - 1]; // the latest tip-off, so the start alert cannot be due yet
    await page.goto(`/app/games/${event.id}`);
    let panel = page.getByRole("region", { name: "Set an alert" });
    await panel.getByText("Before the game starts").click();
    await panel.getByLabel("How long before").selectOption("30");
    await panel.getByRole("button", { name: "Save alert" }).click();
    await expect(panel.getByText(/Alert saved\./)).toBeVisible();
    await panel.getByText("When the game ends").click();
    await panel.getByRole("button", { name: "Save alert" }).click();
    await expect(panel.getByText(/Alert saved\./)).toBeVisible();

    await page.goto(`/app/games/${event.id}?market=spread`);
    panel = page.getByRole("region", { name: "Set an alert" });
    await panel.getByText("Line moves").click();
    await panel.getByLabel(/Moves by at least/).fill("1.5");
    await panel.getByRole("button", { name: "Save alert" }).click();
    await expect(panel.getByText(/Alert saved\./)).toBeVisible();

    await page.goto("/app/alerts");
    const rules = page.getByRole("region", { name: "Your alerts" });
    await expect(rules.getByText("3 active")).toBeVisible();
    await rules.getByRole("button", { name: "Check now" }).click();
    await expect(rules.getByText(/Checked 3 alerts\. 0 fired/)).toBeVisible();

    await rules.getByRole("button", { name: /^Pause/ }).first().click();
    await expect(rules.getByText("Paused", { exact: true })).toBeVisible();
    await expect(rules.getByText("2 active")).toBeVisible();
    await rules.getByRole("button", { name: /^Resume/ }).click();
    await expect(rules.getByText("3 active")).toBeVisible();
  });

  test("alert form rejects a price that is not American odds", async ({ page, request }) => {
    await signUp(page, "alertbad");
    const events = await (await request.get(`${API}/v1/events?status=upcoming`)).json();
    await page.goto(`/app/games/${events[0].id}`);
    const panel = page.getByRole("region", { name: "Set an alert" });
    await panel.getByLabel("Price at or above").fill("50");
    await panel.getByRole("button", { name: "Save alert" }).click();
    await expect(panel.getByRole("alert")).toContainText("Enter American odds");
  });

  test("weekly staking reminder: set it, pass it, see one supportive reminder", async ({ page }) => {
    await signUp(page, "stake");
    await page.goto("/app/settings");
    const section = page.getByRole("region", { name: "Weekly staking reminder" });
    await expect(section.getByText(/reminder, not a limit/)).toBeVisible();
    await section.getByLabel("Weekly amount ($)").fill("50");
    await section.getByRole("button", { name: "Save reminder" }).click();
    await expect(section.getByText("Reminder set at $50.00 a week.")).toBeVisible();

    await page.goto("/app/tracker");
    await page.getByLabel("Pick").fill("Over the reminder");
    await page.getByLabel("Odds", { exact: true }).fill("-110");
    await page.getByLabel("Stake ($)").fill("60");
    await page.getByRole("button", { name: "Save bet" }).click();
    await expect(page.getByText("Bet saved.")).toBeVisible(); // the bet is still logged: this is not a limit
    await expect(page.getByText("You've reached your weekly staking reminder")).toBeVisible();
    const notice = page.getByRole("note").filter({ hasText: "You've reached your weekly staking reminder" });
    await expect(notice.getByRole("link", { name: HELPLINE })).toHaveAttribute("href", "tel:+18006973738");
    await expect(notice).toContainText(`confidential help is available at ${HELPLINE}.`);

    await page.goto("/app/alerts");
    const notifications = page.getByRole("region", { name: "Notifications" });
    await expect(notifications.getByText("Staking reminder", { exact: true })).toHaveCount(1);

    await page.goto("/app/settings");
    await page.getByRole("region", { name: "Weekly staking reminder" }).getByRole("button", { name: "Turn off" }).click();
    await expect(page.getByText("Reminder turned off.")).toBeVisible();
    await page.goto("/app/tracker");
    await expect(page.getByText("You've reached your weekly staking reminder")).toHaveCount(0);
  });

  test("notification preferences persist", async ({ page }) => {
    await signUp(page, "prefs");
    await page.goto("/app/settings");
    const toggle = page.getByRole("switch", { name: "Line moves" });
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    await page.reload();
    await expect(page.getByRole("switch", { name: "Line moves" })).not.toBeChecked();
    await expect(page.getByRole("switch", { name: "Price alerts" })).toBeChecked();
  });
});

test.describe("admin", () => {
  test("ordinary accounts and signed-out visitors see the not-found page", async ({ page }) => {
    // The proxy checks the role before the page starts streaming, so this is a real 404.
    expect((await page.goto("/app/admin"))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    await expect(page.getByText("Recent audit log")).toHaveCount(0);
    await signUp(page, "notadmin");
    expect((await page.goto("/app/admin"))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    await expect(page.getByText("Recent audit log")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  });

  test("an admin account sees the service overview and audit log", async ({ page }) => {
    await adminSignIn(page);
    await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
    expect((await page.goto("/app/admin"))?.status()).toBe(200);
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
