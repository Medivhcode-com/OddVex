"use server";

import { redirect } from "next/navigation";
import { api, ApiError, ApiUnavailableError } from "@/lib/api";
import { clearSession, safeNext, setSession } from "@/lib/session";
import type { AuthResponse } from "@/lib/types";

export type AuthState = { error?: string; fields?: Record<string, string>; values?: Record<string, string> };

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Try again in a moment.";
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many attempts. Wait a minute, then try again.";
    return error.message || fallback;
  }
  return fallback;
}

export async function loginAction(_: AuthState, form: FormData): Promise<AuthState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const values = { email };
  if (!email || !password) return { error: "Enter your email and password.", values };
  let auth: AuthResponse;
  try {
    auth = await api<AuthResponse>("/v1/auth/login", { method: "POST", body: { email, password } });
  } catch (error) {
    return { error: describe(error, "That email and password don't match an account."), values };
  }
  await setSession(auth.access_token, auth.expires_in);
  redirect(safeNext(String(form.get("next") ?? "")));
}

export async function signupAction(_: AuthState, form: FormData): Promise<AuthState> {
  const email = String(form.get("email") ?? "").trim();
  const displayName = String(form.get("display_name") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const ageConfirmed = form.get("age_confirmed") === "on";
  const values = { email, display_name: displayName };
  const fields: Record<string, string> = {};
  if (!/^\S+@\S+\.\S+$/.test(email)) fields.email = "Enter a valid email address.";
  if (!displayName) fields.display_name = "Enter a name to show on your account.";
  if (password.length < 10) fields.password = "Use at least 10 characters.";
  if (!ageConfirmed) fields.age_confirmed = "You must be 21 or over to use OddVex.";
  if (Object.keys(fields).length) return { fields, values };
  let auth: AuthResponse;
  try {
    auth = await api<AuthResponse>("/v1/auth/register", {
      method: "POST",
      body: { email, password, display_name: displayName, age_confirmed: true },
    });
  } catch (error) {
    return { error: describe(error, "The account could not be created."), values };
  }
  await setSession(auth.access_token, auth.expires_in);
  redirect(safeNext(String(form.get("next") ?? "")));
}

export async function logoutAction() {
  await clearSession();
  redirect("/");
}

export async function deleteAccountAction(_: AuthState, form: FormData): Promise<AuthState> {
  if (String(form.get("confirm") ?? "").trim().toUpperCase() !== "DELETE") {
    return { error: "Type DELETE to confirm." };
  }
  try {
    await api("/v1/me", { method: "DELETE", auth: true });
  } catch (error) {
    return { error: describe(error, "The account could not be deleted.") };
  }
  await clearSession();
  redirect("/?account=deleted");
}

export async function changePasswordAction(_: AuthState & { done?: boolean }, form: FormData): Promise<AuthState & { done?: boolean }> {
  const current = String(form.get("current_password") ?? "");
  const next = String(form.get("new_password") ?? "");
  if (!current) return { error: "Enter your current password." };
  if (next.length < 10) return { error: "Use at least 10 characters for the new password." };
  if (next === current) return { error: "The new password must be different from the current one." };
  let auth: AuthResponse;
  try {
    auth = await api<AuthResponse>("/v1/me/password", { method: "POST", auth: true, body: { current_password: current, new_password: next } });
  } catch (error) {
    return { error: describe(error, "The password was not changed.") };
  }
  // Changing the password invalidates every earlier session, so this one gets the fresh token.
  await setSession(auth.access_token, auth.expires_in);
  return { done: true };
}
