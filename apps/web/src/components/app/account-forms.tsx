"use client";

import { useActionState, useState } from "react";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { changePasswordAction } from "@/lib/auth-actions";
import { clientApi, ClientApiError } from "@/lib/client-api";

export function ChangePasswordForm() {
  const [state, action, pending] = useActionState(changePasswordAction, {} as { error?: string; done?: boolean });
  return (
    <form action={action} className="space-y-3" key={state.done ? "done" : "form"}>
      {state.error ? <Notice tone="error">{state.error}</Notice> : null}
      {state.done ? <Notice tone="accent">Password changed. Other devices have been signed out.</Notice> : null}
      <Field id="current_password" name="current_password" type="password" label="Current password" autoComplete="current-password" className="max-w-xs" />
      <Field id="new_password" name="new_password" type="password" label="New password" autoComplete="new-password" hint="At least 10 characters." className="max-w-xs" />
      <Button type="submit" variant="secondary" disabled={pending}>
        {pending ? "Changing password" : "Change password"}
      </Button>
    </form>
  );
}

export function ExportDataButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      const data = await clientApi<unknown>("/v1/me/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `oddvex-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "The export failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3">
      <Button type="button" variant="secondary" onClick={download} disabled={busy}>
        {busy ? "Preparing export" : "Download my data"}
      </Button>
      {error ? <Notice tone="error">{error}</Notice> : null}
    </div>
  );
}
