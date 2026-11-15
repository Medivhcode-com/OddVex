"use client";

import Link from "next/link";
import { useActionState } from "react";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { loginAction, signupAction, type AuthState } from "@/lib/auth-actions";

const initial: AuthState = {};

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(loginAction, initial);
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Field id="email" name="email" type="email" label="Email" autoComplete="email" defaultValue={state.values?.email} required />
      <Field id="password" name="password" type="password" label="Password" autoComplete="current-password" required />
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
