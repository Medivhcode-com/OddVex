import { expect, test } from "./fixtures";
import { adminSignIn, API, logIn, openMoreOnPhone, PASSWORD, setFlag, sidewaysOverflow, signUp } from "./helpers";

const ADMIN_PATHS = ["/app/admin", "/app/admin/users", "/app/admin/flags", "/app/admin/audit", "/app/admin/outbox", "/app/admin/users?q=a", "/app/admin/anything-else"];

// These tests change shared state (a flag, accounts), so they run in order and always put it back.
test.describe.configure({ mode: "serial" });

test.describe("admin console", () => {
  test.afterAll(async ({ request }) => {
    await setFlag(request, "tracker_analytics", true);
  });

  test("everyone who is not an admin gets a real 404 on every admin path", async ({ page, request }) => {
    for (const path of ADMIN_PATHS) {
      expect((await page.goto(path))?.status(), `signed out ${path}`).toBe(404);
      await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
    }
    await signUp(page, "notadmin2");
    for (const path of ADMIN_PATHS) {
      expect((await page.goto(path))?.status(), `signed in ${path}`).toBe(404);
      await expect(page.getByRole("heading", { level: 1 })).toContainText("off the board");
      await expect(page.getByText("Feature flags")).toHaveCount(0);
    }
    // Admin routes are not reachable through the browser bridge either, for reads or writes.
    expect((await request.get("/api/ov/v1/admin/users")).status()).toBe(404);
    expect((await page.request.put("/api/ov/v1/admin/flags/community", { data: { enabled: true } })).status()).toBe(404);
    expect((await (await request.get(`${API}/v1/flags`)).json()).flags.community).toBe(false);
  });

  test("an admin moves between the tabs, and none scrolls sideways", async ({ page }) => {
    await adminSignIn(page);
    const tabs = page.getByRole("navigation", { name: "Admin sections" });
    for (const [name, path, landmark] of [
      ["Users", "/app/admin/users", "Accounts"],
      ["Flags", "/app/admin/flags", "Feature flags"],
      ["Audit", "/app/admin/audit", "Audit log"],
      ["Email outbox", "/app/admin/outbox", "Email outbox"],
      ["Overview", "/app/admin", "Service"],
    ] as const) {
      await tabs.getByRole("link", { name, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(tabs.getByRole("link", { name, exact: true })).toHaveAttribute("aria-current", "page");
      await expect(page.getByRole("region", { name: landmark, exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
      expect(await sidewaysOverflow(page), path).toBeLessThanOrEqual(1);
      expect((await page.goto(path))?.status(), path).toBe(200);
    }
    await openMoreOnPhone(page);
    await expect(page.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Admin", exact: true }).filter({ visible: true })).toBeVisible();
  });

  test("suspend with a reason signs the person out, unsuspend lets them back in, and a plan change shows in their settings", async ({ page, browser }) => {
    const context = await browser.newContext();
    const member = await context.newPage();
    try {
      const email = await signUp(member, "suspendee");
      await adminSignIn(page, "/app/admin/users");

      // Search, with the filters kept in the URL.
      await page.getByLabel("Name or email").fill(email);
      await page.getByRole("button", { name: "Apply" }).click();
      await expect(page).toHaveURL(/\/app\/admin\/users\?q=e2e-suspendee/);
      const accounts = page.getByRole("region", { name: "Accounts", exact: true });
      const row = accounts.getByRole("listitem").filter({ hasText: email });
      await expect(row).toHaveCount(1);
      await expect(accounts.getByRole("listitem")).toHaveCount(1);
      await expect(row.getByText("Active", { exact: true })).toBeVisible();
      await expect(row.getByText("Plan: free")).toBeVisible();

      // Suspending needs a reason and a second click; cancelling changes nothing.
      await row.getByRole("button", { name: /^Suspend/ }).click();
      await row.getByRole("button", { name: "Cancel" }).click();
      await expect(row.getByText("Active", { exact: true })).toBeVisible();
      await row.getByRole("button", { name: /^Suspend/ }).click();
      await row.getByLabel("Reason").fill("ab");
      await row.getByRole("button", { name: "Confirm suspension" }).click();
      await expect(row.getByText("Enter a reason of at least 3 characters", { exact: false })).toBeVisible();
      await expect(row.getByText("Active", { exact: true })).toBeVisible();
      await row.getByLabel("Reason").fill("End-to-end test of suspension");
      await row.getByRole("button", { name: "Confirm suspension" }).click();
      await expect(row.getByText("Account suspended.", { exact: false })).toBeVisible();
      await expect(row.getByText("Suspended", { exact: true })).toBeVisible();
      await page.goto(`/app/admin/users?status=suspended&q=${encodeURIComponent(email)}`);
      await expect(row.getByText("Suspended", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Status")).toHaveValue("suspended");
      await page.goto(`/app/admin/users?status=active&q=${encodeURIComponent(email)}`);
      await expect(page.getByText("No accounts match these filters")).toBeVisible();

      // The suspended person's next page load is signed out, with a neutral explanation.
      await member.goto("/app/tracker");
      await expect(member).toHaveURL(/\/login\?suspended=1$/);
      await expect(member.getByText("This account is suspended")).toBeVisible();
      await expect(member.getByRole("main").getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "/contact");
      expect((await context.cookies()).find((cookie) => cookie.name === "ov_session")).toBeUndefined();
      await member.goto("/app/tracker");
      await expect(member.getByText("Log in to track your bets")).toBeVisible();
      // Logging in is refused with the same explanation, and no session is created.
      await member.goto("/login");
      await member.getByLabel("Email").fill(email);
      await member.getByLabel("Password").fill(PASSWORD);
      await member.getByRole("button", { name: "Log in" }).click();
      const refused = member.getByRole("main").getByRole("alert");
      await expect(refused).toContainText("This account is suspended");
      await expect(refused).toContainText("ask for a copy of your data");
      await expect(refused.getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "/contact");
      await expect(member).toHaveURL(/\/login$/);

      // The audit tab lists the suspension with its reason, and no email address.
      await page.goto("/app/admin/audit");
      await page.getByLabel("Action").fill("admin.user_suspended");
      await page.getByRole("button", { name: "Apply" }).click();
      await expect(page).toHaveURL(/action=admin\.user_suspended/);
      const log = page.getByRole("table", { name: "Audit log entries" });
      await expect(log.getByRole("row").filter({ hasText: "Reason: End-to-end test of suspension" }).first()).toContainText("admin.user_suspended");
      await expect(log.getByRole("row").filter({ hasText: "Reason: End-to-end test of suspension" }).first()).toContainText("status: active to suspended");
      expect(await page.getByRole("main").innerText()).not.toContain("@oddvex.test");

      // Unsuspend, then the same password works again.
      await page.goto(`/app/admin/users?q=${encodeURIComponent(email)}`);
      await expect(row.getByRole("button", { name: /^Suspend/ })).toHaveCount(0);
      await row.getByRole("button", { name: /^Unsuspend/ }).click();
      await row.getByRole("button", { name: "Confirm unsuspend" }).click();
      await expect(row.getByText("Account unsuspended.", { exact: false })).toBeVisible();
      await expect(row.getByText("Active", { exact: true })).toBeVisible();
      await logIn(member, email, PASSWORD);

      // A plan change is confirmed, says nothing was charged, and shows in the person's settings.
      await row.getByRole("button", { name: /^Set plan to premium/ }).click();
      await expect(row.getByText("This is not a purchase.", { exact: false })).toBeVisible();
      await row.getByRole("button", { name: "Confirm plan: premium" }).click();
      await expect(row.getByText("Plan set to premium.", { exact: false })).toBeVisible();
      await expect(row.getByText("Plan: premium")).toBeVisible();
      await member.goto("/app/settings");
      await expect(member.getByRole("region", { name: "Account" }).getByText("Premium", { exact: true })).toBeVisible();
      await row.getByRole("button", { name: /^Set plan to free/ }).click();
      await row.getByRole("button", { name: "Confirm plan: free" }).click();
      await expect(row.getByText("Plan: free")).toBeVisible();

      // The outbox lists the confirmation email queued at signup and says nothing was sent.
      await page.goto("/app/admin/outbox");
      await expect(page.getByText("Nothing is actually sent")).toBeVisible();
      await expect(page.getByRole("table", { name: /Queued emails/ }).getByRole("row").filter({ hasText: email }).first()).toContainText("Confirm your email address");
      const html = await page.content();
      expect(html).not.toMatch(/verify-email\?token=/);
    } finally {
      await context.close();
    }
  });

  test("the audit log pages back with a cursor and filters by account", async ({ page, request }) => {
    await adminSignIn(page, "/app/admin/audit");
    const log = page.getByRole("table", { name: "Audit log entries" });
    await expect(log).toBeVisible();
    await page.getByRole("link", { name: "Load older" }).click();
    await expect(page).toHaveURL(/before=/);
    await expect(log.or(page.getByText("No audited actions yet"))).toBeVisible();
    await page.getByRole("link", { name: "Back to newest" }).click();
    await expect(page).toHaveURL(/\/app\/admin\/audit$/);
    // From an account on the Users tab to that account's entries.
    await page.goto("/app/admin/users?q=e2e-admin");
    await page.getByRole("link", { name: /audit entries for Ops Admin/ }).click();
    await expect(page).toHaveURL(/\/app\/admin\/audit\?user_id=[A-Za-z0-9]+$/);
    await expect(log.getByRole("row").nth(1)).toBeVisible();
    await page.goto("/app/admin/audit?action=no.such.action");
    await expect(page.getByText("No entries match these filters")).toBeVisible();
    expect((await (await request.get(`${API}/v1/flags`)).json()).flags.tracker_analytics).toBe(true);
  });

  test("turning a flag off hides the feature and its page, and turning it on brings both back", async ({ page, browser, request }) => {
    const context = await browser.newContext();
    const member = await context.newPage();
    try {
      await signUp(member, "flagged");
      await expect(member.getByRole("main").getByRole("link", { name: "Analytics", exact: true })).toBeVisible();

      await adminSignIn(page, "/app/admin/flags");
      const flags = page.getByRole("region", { name: "Feature flags", exact: true });
      const flag = flags.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "tracker_analytics", exact: true }) });
      await expect(flag.getByText("On", { exact: true })).toBeVisible();
      await expect(flag.getByText("Tracker analytics: odds bands", { exact: false })).toBeVisible(); // the API's description

      // Community flags repeat the review warning before anything can be confirmed. Nothing is confirmed here.
      const community = flags.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "community", exact: true }) });
      await expect(community.getByText("Off", { exact: true })).toBeVisible();
      await community.getByRole("button", { name: /^Turn on/ }).click();
      await expect(community.getByText("Review required first")).toBeVisible();
      await expect(community.getByRole("note").getByText("legal review and a responsible-gambling review", { exact: false })).toBeVisible();
      await community.getByRole("button", { name: "Cancel" }).click();
      await expect(community.getByText("Off", { exact: true })).toBeVisible();
      expect((await (await request.get(`${API}/v1/flags`)).json()).flags.community).toBe(false);

      // The same holds for every community_* flag the API defines, such as the leaderboard.
      const known = (await (await request.get(`${API}/v1/flags`)).json()).flags as Record<string, boolean>;
      if ("community_leaderboard" in known) {
        const leaderboard = flags.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "community_leaderboard", exact: true }) });
        await leaderboard.getByRole("button", { name: /^Turn on/ }).click();
        await expect(leaderboard.getByRole("note").getByText("legal review and a responsible-gambling review", { exact: false })).toBeVisible();
        await leaderboard.getByRole("button", { name: "Cancel" }).click();
        expect((await (await request.get(`${API}/v1/flags`)).json()).flags.community_leaderboard).toBe(false);
      }

      try {
        await flag.getByRole("button", { name: /^Turn off/ }).click();
        await flag.getByRole("button", { name: "Confirm: turn off tracker_analytics" }).click();
        await expect(flag.getByText("Flag turned off.", { exact: false })).toBeVisible();
        await expect(flag.getByText("Off", { exact: true })).toBeVisible();
        await expect(flag.getByText("Overridden, default on")).toBeVisible();

        // For an ordinary account the page is a real 404 and the entry point is gone.
        expect((await member.goto("/app/tracker/analytics"))?.status()).toBe(404);
        await expect(member.getByRole("heading", { level: 1 })).toContainText("off the board");
        await member.goto("/app/tracker");
        await expect(member.getByRole("heading", { level: 1, name: "Bet tracker" })).toBeVisible();
        await expect(member.getByRole("main").getByRole("link", { name: "Analytics", exact: true })).toHaveCount(0);

        await flag.getByRole("button", { name: /^Turn on/ }).click();
        await flag.getByRole("button", { name: "Confirm: turn on tracker_analytics" }).click();
        await expect(flag.getByText("Flag turned on.", { exact: false })).toBeVisible();
        await expect(flag.getByText("On", { exact: true })).toBeVisible();
      } finally {
        await setFlag(request, "tracker_analytics", true);
      }
      expect((await member.goto("/app/tracker/analytics"))?.status()).toBe(200);
      await expect(member.getByText("No settled bets yet")).toBeVisible();

      // The value screen is hidden the same way, navigation entry included.
      try {
        await setFlag(request, "value_screen", false);
        expect((await member.goto("/app/value"))?.status()).toBe(404);
        await member.goto("/app/odds");
        await expect(member.getByRole("heading", { level: 1, name: "Odds" })).toBeVisible();
        await expect(member.getByRole("link", { name: "Compare the best prices with the consensus of the other books" })).toHaveCount(0);
        await expect(member.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Value", exact: true })).toHaveCount(0);
      } finally {
        await setFlag(request, "value_screen", true);
      }
      expect((await member.goto("/app/value"))?.status()).toBe(200);
    } finally {
      await setFlag(request, "tracker_analytics", true);
      await setFlag(request, "value_screen", true);
      await context.close();
    }
  });
});
