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
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  return email;
}

export async function logIn(page: Page, email: string, password: string, next = "/app/tracker") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
}

/**
 * Signs in as the configured administrator. The API grants the role to this address through
 * configuration (`ODDVEX_ADMIN_EMAILS`), never through the client. The account is created on
 * first use and reused afterwards (the other viewport's run, other spec files).
 */
export async function adminSignIn(page: Page, next = "/app/admin") {
  await page.goto(`/signup?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Name").fill("Ops Admin");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Log out" }).or(page.getByRole("main").getByRole("alert"))).toBeVisible();
  if (await page.getByRole("main").getByRole("alert").isVisible().catch(() => false)) {
    await logIn(page, ADMIN_EMAIL, PASSWORD, next);
  }
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
}

/** An API token for the administrator, for restoring state the UI test may have left behind. */
export async function adminToken(request: APIRequestContext): Promise<string | null> {
  const login = await request.post(`${API}/v1/auth/login`, { data: { email: ADMIN_EMAIL, password: PASSWORD } });
  if (login.ok()) return (await login.json()).access_token as string;
  const register = await request.post(`${API}/v1/auth/register`, { data: { email: ADMIN_EMAIL, password: PASSWORD, display_name: "Ops Admin", age_confirmed: true } });
  return register.ok() ? ((await register.json()).access_token as string) : null;
}

export async function setFlag(request: APIRequestContext, key: string, enabled: boolean) {
  const token = await adminToken(request);
  if (!token) throw new Error("No admin token: the flag could not be set.");
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
