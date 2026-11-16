"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActionState, useState } from "react";
import clsx from "clsx";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { adminFlagAction, adminUserAction, type AdminActionState } from "@/lib/admin-actions";

const TABS = [
  { href: "/app/admin", label: "Overview" },
  { href: "/app/admin/users", label: "Users" },
  { href: "/app/admin/flags", label: "Flags" },
  { href: "/app/admin/audit", label: "Audit" },
  { href: "/app/admin/outbox", label: "Email outbox" },
];

export function AdminTabs() {
  const pathname = usePathname();
  return (
    <nav aria-label="Admin sections" className="-mx-1 mb-6 flex max-w-full gap-1 overflow-x-auto px-1 py-1">
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={clsx(
              "inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-sm font-medium transition-colors",
              active ? "border-ink bg-ink text-bg" : "border-line text-muted hover:border-line-strong hover:text-ink",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

function Result({ state }: { state: AdminActionState }) {
  return (
    <div aria-live="polite">
      {state.error ? <Notice tone="error" role="status">{state.error}</Notice> : null}
      {state.ok ? <Notice tone="accent" role="status">{state.ok}</Notice> : null}
    </div>
  );
}

type UserMode = "suspend" | "unsuspend" | "plan" | null;

/**
 * Suspend, unsuspend and plan changes for one account. Each needs a second, explicit click,
 * and the outcome is shown in place. The change itself is a server action.
 */
export function UserActions({ user }: { user: { id: string; display_name: string; role: string; status: string; plan: string } }) {
  const [mode, setMode] = useState<UserMode>(null);
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminUserAction(previous, form);
    if (next.ok) setMode(null);
    return next;
  }, {} as AdminActionState);
  const suspended = user.status === "suspended";
  const otherPlan = user.plan === "premium" ? "free" : "premium";
  const who = user.display_name;

  return (
    <div className="space-y-3">
      {mode === null ? (
        <div className="flex flex-wrap gap-2">
          {suspended ? (
            <Button type="button" variant="secondary" onClick={() => setMode("unsuspend")}>
              Unsuspend<span className="sr-only"> {who}</span>
            </Button>
          ) : user.role === "admin" ? null : (
            <Button type="button" variant="danger" onClick={() => setMode("suspend")}>
              Suspend<span className="sr-only"> {who}</span>
            </Button>
          )}
          <Button type="button" variant="secondary" onClick={() => setMode("plan")}>
            Set plan to {otherPlan}<span className="sr-only"> for {who}</span>
          </Button>
        </div>
      ) : (
        <form action={action} className="space-y-3 rounded-cell border border-line-strong p-3" aria-label={`Confirm change for ${who}`}>
          <input type="hidden" name="user_id" value={user.id} />
          <input type="hidden" name="intent" value={mode} />
          {mode === "suspend" ? (
            <>
              <p className="text-sm">
                Suspend {who}? Their sessions stop working and they can&rsquo;t log in. Their data is kept, and they can still ask for a copy or for deletion.
              </p>
              <Field id={`reason-${user.id}`} name="reason" label="Reason" hint="Required. Saved in the audit log, not shown to the person." maxLength={500} required />
            </>
          ) : null}
          {mode === "unsuspend" ? <p className="text-sm">Unsuspend {who}? They can log in again, and sessions that have not expired work again.</p> : null}
          {mode === "plan" ? (
            <>
              <input type="hidden" name="plan" value={otherPlan} />
              <p className="text-sm">
                Set the plan of {who} to {otherPlan}? This is not a purchase. Nothing is charged, and OddVex has no billing.
              </p>
            </>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant={mode === "suspend" ? "danger" : "primary"} disabled={pending}>
              {pending ? "Saving" : mode === "suspend" ? "Confirm suspension" : mode === "unsuspend" ? "Confirm unsuspend" : `Confirm plan: ${otherPlan}`}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMode(null)} disabled={pending}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      <Result state={state} />
    </div>
  );
}

/** Turns one feature flag on or off, after a confirm step that repeats any warning for that flag. */
export function FlagToggle({ flag, warning }: { flag: { key: string; enabled: boolean }; warning: string | null }) {
  const [confirming, setConfirming] = useState(false);
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminFlagAction(previous, form);
    if (next.ok) setConfirming(false);
    return next;
  }, {} as AdminActionState);
  const turnOn = !flag.enabled;
  const verb = turnOn ? "Turn on" : "Turn off";

  return (
    <div className="space-y-3">
      {confirming ? (
        <form action={action} className="space-y-3 rounded-cell border border-line-strong p-3" aria-label={`Confirm change to ${flag.key}`}>
          <input type="hidden" name="key" value={flag.key} />
          <input type="hidden" name="enabled" value={turnOn ? "true" : "false"} />
          {turnOn && warning ? (
            <Notice tone="warn" title="Review required first">
              {warning}
            </Notice>
          ) : null}
          <p className="text-sm">
            {verb} <span className="num">{flag.key}</span> for everyone? The change is written to the audit log.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant={turnOn && warning ? "danger" : "primary"} disabled={pending}>
              {pending ? "Saving" : `Confirm: ${verb.toLowerCase()} ${flag.key}`}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setConfirming(false)} disabled={pending}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <Button type="button" variant="secondary" onClick={() => setConfirming(true)}>
          {verb}<span className="sr-only"> {flag.key}</span>
        </Button>
      )}
      <Result state={state} />
    </div>
  );
}
