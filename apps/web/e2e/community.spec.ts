import AxeBuilder from "@axe-core/playwright";
import type { APIRequestContext, BrowserContext } from "@playwright/test";
import { expect, test, watchCsp, type Page } from "./fixtures";
import { adminSignIn, adminToken, API, logIn, openMoreOnPhone, setFlag, sidewaysOverflow, signUp } from "./helpers";

/**
 * The community section, end to end against the real API.
 *
 * Both community flags are OFF by default. This file turns them on for its own tests and
 * always turns them off again (`afterAll`), so no other spec ever sees them on. The tests share
 * accounts and state, so they run in order. The suite runs once per viewport against the same
 * API, so every handle carries a token that is new on each run, and nothing assumes the
 * community is empty (the e2e database also holds seeded, fictional profiles with graded picks).
 */
test.describe.configure({ mode: "serial" });

const BANNED = ["guaranteed", "lock of", "can't lose", "risk-free", "free money", "hot streak", "on fire", "best bets", "units"];
const MARKUP = "<script>alert(1)</script>";
const ANALYSIS = `Pace over the last five games points this way. ${MARKUP} Small sample, so only a lean.`;
const SECOND_ANALYSIS = "Second look at the same game. <b>bold</b> is not markup here.";
const COMMENT = "Which games is that sample from? <b>bold</b>";

type EventRef = { id: string; home_team: { name: string }; away_team: { name: string } };

async function audit(page: Page) {
  // Let fades and color transitions finish first. Auditing mid-transition reads a half-faded color
  // and reports a contrast failure that no one would ever see.
  await page.evaluate(async () => {
    await Promise.all(
      document.getAnimations().map((animation) => {
        const timing = animation.effect?.getComputedTiming();
        return timing && timing.iterations === Infinity ? null : animation.finished.catch(() => null);
      }),
    );
  });
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

/** Runs axe on the current URL in the dark and the light theme. `ready` is something the page must show first. */
async function auditBothThemes(page: Page, name: string, ready: () => Promise<void>) {
  for (const theme of ["dark", "light"] as const) {
    await page.evaluate((value) => localStorage.setItem("ov-theme", value), theme);
    await page.reload();
    await ready();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(await audit(page), `${name}, ${theme} theme`).toEqual([]);
  }
  await page.evaluate(() => localStorage.removeItem("ov-theme"));
}

/** The page's own words: everything in <main> except text the API labels as its own method description. */
async function ownCopy(page: Page): Promise<string> {
  return page.evaluate(() => {
    const main = document.querySelector("main")!.cloneNode(true) as HTMLElement;
    main.querySelectorAll("[data-api-text]").forEach((node) => node.remove());
    return (main.textContent ?? "").toLowerCase().replace(/[‘’]/g, "'");
  });
}

async function expectNoBannedCopy(page: Page, name: string, userContent: string[] = []) {
  let text = await ownCopy(page);
  for (const content of userContent) text = text.split(content.toLowerCase()).join(" ");
  for (const phrase of BANNED) expect(text.includes(phrase), `${name} contains "${phrase}"`).toBe(false);
}

async function flags(request: APIRequestContext): Promise<Record<string, boolean>> {
  return (await (await request.get(`${API}/v1/flags`)).json()).flags;
}

function card(page: Page, handle: string, text: string) {
  return page.getByRole("article").filter({ hasText: `@${handle}` }).filter({ hasText: text });
}

test.describe("community", () => {
  let contextA: BrowserContext;
  let contextB: BrowserContext;
  let a: Page;
  let b: Page;
  let handleA = "";
  let handleB = "";
  let handleC = "";
  let event: EventRef;
  let firstPickId = "";
  let secondPickId = "";
  const csp: string[] = [];
  const dialogs: string[] = [];

  test.beforeAll(async ({ browser, request }) => {
    // Whatever an earlier, interrupted run left behind: start from the documented default.
    await setFlag(request, "community", false);
    await setFlag(request, "community_leaderboard", false);

    const token = `${Date.now().toString(36).slice(-6)}${Math.floor(Math.random() * 1296).toString(36).padStart(2, "0")}`;
    handleA = `pa_${token}`;
    handleB = `pb_${token}`;
    handleC = `pc_${token}`;

    // An upcoming game with a moneyline and a spread, as far in the future as the data offers.
    const upcoming = (await (await request.get(`${API}/v1/events?status=upcoming`)).json()) as (EventRef & { start_time: string })[];
    upcoming.sort((x, y) => y.start_time.localeCompare(x.start_time));
    for (const candidate of upcoming) {
      const detail = await (await request.get(`${API}/v1/events/${candidate.id}`)).json();
      if (["moneyline", "spread"].every((market) => detail.available_markets.includes(market))) {
        event = candidate;
        break;
      }
    }
    expect(event, "an upcoming game with moneyline and spread markets").toBeTruthy();

    contextA = await browser.newContext();
    contextB = await browser.newContext();
    for (const context of [contextA, contextB]) {
      await context.addInitScript(() => {
        try {
          localStorage.setItem("ov-autorefresh", "off");
        } catch {}
      });
    }
    a = await contextA.newPage();
    b = await contextB.newPage();
    for (const page of [a, b]) {
      watchCsp(page, csp);
      // User text with markup in it must never run: an alert would be a dialog.
      page.on("dialog", (dialog) => {
        dialogs.push(dialog.message());
        void dialog.dismiss();
      });
    }
    await signUp(a, "comm-a");
    await signUp(b, "comm-b");
  });

  test.afterAll(async ({ request }) => {
    try {
      await contextA?.close();
      await contextB?.close();
    } finally {
      // Always, even when a test failed: both flags back to OFF.
      try {
        await setFlag(request, "community_leaderboard", false);
      } finally {
        await setFlag(request, "community", false);
      }
      const now = await flags(request);
      expect(now.community, "community flag restored to off").toBe(false);
      expect(now.community_leaderboard, "community_leaderboard flag restored to off").toBe(false);
    }
  });

  test.afterEach(() => {
    expect(csp, "Content-Security-Policy violations on the shared pages").toEqual([]);
    expect(dialogs, "no script from user text ran").toEqual([]);
  });

  test("with the flag off every community URL is a real 404 and nothing links to it", async ({ page, request }) => {
    expect((await flags(request)).community).toBe(false);
    const paths = [
      "/app/community",
      "/app/community/",
      "/app/community?scope=everyone",
      "/app/community/guidelines",
      "/app/community/settings",
      "/app/community/leaderboard",
      "/app/community/picks/anything",
      "/app/community/profiles/demo_bettor",
      "/app/community/unknown/deeper",
    ];
    for (const path of paths) {
      expect((await page.goto(path))?.status(), `signed out ${path}`).toBe(404);
      await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
      expect((await a.goto(path))?.status(), `signed in ${path}`).toBe(404);
      await expect(a.getByRole("heading", { level: 1 })).toContainText("off the board");
    }

    // No navigation entry, on the sidebar or in the phone's "More" sheet.
    await a.goto("/app");
    await openMoreOnPhone(a);
    await expect(a.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Settings", exact: true }).filter({ visible: true })).toBeVisible();
    await expect(a.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Community" })).toHaveCount(0);
    await expect(a.locator('a[href^="/app/community"]')).toHaveCount(0);

    // No entry point on a game, in the settings or on the alerts page.
    await a.goto(`/app/games/${event.id}`);
    await expect(a.getByRole("region", { name: "Track a bet on this game" })).toBeVisible();
    await expect(a.getByText("Share a pick")).toHaveCount(0);
    await expect(a.locator('a[href^="/app/community"]')).toHaveCount(0);
    await a.goto("/app/settings");
    await expect(a.getByRole("switch", { name: "Price alerts" })).toBeVisible();
    await expect(a.getByRole("switch", { name: "New followers" })).toHaveCount(0);
    await expect(a.getByRole("switch", { name: "Graded picks" })).toHaveCount(0);

    // The seeded demo account has community notifications; with the flag off they carry no link.
    await logIn(page, "demo@oddvex.test", "oddvex-demo-2026", "/app/alerts");
    await expect(page.getByRole("region", { name: "Notifications" })).toBeVisible();
    await expect(page.locator('a[href^="/app/community"]')).toHaveCount(0);

    // The browser bridge answers like the API: the feature does not exist.
    const bridged = await a.request.get("/api/ov/v1/community/guidelines");
    expect(bridged.status()).toBe(404);
    expect((await bridged.json()).error.code).toBe("feature_disabled");

    // Marketing keeps it as planned, and it is not in the sitemap.
    await page.goto("/features");
    const row = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "Community", exact: true }) });
    await expect(row.getByText("Planned", { exact: true })).toBeVisible();
    await expect(row.getByRole("link")).toHaveCount(0);
    expect(await (await request.get("/sitemap.xml")).text()).not.toContain("community");
  });

  test("with the flag off the admin console has no Community tab and its page is a 404", async ({ page }) => {
    await adminSignIn(page);
    await expect(page.getByRole("navigation", { name: "Admin sections" }).getByRole("link", { name: "Flags", exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin sections" }).getByRole("link", { name: "Community" })).toHaveCount(0);
    expect((await page.goto("/app/admin/community"))?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
  });

  test("an admin turns the community on, and the entry points appear", async ({ page, request }) => {
    await adminSignIn(page, "/app/admin/flags");
    const list = page.getByRole("region", { name: "Feature flags", exact: true });
    const flag = list.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "community", exact: true }) });
    await flag.getByRole("button", { name: /^Turn on/ }).click();
    await expect(flag.getByText("Review required first")).toBeVisible();
    await flag.getByRole("button", { name: "Confirm: turn on community" }).click();
    await expect(flag.getByText("Flag turned on.", { exact: false })).toBeVisible();
    expect((await flags(request)).community).toBe(true);
    expect((await flags(request)).community_leaderboard).toBe(false);

    // The moderation tab exists now.
    const tabs = page.getByRole("navigation", { name: "Admin sections" });
    await tabs.getByRole("link", { name: "Community", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/admin\/community$/);
    await expect(tabs.getByRole("link", { name: "Community", exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("region", { name: "Community overview" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Report queue" })).toBeVisible();
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);

    // Moderation is not reachable through the browser bridge, for an admin either.
    expect((await page.request.get("/api/ov/v1/admin/community/reports")).status()).toBe(404);

    // The navigation entry, also in the phone's "More" sheet.
    await a.goto("/app");
    await openMoreOnPhone(a);
    const entry = a.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Community", exact: true }).filter({ visible: true });
    await expect(entry).toBeVisible();
    await entry.click();
    await expect(a).toHaveURL(/\/app\/community$/);
    await expect(a.getByRole("heading", { level: 1, name: "Community" })).toBeVisible();
  });

  test("a signed-out visitor is asked to log in, and can still read the guidelines", async ({ page, request }) => {
    for (const path of ["/app/community", "/app/community/settings", `/app/community/profiles/demo_bettor`, "/app/community/picks/abc123"]) {
      expect((await page.goto(path))?.status(), path).toBe(200);
      await expect(page.getByText("Log in to open the community")).toBeVisible();
      await expect(page.getByRole("main").getByRole("link", { name: "Log in", exact: true })).toHaveAttribute("href", `/login?next=${encodeURIComponent(path)}`);
      await expect(page.getByRole("article")).toHaveCount(0);
    }
    const guidelines = await (await request.get(`${API}/v1/community/guidelines`)).json();
    await page.goto("/app/community/guidelines");
    await expect(page.getByText(guidelines.rules[0].text)).toBeVisible();
    // The leaderboard has its own flag, which is still off.
    expect((await page.goto("/app/community/leaderboard"))?.status()).toBe(404);
  });

  test("the first visit shows the API's guidelines and a profile form that validates the handle and the bio", async ({ request }) => {
    const guidelines = await (await request.get(`${API}/v1/community/guidelines`)).json();
    expect(guidelines.rules.length).toBeGreaterThan(3);

    await a.goto("/app/community");
    const rules = a.getByRole("region", { name: "Community guidelines" });
    await expect(rules.getByText(guidelines.intro)).toBeVisible();
    for (const rule of guidelines.rules) {
      await expect(rules.getByText(rule.title, { exact: true })).toBeVisible();
      await expect(rules.getByText(rule.text, { exact: true })).toBeVisible();
    }
    await expect(rules.getByText(guidelines.enforcement)).toBeVisible();
    await expect(rules.getByText(guidelines.help)).toBeVisible();
    await expect(rules.getByText(guidelines.version)).toBeVisible();
    // Until a profile exists there is no feed, and the other pages lead back here.
    await expect(a.getByRole("article")).toHaveCount(0);
    await a.goto("/app/community/settings");
    await expect(a).toHaveURL(/\/app\/community$/);

    const form = a.getByRole("region", { name: "Create your profile" });
    await expect(form.getByText("never see your email address, your name, the bets in your tracker or your plan", { exact: false })).toBeVisible();
    await expect(form.getByText("can’t post picks, comment or follow anyone until you make it public", { exact: false })).toBeVisible();
    const handle = form.getByLabel("Handle");

    // Live, local validation of the handle.
    await handle.fill("Bad Handle!");
    await expect(form.getByText("Use lowercase letters, numbers and underscores only.")).toBeVisible();
    await expect(handle).toHaveAttribute("aria-invalid", "true");
    await handle.fill("ab");
    await expect(form.getByText("Use at least 3 characters.")).toBeVisible();
    await handle.fill("a".repeat(21));
    await expect(form.getByText("Use 20 characters or fewer.")).toBeVisible();
    await form.getByRole("button", { name: "Create profile" }).click();
    await expect(form.getByText("Use 20 characters or fewer.")).toBeVisible();

    // A reserved handle is the API's call.
    await handle.fill("admin");
    await expect(handle).not.toHaveAttribute("aria-invalid", "true");
    await form.getByRole("button", { name: "Create profile" }).click();
    await expect(form.getByText("That handle is reserved. Choose another.")).toBeVisible();

    // A link in the bio is rejected, and so is a phrase the content rules name.
    await handle.fill(handleA);
    await expect(form.getByText("That handle is reserved.", { exact: false })).toHaveCount(0);
    const bio = form.getByLabel("Bio (optional)");
    await bio.fill("My picks are at www.example.com");
    await expect(form.getByText("31 of 280 characters")).toBeVisible();
    await form.getByRole("button", { name: "Create profile" }).click();
    await expect(form.getByText("Links aren't allowed. Remove the web address and try again.")).toBeVisible();
    await bio.fill("Every pick here is risk-free");
    await form.getByRole("button", { name: "Create profile" }).click();
    await expect(form.getByText("This text breaks a community rule (no results presented as certain).", { exact: false })).toBeVisible();
    await expect(a.getByRole("article")).toHaveCount(0);

    // The onboarding screen itself, in both themes.
    await auditBothThemes(a, "onboarding", async () => {
      await expect(a.getByRole("region", { name: "Create your profile" })).toBeVisible();
    });
    expect(await sidewaysOverflow(a)).toBeLessThanOrEqual(1);

    await a.getByLabel("Handle").fill(handleA);
    await a.getByLabel("Bio (optional)").fill("Totals and pace. <b>bold</b>");
    await a.getByRole("checkbox", { name: "Make my profile public" }).check();
    await a.getByRole("button", { name: "Create profile" }).click();
    await expect(a.getByRole("region", { name: "Picks from people you follow" })).toBeVisible();
    await expect(a.getByText("No picks from people you follow yet")).toBeVisible();
    await expect(a.getByRole("navigation", { name: "Community sections" }).getByRole("link", { name: "My profile" })).toHaveAttribute("href", `/app/community/profiles/${handleA}`);

    // The second person cannot take the same handle, whatever the case.
    await b.goto("/app/community");
    await b.getByLabel("Handle").fill(handleA);
    await b.getByRole("checkbox", { name: "Make my profile public" }).check();
    await b.getByRole("button", { name: "Create profile" }).click();
    await expect(b.getByText("That handle is already in use. Choose another.")).toBeVisible();
    await b.getByLabel("Handle").fill(handleB);
    await b.getByRole("button", { name: "Create profile" }).click();
    await expect(b.getByRole("region", { name: "Picks from people you follow" })).toBeVisible();
  });

  test("a private profile can browse but cannot post a pick or a comment", async ({ page, request }) => {
    await signUp(page, "comm-c");
    await page.goto("/app/community");
    await page.getByLabel("Handle").fill(handleC);
    await expect(page.getByRole("checkbox", { name: "Make my profile public" })).not.toBeChecked();
    await page.getByRole("button", { name: "Create profile" }).click();
    await expect(page.getByText("Your profile is private", { exact: true })).toBeVisible();
    await expect(page.getByText("To post picks, comment or follow people, make your profile public.", { exact: false })).toBeVisible();

    // Browsing works: the Everyone feed has the seeded, fictional profiles.
    await page.getByRole("navigation", { name: "Feed scope" }).getByRole("link", { name: "Everyone" }).click();
    await expect(page).toHaveURL(/scope=everyone/);
    await expect(page.getByRole("article").first()).toBeVisible();

    // No way to post from a game.
    await page.goto(`/app/games/${event.id}`);
    const panel = page.getByRole("region", { name: "Share a pick" });
    await expect(panel.getByText("Your community profile is private, so you can't share picks.", { exact: false })).toBeVisible();
    await expect(panel.getByRole("button", { name: "Post pick" })).toHaveCount(0);
    await expect(panel.getByRole("link", { name: "Open community settings" })).toHaveAttribute("href", "/app/community/settings");

    // No comment form on a pick, and the API refuses a direct attempt as well.
    const feed = await (await page.request.get("/api/ov/v1/community/feed?scope=everyone&limit=1")).json();
    await page.goto(`/app/community/picks/${feed.items[0].id}`);
    await expect(page.getByText("Your profile is private, so you can read comments but not add one.", { exact: false })).toBeVisible();
    await expect(page.getByLabel("Add a comment")).toHaveCount(0);
    const refused = await page.request.post("/api/ov/v1/community/picks", { data: { event_id: event.id, market: "moneyline", outcome_key: "home" } });
    expect(refused.status()).toBe(403);
    expect((await refused.json()).error.code).toBe("profile_required");

    // Nobody else can find a private profile.
    expect((await b.request.get(`/api/ov/v1/community/profiles/${handleC}`)).status()).toBe(404);
    await b.goto(`/app/community/profiles/${handleC}`);
    await expect(b.getByRole("heading", { level: 1 })).toContainText("off the board");
    expect((await flags(request)).community).toBe(true);
  });

  test("a public profile shares a pick from an upcoming game; rejections are explained and a second pick on the market is refused", async () => {
    await a.goto(`/app/games/${event.id}?market=moneyline`);
    const panel = a.getByRole("region", { name: "Share a pick" });
    await expect(panel.getByLabel("Outcome, at the best current price")).toBeVisible();
    // A pick is a selection and reasoning. Nothing asks for a stake, a size or a confidence.
    await expect(panel.getByRole("textbox")).toHaveCount(1);
    await expect(panel.getByRole("spinbutton")).toHaveCount(0);
    await expect(panel.getByLabel(/stake|unit|confidence|amount/i)).toHaveCount(0);
    await expect(panel.getByText("Plain text only. No guarantees, no links and no selling picks.")).toBeVisible();

    const analysis = panel.getByLabel("Analysis (optional)");
    await analysis.fill("This is a guaranteed winner");
    await expect(panel.getByText("27 of 1000 characters")).toBeVisible();
    await panel.getByRole("button", { name: "Post pick" }).click();
    await expect(panel.getByRole("alert")).toContainText("This text breaks a community rule (no results presented as certain).");
    await analysis.fill("Full write-up at https://example.com/picks");
    await panel.getByRole("button", { name: "Post pick" }).click();
    await expect(panel.getByRole("alert")).toContainText("Links aren't allowed.");
    await analysis.fill("x".repeat(1001));
    await expect(panel.getByText("1001 of 1000 characters, over the limit")).toBeVisible();
    await panel.getByRole("button", { name: "Post pick" }).click();
    await expect(panel.getByRole("alert")).toContainText("Keep the analysis to 1000 characters or fewer.");

    await analysis.fill(ANALYSIS);
    await panel.getByRole("button", { name: "Post pick" }).click();
    await expect(panel.getByText("Pick posted")).toBeVisible();
    const link = panel.getByRole("link", { name: "Open the pick" });
    firstPickId = (await link.getAttribute("href"))!.split("/").pop()!;
    expect(firstPickId).toMatch(/^[A-Za-z0-9]+$/);

    // One pick per game and market.
    await analysis.fill("A second go at the same market.");
    await panel.getByRole("button", { name: "Post pick" }).click();
    await expect(panel.getByRole("alert")).toContainText("You already have a pick on this market for this game.");
    await expect(panel.getByRole("alert").getByRole("link", { name: "Open your pick" })).toHaveAttribute("href", `/app/community/picks/${firstPickId}`);

    // Another market of the same game is a separate pick.
    await a.goto(`/app/games/${event.id}?market=spread`);
    await a.getByRole("region", { name: "Share a pick" }).getByLabel("Analysis (optional)").fill(SECOND_ANALYSIS);
    await a.getByRole("region", { name: "Share a pick" }).getByRole("button", { name: "Post pick" }).click();
    await expect(a.getByRole("region", { name: "Share a pick" }).getByText("Pick posted")).toBeVisible();
    secondPickId = (await a.getByRole("region", { name: "Share a pick" }).getByRole("link", { name: "Open the pick" }).getAttribute("href"))!.split("/").pop()!;

    // The author can delete a pick while the game is upcoming. Nothing is deleted here.
    await a.goto(`/app/community/picks/${secondPickId}`);
    await a.getByRole("button", { name: "Delete pick" }).click();
    await expect(a.getByText("You can only do this before the game starts.", { exact: false })).toBeVisible();
    await a.getByRole("button", { name: "Keep" }).click();
    await expect(a.getByRole("button", { name: "Report this pick" })).toHaveCount(0);
  });

  test("the other person finds the pick under Everyone, follows the author and then sees it under Following", async () => {
    await b.goto("/app/community");
    await expect(b.getByText("No picks from people you follow yet")).toBeVisible();
    await b.getByRole("navigation", { name: "Feed scope" }).getByRole("link", { name: "Everyone" }).click();
    await expect(b).toHaveURL(/\/app\/community\?scope=everyone$/);
    await expect(b.getByRole("navigation", { name: "Feed scope" }).getByRole("link", { name: "Everyone" })).toHaveAttribute("aria-current", "page");
    await expect(b.getByText("Verified: every pick is timestamped before the game and graded automatically from the final score.")).toBeVisible();

    const pick = card(b, handleA, "Small sample, so only a lean.");
    await expect(pick).toHaveCount(1);
    // Markup in user text is text: it is shown literally and nothing is created from it.
    await expect(pick.getByText(ANALYSIS, { exact: true })).toBeVisible();
    await expect(pick.locator("script, b")).toHaveCount(0);
    expect(await b.evaluate(() => document.querySelectorAll("main script").length)).toBe(0);
    await expect(pick.getByText("Price when posted")).toBeVisible();
    await expect(pick.getByText("Upcoming", { exact: true })).toBeVisible();
    await expect(pick.getByText("Verified", { exact: true })).toBeVisible();
    await expect(pick.getByRole("link", { name: `${event.away_team.name} at ${event.home_team.name}` })).toHaveAttribute("href", `/app/games/${event.id}`);
    await expect(pick.getByRole("link", { name: /^0 comments/ })).toHaveAttribute("href", `/app/community/picks/${firstPickId}#comments`);
    await expect(pick.locator("time").first()).toHaveAttribute("datetime", /^\d{4}-\d\d-\d\dT/);

    // "Load more" appends the next page.
    const before = await b.getByRole("article").count();
    expect(before).toBeGreaterThanOrEqual(2);
    await expect(b.getByText(`Showing ${before} picks, newest first.`)).toBeVisible();
    await b.getByRole("button", { name: "Load more" }).click();
    await expect.poll(() => b.getByRole("article").count()).toBeGreaterThan(before);

    expect(await sidewaysOverflow(b), "feed").toBeLessThanOrEqual(1);
    await expectNoBannedCopy(b, "feed");

    // Follow from the profile, then the Following feed has the picks.
    await b.goto("/app/community?scope=everyone");
    await card(b, handleA, "Small sample, so only a lean.").getByRole("link", { name: `@${handleA}` }).click();
    await expect(b).toHaveURL(new RegExp(`/app/community/profiles/${handleA}$`));
    const follow = b.getByRole("button", { name: `Follow @${handleA}` });
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await follow.click();
    await expect(b.getByRole("button", { name: `Following @${handleA}` })).toHaveAttribute("aria-pressed", "true");
    await expect(b.getByRole("region", { name: "About" }).locator("dl > div").filter({ hasText: "Followers" }).locator("dd")).toHaveText("1");

    await b.goto("/app/community");
    await expect(b.getByRole("region", { name: "Picks from people you follow" }).getByRole("article")).toHaveCount(2);
    await expect(card(b, handleA, "Small sample, so only a lean.")).toHaveCount(1);
    await expect(card(b, handleA, "Second look at the same game.")).toHaveCount(1);

    await auditBothThemes(b, "feed", async () => {
      await expect(b.getByRole("article").first()).toBeVisible();
    });
  });

  test("like and unlike update the count, the word and aria-pressed", async () => {
    await b.goto("/app/community");
    const pick = card(b, handleA, "Small sample, so only a lean.");
    const like = pick.getByRole("button", { name: /^Like/ });
    await expect(like).toHaveAttribute("aria-pressed", "false");
    await expect(like).toHaveText(/^Like\s*0\s*likes$/);
    await like.click();
    await expect(like).toHaveAttribute("aria-pressed", "true");
    await expect(like).toHaveText(/^Liked\s*1\s*like$/);
    // It is stored: a reload shows the same.
    await b.reload();
    await expect(pick.getByRole("button", { name: /^Liked/ })).toHaveAttribute("aria-pressed", "true");
    await pick.getByRole("button", { name: /^Liked/ }).click();
    await expect(like).toHaveAttribute("aria-pressed", "false");
    await expect(like).toHaveText(/^Like\s*0\s*likes$/);
    const target = await like.boundingBox();
    expect(target!.height).toBeGreaterThanOrEqual(44);
  });

  test("comments: one is posted, a link and a banned phrase are rejected in plain words, and markup stays text", async () => {
    await b.goto("/app/community");
    await card(b, handleA, "Second look at the same game.").getByRole("link", { name: /comments/ }).click();
    await expect(b).toHaveURL(new RegExp(`/app/community/picks/${secondPickId}#comments$`));
    await expect(b.getByRole("heading", { level: 1, name: `Pick by @${handleA}` })).toBeVisible();
    const comments = b.getByRole("region", { name: "Comments" });
    await expect(comments.getByText("No comments yet")).toBeVisible();
    await expect(comments.getByText("Plain text only. No guarantees, no links and no selling picks.")).toBeVisible();
    const box = comments.getByLabel("Add a comment");

    await box.fill("See https://example.com for my numbers");
    await comments.getByRole("button", { name: "Post comment" }).click();
    await expect(comments.getByRole("alert")).toHaveText("Links aren't allowed. Remove the web address and try again.");
    await box.fill("guaranteed winner");
    await expect(comments.getByText("17 of 500 characters")).toBeVisible();
    await comments.getByRole("button", { name: "Post comment" }).click();
    await expect(comments.getByRole("alert")).toContainText("This text breaks a community rule (no results presented as certain).");
    await expect(comments.getByRole("listitem")).toHaveCount(0);

    await box.fill(COMMENT);
    await comments.getByRole("button", { name: "Post comment" }).click();
    await expect(comments.getByText("Comment posted.")).toBeVisible();
    const item = comments.getByRole("listitem").filter({ hasText: `@${handleB}` });
    await expect(item.getByText(COMMENT, { exact: true })).toBeVisible();
    await expect(item.locator("b")).toHaveCount(0);
    await expect(comments.getByText("1 comment", { exact: true })).toBeVisible();
    await expect(box).toHaveValue("");

    // The author of a comment can delete it; a second one is added and removed.
    await box.fill("A comment to delete");
    await comments.getByRole("button", { name: "Post comment" }).click();
    const extra = comments.getByRole("listitem").filter({ hasText: "A comment to delete" });
    await extra.getByRole("button", { name: "Delete your comment" }).click();
    await extra.getByRole("button", { name: "Delete comment" }).click();
    await expect(extra).toHaveCount(0);
    await expect(comments.getByText("1 comment", { exact: true })).toBeVisible();

    // Stored, and the other person sees it as text too, with Report but without Delete.
    await a.goto(`/app/community/picks/${secondPickId}`);
    const seen = a.getByRole("region", { name: "Comments" }).getByRole("listitem").filter({ hasText: `@${handleB}` });
    await expect(seen.getByText(COMMENT, { exact: true })).toBeVisible();
    await expect(seen.getByRole("button", { name: `Report comment by @${handleB}` })).toBeVisible();
    await expect(seen.getByRole("button", { name: /Delete/ })).toHaveCount(0);

    await b.reload();
    expect(await sidewaysOverflow(b), "pick page").toBeLessThanOrEqual(1);
    await expectNoBannedCopy(b, "pick page");
    await auditBothThemes(b, "pick page", async () => {
      await expect(b.getByRole("region", { name: "Comments" }).getByRole("listitem")).toHaveCount(1);
    });
  });

  test("the author is told about the follower and the comment, and the links open the new pages", async () => {
    await a.goto("/app/alerts");
    const list = a.getByRole("region", { name: "Notifications" });
    const follower = list.getByRole("listitem").filter({ hasText: "New follower" }).filter({ hasText: handleB });
    await expect(follower).toHaveCount(1);
    await expect(follower.getByRole("link", { name: /^Open/ })).toHaveAttribute("href", `/app/community/profiles/${handleB}`);
    const comment = list.getByRole("listitem").filter({ hasText: "Comment on your pick" }).first();
    await expect(comment.getByRole("link", { name: /^Open/ })).toHaveAttribute("href", `/app/community/picks/${secondPickId}`);
    // The comment text is not repeated in the notification.
    await expect(list.getByText("Which games is that sample from?")).toHaveCount(0);
    await comment.getByRole("link", { name: /^Open/ }).click();
    await expect(a).toHaveURL(new RegExp(`/app/community/picks/${secondPickId}$`));
    await expect(a.getByRole("heading", { level: 1, name: `Pick by @${handleA}` })).toBeVisible();
    await a.goto("/app/alerts");
    await follower.getByRole("link", { name: /^Open/ }).click();
    await expect(a.getByRole("heading", { level: 1, name: `@${handleB}` })).toBeVisible();

    // The three kinds have their own switches while the community is on.
    await a.goto("/app/settings");
    for (const name of ["New followers", "Comments on your picks", "Graded picks"]) await expect(a.getByRole("switch", { name, exact: true })).toBeChecked();
    await a.getByRole("switch", { name: "Graded picks", exact: true }).click();
    await a.reload();
    await expect(a.getByRole("switch", { name: "Graded picks", exact: true })).not.toBeChecked();
    await expect(a.getByRole("switch", { name: "New followers", exact: true })).toBeChecked();
    await a.getByRole("switch", { name: "Graded picks", exact: true }).click();
    await expect(a.getByRole("switch", { name: "Graded picks", exact: true })).toBeChecked();
  });

  test("a profile shows the bio as text, the counts and the record with its sample note and method", async ({ request }) => {
    await b.goto(`/app/community/profiles/${handleA}`);
    await expect(b.getByRole("heading", { level: 1, name: `@${handleA}` })).toBeVisible();
    await expect(b.getByText(/^Joined [A-Z][a-z]+ \d{4}$/)).toBeVisible();
    const about = b.getByRole("region", { name: "About" });
    await expect(about.getByText("Totals and pace. <b>bold</b>", { exact: true })).toBeVisible();
    await expect(about.locator("b")).toHaveCount(0);
    await expect(b.getByRole("link", { name: "Edit profile" })).toHaveCount(0);

    // No graded picks yet: the record says so, with the API's caution, method and caveat.
    const token = await adminToken(request);
    const record = (await (await request.get(`${API}/v1/community/profiles/${handleA}`, { headers: { authorization: `Bearer ${token}` } })).json()).record;
    const panel = b.getByRole("region", { name: "Graded record" });
    await expect(panel.getByText("No graded picks yet.", { exact: false })).toBeVisible();
    expect(record.sample_note).toMatch(/^Small sample: 0 graded picks/);
    await expect(panel.getByText(record.sample_note, { exact: true })).toBeVisible();
    await expect(panel.getByText(record.method, { exact: false })).toBeVisible();
    await expect(panel.getByText(record.caveat, { exact: true })).toBeVisible();
    await expect(b.getByRole("region", { name: "Picks" }).getByRole("article")).toHaveCount(2);

    expect(await sidewaysOverflow(b), "profile").toBeLessThanOrEqual(1);
    await expectNoBannedCopy(b, "profile");
    await auditBothThemes(b, "profile", async () => {
      await expect(b.getByRole("region", { name: "Graded record" })).toBeVisible();
    });

    // My own profile: an edit link and my lists.
    await a.goto(`/app/community/profiles/${handleA}`);
    await expect(a.getByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/app/community/settings");
    await expect(a.getByRole("button", { name: /^Follow/ })).toHaveCount(0);
    await a.getByRole("navigation", { name: "Profile lists" }).getByRole("link", { name: "1 follower" }).click();
    await expect(a).toHaveURL(/tab=followers$/);
    await expect(a.getByRole("region", { name: "Followers" }).getByRole("link", { name: `@${handleB}` })).toBeVisible();
    await a.getByRole("navigation", { name: "Profile lists" }).getByRole("link", { name: "0 following" }).click();
    await expect(a.getByText("You don't follow anyone yet")).toBeVisible();
  });

  test("a graded record shows the win rate with its interval and sample size, and a graded pick explains the delete lock", async ({ page, request }) => {
    // The seeded demo account has a public profile with graded picks.
    const login = await request.post(`${API}/v1/auth/login`, { data: { email: "demo@oddvex.test", password: "oddvex-demo-2026" } });
    const headers = { authorization: `Bearer ${(await login.json()).access_token}` };
    const me = await (await request.get(`${API}/v1/community/profile`, { headers })).json();
    expect(me.record.picks, "the demo profile has graded picks").toBeGreaterThan(0);
    expect(me.record.win_rate_interval, "and at least one of them was decided").toBeTruthy();

    await logIn(page, "demo@oddvex.test", "oddvex-demo-2026", `/app/community/profiles/${me.handle}`);
    const panel = page.getByRole("region", { name: "Graded record" });
    const figure = (label: string) => panel.locator("dl > div").filter({ has: page.getByText(label, { exact: true }) });
    await expect(figure("Graded picks").locator("dd").first()).toHaveText(String(me.record.picks));
    await expect(figure("Won, lost, push").locator("dd").first()).toHaveText(`${me.record.wins}-${me.record.losses}-${me.record.pushes}`);
    await expect(figure("Win rate").locator("dd").first()).toHaveText(`${(me.record.win_rate * 100).toFixed(1)}%`);
    const low = `${(me.record.win_rate_interval.low * 100).toFixed(1)}%`;
    const high = `${(me.record.win_rate_interval.high * 100).toFixed(1)}%`;
    await expect(figure("Win rate")).toContainText(`95% interval ${low} to ${high}, from ${me.record.wins + me.record.losses} decided`);
    await expect(figure("Average price").locator("dd").first()).toHaveText(/^[+−]\d+$/);
    await expect(figure("Flat-stake ROI").locator("dd").first()).toHaveText(/^[+−]?\d+\.\d%$/);
    await expect(panel.getByText(me.record.method, { exact: false })).toBeVisible();
    if (me.record.sample_note) await expect(panel.getByText(me.record.sample_note, { exact: true })).toBeVisible();
    await expect(panel.getByText(me.record.caveat, { exact: true })).toBeVisible();
    await expectNoBannedCopy(page, "profile with a graded record");
    expect(await audit(page), "profile with a graded record").toEqual([]);

    // A graded pick: its result in words, the final score, and why it can no longer be deleted.
    const graded = (await (await request.get(`${API}/v1/community/picks?handle=${me.handle}&status=graded&limit=1`, { headers })).json()).items[0];
    await page.goto(`/app/community/picks/${graded.id}`);
    const label = { won: "Won", lost: "Lost", push: "Push" }[graded.result as "won" | "lost" | "push"];
    await expect(page.getByRole("article").getByText(label, { exact: true })).toBeVisible();
    await expect(page.getByRole("article").getByText("Final score, away then home")).toBeVisible();
    await expect(page.getByRole("article").getByText(`${graded.final_score.away} to ${graded.final_score.home}`, { exact: true })).toBeVisible();
    await expect(page.getByText("Picks can't be deleted after the game starts, so records stay honest.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Delete pick" })).toHaveCount(0);
    await expectNoBannedCopy(page, "graded pick page");
    expect(await audit(page), "graded pick page").toEqual([]);

    // The graded-pick notification opens that kind of page.
    await page.goto("/app/alerts");
    const notice = page.getByRole("region", { name: "Notifications" }).getByRole("listitem").filter({ hasText: "Graded pick" }).first();
    await expect(notice.getByRole("link", { name: /^Open/ })).toHaveAttribute("href", /^\/app\/community\/picks\/[A-Za-z0-9]+$/);
    await notice.getByRole("link", { name: /^Open/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: `Pick by @${me.handle}` })).toBeVisible();
  });

  test("a report reaches the moderation queue; hiding the pick removes it for others and leaves the author a placeholder", async ({ page }) => {
    // The other person reports the first pick. The confirmation is neutral.
    await b.goto(`/app/community/picks/${firstPickId}`);
    await b.getByRole("button", { name: "Report this pick" }).click();
    const form = b.getByRole("form", { name: "Report this pick" });
    await expect(form.getByLabel("Reason").locator("option")).toHaveText(["Spam", "Harassment", "Encouraging betting", "Misleading claims", "Personal information", "Other"]);
    await form.getByLabel("Reason").selectOption({ label: "Misleading claims" });
    await form.getByLabel("Details (optional)").fill(`Reported by the end-to-end test ${handleB}`);
    await form.getByRole("button", { name: "Send report" }).click();
    await expect(b.getByText("Report received. A moderator will review it against the community guidelines. The person you reported is not told.")).toBeVisible();
    // The author cannot report their own pick: there is no button, and the API refuses.
    const own = await a.request.post("/api/ov/v1/community/reports", { data: { target_type: "pick", target_id: firstPickId, reason: "spam" } });
    expect(own.status()).toBe(422);

    await adminSignIn(page, "/app/admin/community");
    const overview = page.getByRole("region", { name: "Community overview" });
    await expect(overview.getByText("Open reports")).toBeVisible();
    const queue = page.getByRole("region", { name: "Report queue" });
    const report = queue.getByRole("listitem").filter({ hasText: `@${handleA}` }).filter({ hasText: `@${handleB}` });
    await expect(report).toHaveCount(1);
    await expect(report.getByRole("heading", { name: "Pick reported for misleading claims" })).toBeVisible();
    await expect(report.getByText("Target: Pick", { exact: true })).toBeVisible();
    // The excerpt is the stored text, shown as text.
    await expect(report.locator("blockquote")).toHaveText(ANALYSIS);
    await expect(report.locator("blockquote script, blockquote b")).toHaveCount(0);
    await expect(report.locator("dl > div").filter({ hasText: "Reporter" })).toContainText(`@${handleB}`);
    await expect(report.locator("dl > div").filter({ hasText: "Author" })).toContainText(`@${handleA}`);
    await expect(report.locator("dl > div").filter({ hasText: "Reason" })).toContainText("Misleading claims");
    await expect(report.getByText(`Reported by the end-to-end test ${handleB}`)).toBeVisible();
    for (const name of ["Dismiss", "Hide content", "Remove content", "Suspend author"]) await expect(report.getByRole("button", { name: new RegExp(`^${name}`) })).toBeVisible();

    // The moderation tab, with the queue filled and a confirm step open, in both themes.
    await auditBothThemes(page, "moderation tab", async () => {
      await expect(report).toHaveCount(1);
    });
    await report.getByRole("button", { name: /^Hide content/ }).click();
    await expect(report.getByText("It disappears from every public view", { exact: false })).toBeVisible();
    expect(await audit(page), "moderation confirm step").toEqual([]);
    expect(await sidewaysOverflow(page), "moderation tab").toBeLessThanOrEqual(1);

    // Cancelling changes nothing; a note is required; then the decision is confirmed.
    await report.getByRole("button", { name: "Cancel" }).click();
    await report.getByRole("button", { name: /^Hide content/ }).click();
    await report.getByLabel("Note").fill("ab");
    await report.getByRole("button", { name: "Confirm: hide content" }).click();
    await expect(report.getByText("Enter a note of at least 3 characters", { exact: false })).toBeVisible();
    await report.getByLabel("Note").fill(`End-to-end moderation ${handleA}`);
    await report.getByRole("button", { name: "Confirm: hide content" }).click();
    await expect(queue.getByText("Content hidden. It no longer appears in any public view", { exact: false })).toBeVisible();
    await expect(report).toHaveCount(0);

    // The decision is in the resolved list, with its note, and in the audit log.
    await page.getByRole("navigation", { name: "Report status" }).getByRole("link", { name: "Resolved" }).click();
    await expect(page).toHaveURL(/\/app\/admin\/community\?status=resolved$/);
    const resolved = queue.getByRole("listitem").filter({ hasText: `End-to-end moderation ${handleA}` });
    await expect(resolved).toContainText("Content hidden");
    await expect(resolved.getByText("Now hidden", { exact: true })).toBeVisible();
    // A decided report has no decision buttons left; hidden content can still be restored from here.
    await expect(resolved.getByRole("button")).toHaveText([/^Restore pick/]);
    expect(await audit(page), "moderation tab, resolved").toEqual([]);
    await page.goto("/app/admin/audit?action=community.report_resolved");
    await expect(page.getByRole("table", { name: "Audit log entries" }).getByRole("row").nth(1)).toContainText("community.report_resolved");

    // For the other person the pick is gone: from both feeds, and its page is not found.
    await b.goto("/app/community");
    await expect(card(b, handleA, "Second look at the same game.")).toHaveCount(1);
    await expect(card(b, handleA, "Small sample, so only a lean.")).toHaveCount(0);
    await b.goto("/app/community?scope=everyone");
    await expect(card(b, handleA, "Second look at the same game.")).toHaveCount(1);
    await expect(card(b, handleA, "Small sample, so only a lean.")).toHaveCount(0);
    await b.goto(`/app/community/picks/${firstPickId}`);
    await expect(b.getByRole("heading", { level: 1 })).toContainText("off the board");

    // The author still sees their own pick, with a placeholder instead of the text.
    await a.goto(`/app/community/picks/${firstPickId}`);
    await expect(a.getByRole("article").getByText("Removed by moderators.", { exact: true })).toBeVisible();
    await expect(a.getByText("Small sample, so only a lean.", { exact: false })).toHaveCount(0);
    await expect(a.getByText("Comments are closed on a pick that moderators removed.")).toBeVisible();
    expect(await audit(a), "author's view of a removed pick").toEqual([]);
  });

  test("blocking hides both people from each other and removes the follow", async () => {
    await b.goto(`/app/community/profiles/${handleA}`);
    await expect(b.getByRole("button", { name: `Following @${handleA}` })).toHaveAttribute("aria-pressed", "true");
    await b.getByRole("button", { name: `Block @${handleA}` }).click();
    const confirm = b.getByRole("group", { name: `Confirm blocking @${handleA}` });
    await expect(confirm).toContainText("You will no longer see their profile, picks or comments, and they will no longer see yours.");
    await expect(confirm).toContainText("that follow is removed");
    await confirm.getByRole("button", { name: "Cancel" }).click();
    await expect(b.getByRole("region", { name: "Picks" })).toBeVisible();
    await b.getByRole("button", { name: `Block @${handleA}` }).click();
    await b.getByRole("button", { name: "Block profile" }).click();
    await expect(b.getByText("You blocked this profile")).toBeVisible();
    await expect(b.getByRole("region", { name: "Picks" })).toHaveCount(0);
    await expect(b.getByRole("button", { name: /^Follow/ })).toHaveCount(0);

    // Their content is gone for the person who blocked.
    for (const path of ["/app/community", "/app/community?scope=everyone"]) {
      await b.goto(path);
      await expect(b.getByRole("region", { name: /^Picks from/ })).toBeVisible();
      await expect(b.getByRole("article").filter({ hasText: `@${handleA}` })).toHaveCount(0);
    }
    await b.goto(`/app/community/picks/${secondPickId}`);
    await expect(b.getByRole("heading", { level: 1 })).toContainText("off the board");

    // The blocked person is not told: the other profile simply is not found, and the follower is gone.
    await a.goto(`/app/community/profiles/${handleB}`);
    await expect(a.getByRole("heading", { level: 1 })).toContainText("off the board");
    await a.goto(`/app/community/profiles/${handleA}?tab=followers`);
    await expect(a.getByText("No followers yet")).toBeVisible();
    await a.goto(`/app/community/picks/${secondPickId}`);
    await expect(a.getByRole("region", { name: "Comments" }).getByText("No comments yet")).toBeVisible();

    // The block is listed in the settings and can be lifted there. The follow does not come back.
    await b.goto("/app/community/settings");
    const blocked = b.getByRole("region", { name: "Blocked profiles" });
    await expect(blocked.getByRole("link", { name: `@${handleA}` })).toBeVisible();
    await blocked.getByRole("button", { name: `Unblock @${handleA}` }).click();
    await expect(blocked.getByText("You haven't blocked anyone")).toBeVisible();
    await b.goto(`/app/community/profiles/${handleA}`);
    await expect(b.getByRole("button", { name: `Follow @${handleA}` })).toHaveAttribute("aria-pressed", "false");
    await expect(b.getByRole("region", { name: "About" }).locator("dl > div").filter({ hasText: "Followers" }).locator("dd")).toHaveText("0");
    await b.goto("/app/community");
    await expect(b.getByText("No picks from people you follow yet")).toBeVisible();
  });

  test("community settings: the profile is edited, and the page says what deleting the account removes", async () => {
    await a.goto("/app/community/settings");
    const profile = a.getByRole("region", { name: "Profile", exact: true });
    await expect(profile.getByLabel("Handle")).toHaveValue(handleA);
    await expect(profile.getByRole("checkbox", { name: "Make my profile public" })).toBeChecked();
    await profile.getByLabel("Bio (optional)").fill("dm me for more");
    await profile.getByRole("button", { name: "Save profile" }).click();
    await expect(profile.getByText("This text breaks a community rule (no asking people to contact you elsewhere).", { exact: false })).toBeVisible();
    await profile.getByLabel("Bio (optional)").fill("Totals and pace, edited.");
    await profile.getByRole("button", { name: "Save profile" }).click();
    await expect(profile.getByText("Profile saved.")).toBeVisible();
    await a.goto(`/app/community/profiles/${handleA}`);
    await expect(a.getByRole("region", { name: "About" }).getByText("Totals and pace, edited.", { exact: true })).toBeVisible();

    await a.goto("/app/community/settings");
    const leaving = a.getByRole("region", { name: "Leaving the community" });
    await expect(leaving).toContainText("Deleting your OddVex account removes your community profile, your follows in both directions, your likes, your blocks, the reports you made, your comments and every pick you posted, graded ones included.");
    await expect(leaving.getByRole("link", { name: "account settings" })).toHaveAttribute("href", "/app/settings");
    await expect(a.getByRole("region", { name: "Blocked profiles" }).getByText("You haven't blocked anyone")).toBeVisible();
    expect(await sidewaysOverflow(a), "community settings").toBeLessThanOrEqual(1);
    await auditBothThemes(a, "community settings", async () => {
      await expect(a.getByRole("region", { name: "Leaving the community" })).toBeVisible();
    });
    await a.goto("/app/settings");
    await expect(a.getByText("everything you posted in the community, graded picks included", { exact: false })).toBeVisible();
  });

  test("the leaderboard needs its own flag, shows the API's caveat and keeps its filters in the URL", async ({ request }) => {
    // Off: a real 404 and no link, while the rest of the community works.
    expect((await a.goto("/app/community/leaderboard"))?.status()).toBe(404);
    await expect(a.getByRole("heading", { level: 1 })).toContainText("off the board");
    await a.goto("/app/community");
    await expect(a.getByRole("navigation", { name: "Community sections" }).getByRole("link", { name: "Feed" })).toBeVisible();
    await expect(a.getByRole("link", { name: "Leaderboard" })).toHaveCount(0);

    await setFlag(request, "community_leaderboard", true);
    try {
      const token = await adminToken(request);
      const board = await (await request.get(`${API}/v1/community/leaderboard?window=all`, { headers: { authorization: `Bearer ${token}` } })).json();

      await a.goto("/app/community");
      await a.getByRole("navigation", { name: "Community sections" }).getByRole("link", { name: "Leaderboard" }).click();
      await expect(a).toHaveURL(/\/app\/community\/leaderboard$/);
      expect((await a.goto("/app/community/leaderboard"))?.status()).toBe(200);
      await expect(a.getByRole("heading", { level: 1, name: "Leaderboard" })).toBeVisible();
      await expect(a.getByText(board.caveat, { exact: true })).toBeVisible();
      await expect(a.getByText("Ranked by the lower end of the win-rate interval, not the win rate itself, so a small sample can't top the list.")).toBeVisible();
      await expect(a.getByText(board.method, { exact: true })).toBeVisible();

      const ranking = a.getByRole("region", { name: "Ranking", exact: true });
      const table = ranking.getByRole("table");
      const empty = ranking.getByText("Nobody is ranked in this view yet");
      await expect(table.or(empty)).toBeVisible();
      if (board.items.length > 0) {
        // Rows are shown in the API's order, with the sample size and the interval.
        // The average price and the flat-stake return sit next to the win rate, so a record built on short prices reads for what it is.
        await expect(table.getByRole("columnheader")).toHaveText(["Rank", "Profile", "Graded picks", "Win rate", "95% interval", "Average price", "Flat-stake return"]);
        await expect(ranking.getByText("Neither changes the order.", { exact: false })).toBeVisible();
        const rows = table.locator("tbody tr");
        await expect(rows).toHaveCount(board.items.length);
        type Row = { rank: number; handle: string; record: { picks: number; average_price: { american: number } | null; flat_stake_roi: number | null } };
        for (const [index, row] of (board.items as Row[]).entries()) {
          await expect(rows.nth(index).locator("td").first()).toHaveText(String(row.rank));
          await expect(rows.nth(index).getByRole("link", { name: `@${row.handle}` })).toHaveAttribute("href", `/app/community/profiles/${row.handle}`);
          await expect(rows.nth(index).locator("td").nth(1)).toHaveText(String(row.record.picks));
          await expect(rows.nth(index).locator("td").nth(3)).toHaveText(/^\d+\.\d% to \d+\.\d%$/);
          const american = row.record.average_price ? Math.round(row.record.average_price.american) : null;
          await expect(rows.nth(index).locator("td").nth(4)).toHaveText(american === null ? "n/a" : american > 0 ? `+${american}` : `−${Math.abs(american)}`);
          const roi = row.record.flat_stake_roi;
          await expect(rows.nth(index).locator("td").nth(5)).toHaveText(roi === null ? "n/a" : /^([+−]\d+\.\d|0\.0)%$/);
        }
      } else {
        await expect(empty).toBeVisible();
      }

      // No prizes and no heat: a ranking is described, not celebrated.
      const copy = await ownCopy(a);
      for (const word of ["trophy", "medal", "champion", "winner", "flame", "hot", "🔥", "🏆", "🥇"]) expect(new RegExp(`(^|[^a-z])${word}([^a-z]|$)`).test(copy), `leaderboard says "${word}"`).toBe(false);
      await expectNoBannedCopy(a, "leaderboard");
      expect(await sidewaysOverflow(a), "leaderboard").toBeLessThanOrEqual(1);

      // Filters live in the URL.
      await a.getByRole("navigation", { name: "Window" }).getByRole("link", { name: "Last 30 days" }).click();
      await expect(a).toHaveURL(/\/app\/community\/leaderboard\?window=30d$/);
      await expect(a.getByRole("navigation", { name: "Window" }).getByRole("link", { name: "Last 30 days" })).toHaveAttribute("aria-current", "page");
      const league = a.getByRole("navigation", { name: "League" }).getByRole("link").nth(1);
      await league.click();
      await expect(a).toHaveURL(/\/app\/community\/leaderboard\?league=[a-z0-9_]+&window=30d$/);
      await expect(table.or(empty)).toBeVisible();
      await a.reload();
      await expect(a.getByRole("navigation", { name: "Window" }).getByRole("link", { name: "Last 30 days" })).toHaveAttribute("aria-current", "page");

      await a.goto("/app/community/leaderboard");
      await auditBothThemes(a, "leaderboard", async () => {
        await expect(a.getByRole("heading", { level: 1, name: "Leaderboard" })).toBeVisible();
      });
    } finally {
      await setFlag(request, "community_leaderboard", false);
    }
    expect((await a.goto("/app/community/leaderboard"))?.status()).toBe(404);
  });

  test("turning the community off again removes the pages and the entry points", async ({ page, request }) => {
    await adminSignIn(page, "/app/admin/flags");
    const flag = page.getByRole("region", { name: "Feature flags", exact: true }).getByRole("listitem").filter({ has: page.getByRole("heading", { name: "community", exact: true }) });
    await flag.getByRole("button", { name: /^Turn off/ }).click();
    await flag.getByRole("button", { name: "Confirm: turn off community" }).click();
    await expect(flag.getByText("Flag turned off.", { exact: false })).toBeVisible();
    expect((await flags(request)).community).toBe(false);
    await expect(page.getByRole("navigation", { name: "Admin sections" }).getByRole("link", { name: "Community" })).toHaveCount(0);

    for (const path of ["/app/community", `/app/community/picks/${secondPickId}`, `/app/community/profiles/${handleA}`, "/app/community/settings"]) {
      expect((await a.goto(path))?.status(), path).toBe(404);
    }
    await a.goto("/app");
    await openMoreOnPhone(a);
    await expect(a.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Community" })).toHaveCount(0);
    // Notifications from while it was on keep their text and lose their link.
    await a.goto("/app/alerts");
    await expect(a.getByRole("region", { name: "Notifications" }).getByRole("listitem").filter({ hasText: "New follower" })).toHaveCount(1);
    await expect(a.locator('a[href^="/app/community"]')).toHaveCount(0);
  });
});
