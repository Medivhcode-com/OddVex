"use client";

import { useActionState } from "react";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { deleteAccountAction, type AuthState } from "@/lib/auth-actions";

const initial: AuthState = {};

export function DeleteAccountForm() {
  const [state, action, pending] = useActionState(deleteAccountAction, initial);
  return (
    <form action={action} className="space-y-3">
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      <Field id="confirm" name="confirm" label="Type DELETE to confirm" autoComplete="off" className="max-w-xs" />
      <Button type="submit" variant="danger" disabled={pending}>
        {pending ? "Deleting account" : "Delete account and data"}
      </Button>
    </form>
  );
}
