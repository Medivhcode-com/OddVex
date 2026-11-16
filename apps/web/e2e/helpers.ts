import { expect, type Page } from "./fixtures";
import type { APIRequestContext } from "@playwright/test";

export const API = "http://localhost:8210";
export const PASSWORD = "correct-horse-battery";
export const ADMIN_EMAIL = "e2e-admin@oddvex.test";

/** Creates a fresh account through the signup form and lands on the tracker. Returns its email. */
export async function signUp(page: Page, tag: string) {
  const email = `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@oddvex.test`;
  await page.goto("/signup?next=/app/tracker");
  await page.getByLabel("Name").fill("Casey Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  // The signup URL also ends in /app/tracker (its ?next= value), so wait for a signed-in signal too.
  await expect(page).toHaveURL(/^[^?]*\/app\/tracker$/);
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  return email;
}

export async function logIn(page: Page, email: string, password: string, next = "/app/tracker") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
}

/**
 * Makes sure the configured administrator exists and has the role, and returns an API token.
 *
 * The API grants the role from configuration (`ODDVEX_ADMIN_EMAILS`), never through the
 * client, and only once the address has been confirmed. No email is sent in this build, so
 * the confirmation link is read from the test-only outbox route.
 */
export async function adminToken(request: APIRequestContext): Promise<string> {
  const credentials = { email: ADMIN_EMAIL, password: PASSWORD };
  let response = await request.post(`${API}/v1/auth/login`, { data: credentials });
  if (!response.ok()) response = await request.post(`${API}/v1/auth/register`, { data: { ...credentials, display_name: "Ops Admin", age_confirmed: true } });
  expect(response.ok(), "admin account can sign in").toBe(true);
  let { access_token: token, user } = (await response.json()) as { access_token: string; user: { role: string; email_verified?: boolean } };
  if (user.role !== "admin" && !user.email_verified) {
    const headers = { authorization: `Bearer ${token}` };
    const outbox = `${API}/v1/dev/email-outbox/latest?to=${encodeURIComponent(ADMIN_EMAIL)}&template=verify_email`;
    if (!(await request.get(outbox)).ok()) await request.post(`${API}/v1/auth/verify-email/request`, { headers });
    let link = "";
    await expect
      .poll(async () => {
        const latest = await request.get(outbox);
        link = latest.ok() ? ((await latest.json()).token ?? "") : "";
        return link;
      })
      .not.toBe("");
    expect((await request.post(`${API}/v1/auth/verify-email/confirm`, { data: { token: link } })).ok(), "admin email confirmed").toBe(true);
    response = await request.post(`${API}/v1/auth/login`, { data: credentials });
    ({ access_token: token, user } = await response.json());
  }
  const me = await (await request.get(`${API}/v1/me`, { headers: { authorization: `Bearer ${token}` } })).json();
  expect(me.role, "configured admin has the admin role").toBe("admin");
  return token;
}

/** Signs in as the configured administrator through the login form. */
export async function adminSignIn(page: Page, next = "/app/admin") {
  await adminToken(page.request);
  await logIn(page, ADMIN_EMAIL, PASSWORD, next);
}

export async function setFlag(request: APIRequestContext, key: string, enabled: boolean) {
  const token = await adminToken(request);
  const response = await request.put(`${API}/v1/admin/flags/${key}`, { data: { enabled }, headers: { authorization: `Bearer ${token}` } });
  expect(response.ok(), `set ${key}=${enabled}`).toBe(true);
}

/** Opens the bottom bar's "More" sheet on the phone layout; a no-op on desktop, where the sidebar is visible. */
export async function openMoreOnPhone(page: Page) {
  const more = page.locator("summary", { hasText: "More" });
  if (await more.isVisible()) await more.click();
}

export async function sidewaysOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}
