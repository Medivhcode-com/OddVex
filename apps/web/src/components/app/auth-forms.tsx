"use client";

import Link from "next/link";
import { startTransition, useActionState, useEffect, useRef } from "react";
import { SuspendedNotice } from "@/components/app/suspended-notice";
import { Button, ButtonLink, Field, Notice } from "@/components/ui/primitives";
import {
  confirmEmailAction,
  loginAction,
  requestEmailVerificationAction,
  requestPasswordResetAction,
  resetPasswordAction,
  signupAction,
  type AuthState,
  type ConfirmEmailState,
  type ResetRequestState,
  type VerificationRequestState,
} from "@/lib/auth-actions";

const initial: AuthState = {};

export function LoginForm({ next, notice, suspended = false }: { next: string; notice?: string; suspended?: boolean }) {
  const [state, action, pending] = useActionState(loginAction, initial);
  const errorRef = useRef<HTMLDivElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const submittedPassword = useRef<string | null>(null);

  // Submitting through `action` alone makes React reset the whole form when a failed attempt
  // returns, which also wiped anything typed in the meantime. Dispatching the action ourselves
  // leaves the fields alone, so the email stays and a second attempt works on the same page.
  // Without JavaScript the form still posts through `action`.
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    submittedPassword.current = String(data.get("password") ?? "");
    startTransition(() => action(data));
  }

  useEffect(() => {
    if (!state.error && !state.suspended) return;
    // Move focus to the message so keyboard and screen reader users land on what went wrong.
    errorRef.current?.focus();
    // Clear the rejected password, unless a new one was typed while the request was running.
    const field = passwordRef.current;
    if (field && field.value === submittedPassword.current) field.value = "";
  }, [state]);

  return (
    <form action={action} onSubmit={submit} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      {notice && !state.error && !state.suspended ? <Notice tone="accent" role="status">{notice}</Notice> : null}
      {suspended && !state.error && !state.suspended ? <SuspendedNotice role="status" /> : null}
      {state.error || state.suspended ? (
        <div ref={errorRef} tabIndex={-1} className="rounded-cell">
          {state.suspended ? <SuspendedNotice role="alert" /> : <Notice tone="error">{state.error}</Notice>}
        </div>
      ) : null}
      <Field id="email" name="email" type="email" label="Email" autoComplete="email" defaultValue={state.values?.email} required />
      <Field ref={passwordRef} id="password" name="password" type="password" label="Password" autoComplete="current-password" required />
      <p className="-mt-1 text-sm">
        <Link href="/forgot-password" className="inline-flex min-h-11 items-center text-muted underline underline-offset-4 hover:text-ink">
          Forgot password?
        </Link>
      </p>
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Logging in" : "Log in"}
      </Button>
      <p className="text-center text-sm text-muted">
        New to OddVex?{" "}
        <Link href={`/signup?next=${encodeURIComponent(next)}`} className="text-ink underline underline-offset-4">
          Create an account
        </Link>
      </p>
    </form>
  );
}

const PREVIEW_EMAIL_NOTE = "In this preview no email is actually sent, so the link will not arrive in your inbox.";

export function ForgotPasswordForm() {
  const [state, action, pending] = useActionState(requestPasswordResetAction, {} as ResetRequestState);
  if (state.done) {
    return (
      <div className="space-y-4">
        <Notice tone="accent" role="status" title="Check your email">
          If an account exists for that address, we&rsquo;ve sent a link to set a new password. The link works once and
          then expires.
        </Notice>
        <Notice tone="warn">{PREVIEW_EMAIL_NOTE}</Notice>
        <p className="text-center text-sm text-muted">
          <Link href="/login" className="text-ink underline underline-offset-4">
            Back to log in
          </Link>
        </p>
      </div>
    );
  }
  return (
    <form action={action} className="space-y-4" noValidate>
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Field id="email" name="email" type="email" label="Email" autoComplete="email" defaultValue={state.values?.email} error={state.fields?.email} required />
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Sending link" : "Send reset link"}
      </Button>
      <Notice tone="warn">{PREVIEW_EMAIL_NOTE}</Notice>
      <p className="text-center text-sm text-muted">
        Remembered it?{" "}
        <Link href="/login" className="text-ink underline underline-offset-4">
          Log in
        </Link>
      </p>
    </form>
  );
}

function RequestNewLink() {
  return (
    <p className="text-sm text-muted">
      <Link href="/forgot-password" className="text-ink underline underline-offset-4">
        Request a new reset link
      </Link>
    </p>
  );
}

export function ResetPasswordForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState(resetPasswordAction, {} as AuthState & { expired?: boolean });
  if (state.expired) {
    return (
      <div className="space-y-4">
        <Notice tone="error">{state.error}</Notice>
        <RequestNewLink />
      </div>
    );
  }
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="token" value={token} />
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Field
        id="new_password"
        name="new_password"
        type="password"
        label="New password"
        autoComplete="new-password"
        hint="At least 10 characters."
        error={state.fields?.new_password}
        required
      />
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Saving password" : "Set new password"}
      </Button>
      <p className="text-sm text-muted">Setting a new password signs you out everywhere. You then log in with the new one.</p>
    </form>
  );
}

/**
 * Asks for a new confirmation link for the signed-in account. The answer is neutral, and says
 * plainly that this preview sends no email.
 */
export function ResendVerification({ variant = "secondary" }: { variant?: "primary" | "secondary" }) {
  const [state, action, pending] = useActionState(requestEmailVerificationAction, {} as VerificationRequestState);
  return (
    <form action={action} className="space-y-3">
      <Button type="submit" variant={variant} disabled={pending}>
        {pending ? "Sending link" : "Send a new verification link"}
      </Button>
      <div aria-live="polite" className="space-y-3">
        {state.error ? <Notice tone="error" role="status">{state.error}</Notice> : null}
        {state.done ? (
          <>
            <Notice tone="accent" role="status">
              A new confirmation link has been queued for your address. It works once and expires after 24 hours.
            </Notice>
            <Notice tone="warn">{PREVIEW_EMAIL_NOTE}</Notice>
          </>
        ) : null}
      </div>
    </form>
  );
}

export function ConfirmEmailForm({ token, canResend = false }: { token: string; canResend?: boolean }) {
  const [state, action, pending] = useActionState(confirmEmailAction, {} as ConfirmEmailState);
  if (state.expired) {
    return (
      <div className="space-y-4">
        <Notice tone="error">{state.error}</Notice>
        {canResend ? (
          <ResendVerification />
        ) : (
          <p className="text-sm text-muted">
            <Link href="/login?next=/app/settings" className="text-ink underline underline-offset-4">
              Log in
            </Link>{" "}
            to request a new link from Settings.
          </p>
        )}
      </div>
    );
  }
  if (state.done) {
    return (
      <div className="space-y-4">
        <Notice tone="accent" role="status">
          Email address confirmed.
        </Notice>
        <ButtonLink href="/app" variant="secondary">
          Open the app
        </ButtonLink>
      </div>
    );
  }
  return (
    <form action={action} className="space-y-4">
      <input type="hidden" name="token" value={token} />
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Confirming" : "Confirm email address"}
      </Button>
    </form>
  );
}

/** Shown when a reset or confirmation page is opened without the token from the link. */
export function MissingLinkToken({ reset }: { reset?: boolean }) {
  return (
    <div className="space-y-4">
      <Notice tone="error">This link is incomplete. Open the full link from the message, or start again.</Notice>
      {reset ? <RequestNewLink /> : null}
    </div>
  );
}

export function SignupForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(signupAction, initial);
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Field id="display_name" name="display_name" label="Name" autoComplete="nickname" defaultValue={state.values?.display_name} error={state.fields?.display_name} required />
      <Field id="email" name="email" type="email" label="Email" autoComplete="email" defaultValue={state.values?.email} error={state.fields?.email} required />
      <Field id="password" name="password" type="password" label="Password" autoComplete="new-password" hint="At least 10 characters." error={state.fields?.password} required />
      <div>
        <label className="flex min-h-11 items-start gap-3 text-sm">
          <input
            type="checkbox"
            name="age_confirmed"
            className="mt-0.5 size-5 shrink-0 accent-[var(--ov-accent)]"
            aria-describedby={state.fields?.age_confirmed ? "age-error" : undefined}
            aria-invalid={state.fields?.age_confirmed ? true : undefined}
          />
          <span>I am 21 or older, and I understand OddVex provides information only and does not take bets.</span>
        </label>
        {state.fields?.age_confirmed ? (
          <p id="age-error" className="mt-1 text-sm text-error">
            {state.fields.age_confirmed}
          </p>
        ) : null}
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Creating account" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted">
        By creating an account you agree to the{" "}
        <Link href="/terms" className="underline underline-offset-4">terms</Link> and{" "}
        <Link href="/privacy" className="underline underline-offset-4">privacy policy</Link>.
      </p>
      <p className="text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href={`/login?next=${encodeURIComponent(next)}`} className="text-ink underline underline-offset-4">
          Log in
        </Link>
      </p>
    </form>
  );
}
