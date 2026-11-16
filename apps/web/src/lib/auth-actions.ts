"use server";

import { redirect } from "next/navigation";
import { api, ApiError, ApiUnavailableError } from "@/lib/api";
import { clearSession, safeNext, setSession } from "@/lib/session";
import type { AuthResponse } from "@/lib/types";

export type AuthState = { error?: string; fields?: Record<string, string>; values?: Record<string, string>; suspended?: boolean };

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
    // The API answers this only after the correct password, so it reveals nothing to a guesser.
    if (error instanceof ApiError && error.code === "account_suspended") return { suspended: true, values };
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

export type ResetRequestState = { error?: string; fields?: Record<string, string>; values?: Record<string, string>; done?: boolean };

/**
 * Asks the API to queue a reset link. The answer is the same whether or not an account
 * exists, so this never reveals which addresses are registered.
 */
export async function requestPasswordResetAction(_: ResetRequestState, form: FormData): Promise<ResetRequestState> {
  const email = String(form.get("email") ?? "").trim();
  const values = { email };
  if (!/^\S+@\S+\.\S+$/.test(email)) return { fields: { email: "Enter a valid email address." }, values };
  try {
    await api("/v1/auth/password-reset/request", { method: "POST", body: { email } });
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) return { fields: { email: "Enter a valid email address." }, values };
    if (error instanceof ApiError && error.status === 404) return { error: "Password reset is switched off right now.", values };
    return { error: describe(error, "The request could not be sent. Try again."), values };
  }
  return { done: true };
}

const LINK_EXPIRED = "This link has expired or was already used.";

export async function resetPasswordAction(_: AuthState & { expired?: boolean }, form: FormData): Promise<AuthState & { expired?: boolean }> {
  const token = String(form.get("token") ?? "");
  const password = String(form.get("new_password") ?? "");
  if (password.length < 10) return { fields: { new_password: "Use at least 10 characters." } };
  if (password.length > 128) return { fields: { new_password: "Use 128 characters or fewer." } };
  try {
    await api("/v1/auth/password-reset/confirm", { method: "POST", body: { token, new_password: password } });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 400 || error.status === 422)) return { error: LINK_EXPIRED, expired: true };
    if (error instanceof ApiError && error.status === 404) return { error: "Password reset is switched off right now." };
    return { error: describe(error, "The password was not changed.") };
  }
  // The reset signs out every earlier session, including one in this browser.
  await clearSession();
  redirect("/login?reset=done");
}

export type ConfirmEmailState = AuthState & { done?: boolean; expired?: boolean };

export async function confirmEmailAction(_: ConfirmEmailState, form: FormData): Promise<ConfirmEmailState> {
  const token = String(form.get("token") ?? "");
  try {
    await api("/v1/auth/verify-email/confirm", { method: "POST", body: { token } });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 400 || error.status === 422)) return { error: LINK_EXPIRED, expired: true };
    if (error instanceof ApiError && error.status === 404) return { error: "Email confirmation is switched off right now." };
    return { error: describe(error, "The address could not be confirmed. Try again.") };
  }
  return { done: true };
}

export type VerificationRequestState = { error?: string; done?: boolean };

/** Queues a new confirmation link for the signed-in account. In this preview nothing is emailed. */
export async function requestEmailVerificationAction(): Promise<VerificationRequestState> {
  try {
    await api("/v1/auth/verify-email/request", { method: "POST", auth: true });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { error: "Log in again to request a new link." };
    if (error instanceof ApiError && error.status === 404) return { error: "Email confirmation is switched off right now." };
    if (error instanceof ApiError && error.status === 429) return { error: "You have asked for several links in a short time. Wait a few minutes, then try again." };
    return { error: describe(error, "The request could not be sent. Try again.") };
  }
  return { done: true };
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
