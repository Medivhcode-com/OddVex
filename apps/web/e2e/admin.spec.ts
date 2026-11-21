import { expect, test } from "./fixtures";
import type { APIRequestContext } from "@playwright/test";
import { ADMIN_EMAIL, adminSignIn, API, logIn, openMoreOnPhone, PASSWORD, setFlag, sidewaysOverflow, signUp } from "./helpers";

/** A fresh account made through the API, with a token for direct API calls. */
async function member(request: APIRequestContext, tag: string) {
  const email = `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@oddvex.test`;
  const response = await request.post(`${API}/v1/auth/register`, { data: { email, password: PASSWORD, display_name: `Member ${tag}`, age_confirmed: true } });
  expect(response.ok(), `register ${tag}`).toBe(true);
  const token = ((await response.json()) as { access_token: string }).access_token;
  return { email, headers: { authorization: `Bearer ${token}` } };
}

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
      // It says how to ask for a copy of the data or for deletion: the contact address, or the contact page while none is set.
      const ended = member.getByRole("main").getByRole("status").filter({ hasText: "This account is suspended" });
      await expect(ended).toContainText("To ask for a copy of your data, or for the account and its data to be deleted");
      await expect(ended.getByRole("link", { name: /^(contact page|\S+@\S+)$/ })).toHaveAttribute("href", /^(\/contact|mailto:\S+@\S+)$/);
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
      await expect(refused.getByRole("link", { name: /^(contact page|\S+@\S+)$/ })).toHaveAttribute("href", /^(\/contact|mailto:\S+@\S+)$/);
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

  test("an admin exports a member's data with a reason and deletes the account behind a typed confirmation", async ({ page, request }) => {
    const owner = await member(request, "datarights");
    await adminSignIn(page, `/app/admin/users?q=${encodeURIComponent(owner.email)}`);
    const accounts = page.getByRole("region", { name: "Accounts", exact: true });
    const row = accounts.getByRole("listitem").filter({ hasText: owner.email });
    await expect(row).toHaveCount(1);

    // Export: a reason is required, must not name the account, and the API's document is downloaded.
    await row.getByRole("button", { name: /^Export data/ }).click();
    const exportForm = row.getByRole("form", { name: /^Export the data of/ });
    await exportForm.getByLabel("Reason").fill("ab");
    await exportForm.getByRole("button", { name: "Download export" }).click();
    await expect(exportForm.getByText("Enter a reason of at least 3 characters", { exact: false })).toBeVisible();
    await exportForm.getByLabel("Reason").fill(`Request from ${owner.email}`);
    await exportForm.getByRole("button", { name: "Download export" }).click();
    await expect(exportForm.getByText("Leave the email address out of the reason", { exact: false })).toBeVisible();
    await exportForm.getByLabel("Reason").fill("Owner request REF-E2E-1");
    const [download] = await Promise.all([page.waitForEvent("download"), exportForm.getByRole("button", { name: "Download export" }).click()]);
    expect(download.suggestedFilename()).toMatch(/^oddvex-export-[A-Za-z0-9_-]+-\d{4}-\d{2}-\d{2}\.json$/);
    const chunks: Buffer[] = [];
    for await (const chunk of await download.createReadStream()) chunks.push(chunk as Buffer);
    const text = Buffer.concat(chunks).toString("utf8");
    const data = JSON.parse(text);
    expect(data.user.email).toBe(owner.email);
    expect(Array.isArray(data.bets)).toBe(true);
    expect(text.toLowerCase()).not.toContain("password_hash");
    await expect(exportForm.getByText("Export downloaded as", { exact: false })).toBeVisible();
    await exportForm.getByRole("button", { name: "Close" }).click();

    // The API's 409 is shown for the administrator's own account, for export and for delete.
    await page.goto(`/app/admin/users?q=${encodeURIComponent(ADMIN_EMAIL)}`);
    const own = accounts.getByRole("listitem").filter({ hasText: ADMIN_EMAIL });
    await own.getByRole("button", { name: /^Export data/ }).click();
    await own.getByLabel("Reason").fill("Checking the refusal REF-E2E-2");
    await own.getByRole("button", { name: "Download export" }).click();
    await expect(own.getByText("You cannot export your own account here.", { exact: false })).toBeVisible();
    await own.getByRole("button", { name: "Cancel" }).click();
    await own.getByRole("button", { name: /^Delete account/ }).click();
    await own.getByLabel("Reason").fill("Checking the refusal REF-E2E-2");
    await own.getByLabel("Type the account's email address to confirm").fill(ADMIN_EMAIL);
    await own.getByRole("button", { name: "Delete account permanently" }).click();
    await expect(own.getByText("You cannot delete your own account here.", { exact: false })).toBeVisible();
    await own.getByRole("button", { name: "Cancel" }).click();

    // Delete: the button stays off until the account's address is typed; then the account is gone.
    await page.goto(`/app/admin/users?q=${encodeURIComponent(owner.email)}`);
    await row.getByRole("button", { name: /^Delete account/ }).click();
    await expect(row.getByText("This cannot be undone.", { exact: false })).toBeVisible();
    const confirm = row.getByRole("button", { name: "Delete account permanently" });
    await row.getByLabel("Reason").fill("Owner request REF-E2E-3");
    await expect(confirm).toBeDisabled();
    await row.getByLabel("Type the account's email address to confirm").fill("someone-else@oddvex.test");
    await expect(confirm).toBeDisabled();
    await row.getByLabel("Type the account's email address to confirm").fill(` ${owner.email.toUpperCase()} `);
    await expect(confirm).toBeEnabled();
    await confirm.click();
    await expect(accounts.getByText("Account deleted.", { exact: false })).toBeVisible();
    await expect(row).toHaveCount(0);
    expect((await request.post(`${API}/v1/auth/login`, { data: { email: owner.email, password: PASSWORD } })).status()).toBe(401);

    // Both are in the audit log with their reasons and without the address.
    await page.goto("/app/admin/audit?action=admin.user_exported");
    await expect(page.getByRole("table", { name: "Audit log entries" }).getByRole("row").filter({ hasText: "REF-E2E-1" }).first()).toContainText("admin.user_exported");
    await page.goto("/app/admin/audit?action=admin.user_deleted");
    await expect(page.getByRole("table", { name: "Audit log entries" }).getByRole("row").filter({ hasText: "REF-E2E-3" }).first()).toContainText("admin.user_deleted");
    expect(await page.getByRole("main").innerText()).not.toContain(owner.email);
  });

  test("the moderation queue shows what was reported after an edit or a deletion, flags an author's edit and restores content", async ({ page, request, browser }) => {
    const token = `${Date.now().toString(36).slice(-6)}${Math.floor(Math.random() * 1296).toString(36).padStart(2, "0")}`;
    const a = await member(request, "moda");
    const b = await member(request, "modb");
    const handleA = `ma_${token}`;
    const handleB = `mb_${token}`;
    await setFlag(request, "community", true);
    try {
      expect((await request.put(`${API}/v1/community/profile`, { headers: a.headers, data: { handle: handleA, bio: `Original bio ${token}`, is_public: true } })).ok()).toBe(true);
      expect((await request.put(`${API}/v1/community/profile`, { headers: b.headers, data: { handle: handleB, bio: null, is_public: true } })).ok()).toBe(true);

      // A pick by A, a comment on it by B. A reports the comment, and B deletes it.
      const upcoming = (await (await request.get(`${API}/v1/events?status=upcoming`)).json()) as { id: string; start_time: string }[];
      upcoming.sort((x, y) => y.start_time.localeCompare(x.start_time));
      let pickId = "";
      for (const event of upcoming) {
        const created = await request.post(`${API}/v1/community/picks`, { headers: a.headers, data: { event_id: event.id, market: "moneyline", outcome_key: "home", analysis: `Pick text ${token}` } });
        if (created.ok()) {
          pickId = (await created.json()).id;
          break;
        }
      }
      expect(pickId, "a pick on an upcoming game").not.toBe("");
      const comment = await request.post(`${API}/v1/community/picks/${pickId}/comments`, { headers: b.headers, data: { body: `Comment text ${token}` } });
      expect(comment.ok()).toBe(true);
      const commentId = (await comment.json()).id as string;
      expect((await request.post(`${API}/v1/community/reports`, { headers: a.headers, data: { target_type: "comment", target_id: commentId, reason: "harassment" } })).ok()).toBe(true);
      expect((await request.delete(`${API}/v1/community/comments/${commentId}`, { headers: b.headers })).status()).toBe(204);

      // B reports A's profile, and A then edits the bio.
      expect((await request.post(`${API}/v1/community/reports`, { headers: b.headers, data: { target_type: "profile", target_id: handleA, reason: "personal_information" } })).ok()).toBe(true);
      expect((await request.put(`${API}/v1/community/profile`, { headers: a.headers, data: { handle: handleA, bio: `Edited bio ${token}`, is_public: true } })).ok()).toBe(true);

      await adminSignIn(page, "/app/admin/community");
      const queue = page.getByRole("region", { name: "Report queue" });
      const deleted = queue.getByRole("listitem").filter({ hasText: `Comment text ${token}` });
      await expect(deleted).toHaveCount(1);
      await expect(deleted.getByText("Target deleted", { exact: true })).toBeVisible();
      await expect(deleted.getByText("As reported", { exact: true })).toBeVisible();
      await expect(deleted.locator("blockquote")).toHaveText(`Comment text ${token}`);
      await expect(deleted.getByText("The item no longer exists.")).toBeVisible();

      const edited = queue.getByRole("listitem").filter({ hasText: `Original bio ${token}` });
      await expect(edited).toHaveCount(1);
      await expect(edited.getByText("Changed since the report", { exact: true })).toBeVisible();
      await expect(edited.locator("blockquote")).toHaveText([`Original bio ${token}`, `Edited bio ${token}`]);
      await expect(edited.getByText(/Earlier removals of this author.s content: 0/)).toBeVisible();

      // Hide the profile. Editing it again does not bring it back: it returns to the queue, marked as the author's edit.
      await edited.getByRole("button", { name: /^Hide content/ }).click();
      await expect(edited.getByText("only Restore does", { exact: false })).toBeVisible();
      await edited.getByLabel("Note").fill(`Hidden by the end-to-end test ${token}`);
      await edited.getByRole("button", { name: "Confirm: hide content" }).click();
      await expect(queue.getByText("Content hidden.", { exact: false })).toBeVisible();
      expect((await request.get(`${API}/v1/community/profiles/${handleA}`, { headers: b.headers })).status()).toBe(404);
      // A edits the hidden profile in the settings. Changing only the public setting queues no review, so none is promised;
      // a changed bio goes back to review, and the form says so. Either way the profile stays hidden.
      const ownerContext = await browser.newContext();
      try {
        const owner = await ownerContext.newPage();
        await logIn(owner, a.email, PASSWORD, "/app/community/settings");
        await expect(owner.getByText("If you change the handle or the bio, the profile stays hidden and goes back to a moderator for review.", { exact: false })).toBeVisible();
        const form = owner.getByRole("region", { name: "Profile" });
        await form.getByLabel("Make my profile public").uncheck();
        await form.getByRole("button", { name: "Save profile" }).click();
        await expect(form.getByText("Profile saved. It stays hidden: only a moderator can make it visible again.")).toBeVisible();
        await form.getByLabel("Make my profile public").check();
        await form.getByLabel("Bio (optional)").fill(`Second edit ${token}`);
        await form.getByRole("button", { name: "Save profile" }).click();
        await expect(form.getByText("Profile saved. It stays hidden, and the change goes to a moderator for review.")).toBeVisible();
      } finally {
        await ownerContext.close();
      }
      expect((await request.get(`${API}/v1/community/profiles/${handleA}`, { headers: b.headers })).status()).toBe(404);

      await page.reload();
      const authorEdit = queue.getByRole("listitem").filter({ hasText: `Second edit ${token}` }).filter({ hasText: "Edited by its author" });
      await expect(authorEdit).toHaveCount(1);
      await expect(authorEdit.getByRole("heading", { name: "Profile edited after moderation" })).toBeVisible();
      await expect(authorEdit.getByText("It stays hidden or removed until an administrator restores it.", { exact: false })).toBeVisible();
      await expect(authorEdit.getByText(/Earlier removals of this author.s content: 1/)).toBeVisible();
      await expect(authorEdit.getByText("Now hidden", { exact: true })).toBeVisible();

      // Restore needs a note and a second click; then the profile is visible again and the entry is closed.
      await authorEdit.getByRole("button", { name: /^Restore profile/ }).click();
      await authorEdit.getByLabel("Note").fill("ab");
      await authorEdit.getByRole("button", { name: "Confirm: restore profile" }).click();
      await expect(authorEdit.getByText("Enter a note of at least 3 characters", { exact: false })).toBeVisible();
      await authorEdit.getByLabel("Note").fill(`Restored by the end-to-end test ${token}`);
      await authorEdit.getByRole("button", { name: "Confirm: restore profile" }).click();
      await expect(queue.getByText("Content restored.", { exact: false })).toBeVisible();
      await expect(authorEdit).toHaveCount(0);
      expect((await request.get(`${API}/v1/community/profiles/${handleA}`, { headers: b.headers })).status()).toBe(200);

      await page.getByRole("navigation", { name: "Report status" }).getByRole("link", { name: "Resolved" }).click();
      await expect(queue.getByRole("listitem").filter({ hasText: `Restored by the end-to-end test ${token}` }).first()).toContainText("Content restored");
    } finally {
      await setFlag(request, "community", false);
    }
  });
});

