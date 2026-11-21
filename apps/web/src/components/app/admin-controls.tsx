"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useActionState, useContext, useState, type ReactNode } from "react";
import clsx from "clsx";
import { Button, Field, Notice } from "@/components/ui/primitives";
import { adminExportUserAction, adminFlagAction, adminReportAction, adminRestoreAction, adminUserAction, type AdminActionState } from "@/lib/admin-actions";

const TABS = [
  { href: "/app/admin", label: "Overview" },
  { href: "/app/admin/users", label: "Users" },
  { href: "/app/admin/flags", label: "Flags" },
  { href: "/app/admin/audit", label: "Audit" },
  { href: "/app/admin/outbox", label: "Email outbox" },
];

/** The Community tab (moderation) exists only while the `community` feature flag is on. */
export function AdminTabs({ community = false }: { community?: boolean }) {
  const pathname = usePathname();
  const tabs = community ? [...TABS, { href: "/app/admin/community", label: "Community" }] : TABS;
  return (
    <nav aria-label="Admin sections" className="-mx-1 mb-6 flex max-w-full gap-1 overflow-x-auto px-1 py-1">
      {tabs.map((tab) => {
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

type UserMode = "suspend" | "unsuspend" | "plan" | "export" | "delete" | null;

const AccountResultContext = createContext<(message: string) => void>(() => {});

/**
 * Wraps the list of accounts. A deleted account leaves the list when the page is refreshed, so
 * the outcome of a deletion is shown here, above the list, where it stays.
 */
export function AccountList({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  return (
    <AccountResultContext.Provider value={setMessage}>
      <div aria-live="polite" className={message ? "border-b border-line p-4 sm:px-5" : undefined}>
        {message ? <Notice tone="accent" role="status">{message}</Notice> : null}
      </div>
      {children}
    </AccountResultContext.Provider>
  );
}

/** Saves `text` as a file in the browser. */
function saveFile(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Export for an owner who cannot sign in: a reason (saved in the audit log), then the API's
 * JSON document is downloaded. The export itself is a server action; the file is made here.
 */
function ExportForm({ user, onDone }: { user: { id: string; display_name: string }; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await adminExportUserAction(user.id, reason);
      if (result.error || !result.document || !result.filename) {
        setError(result.error ?? "The export failed. Nothing was changed.");
        return;
      }
      saveFile(result.filename, result.document);
      setDone(`Export downloaded as ${result.filename}. It is the owner's data: pass it on to them only, once you know the request is theirs.`);
    } catch {
      setError("The export failed. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-cell border border-line-strong p-3" aria-label={`Export the data of ${user.display_name}`}>
      <p className="text-sm">
        Download everything OddVex stores about {user.display_name}, the same file the owner gets from Settings. Use it for a request from an owner who can&rsquo;t sign in. Nothing in the account changes.
      </p>
      <Field id={`export-reason-${user.id}`} name="reason" label="Reason" hint="Required, such as the reference of the owner's request. Saved in the audit log. Don't include the email address." maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} required />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Preparing export" : "Download export"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone} disabled={busy}>
          {done ? "Close" : "Cancel"}
        </Button>
      </div>
      <Result state={{ error: error ?? undefined, ok: done ?? undefined }} />
    </form>
  );
}

const sameAddress = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/**
 * Suspend, unsuspend, plan changes, export and delete for one account. Each needs a second,
 * explicit click, and the outcome is shown in place; a deletion is reported above the list
 * (see `AccountList`), since the account then leaves it. Deleting also needs the account's
 * email address typed out. The changes are server actions, and the API refuses to export or
 * delete an administrator's account or the caller's own (its message is shown).
 */
export function UserActions({ user }: { user: { id: string; display_name: string; email: string; role: string; status: string; plan: string } }) {
  const announce = useContext(AccountResultContext);
  const [mode, setMode] = useState<UserMode>(null);
  const [typedEmail, setTypedEmail] = useState("");
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminUserAction(previous, form);
    if (next.ok) {
      if (form.get("intent") === "delete") {
        announce(next.ok);
        setMode(null);
        return {};
      }
      setMode(null);
    }
    return next;
  }, {} as AdminActionState);
  const suspended = user.status === "suspended";
  const otherPlan = user.plan === "premium" ? "free" : "premium";
  const who = user.display_name;
  const open = (next: UserMode) => {
    setTypedEmail("");
    setMode(next);
  };

  return (
    <div className="space-y-3">
      {mode === null ? (
        <div className="flex flex-wrap gap-2">
          {suspended ? (
            <Button type="button" variant="secondary" onClick={() => open("unsuspend")}>
              Unsuspend<span className="sr-only"> {who}</span>
            </Button>
          ) : user.role === "admin" ? null : (
            <Button type="button" variant="danger" onClick={() => open("suspend")}>
              Suspend<span className="sr-only"> {who}</span>
            </Button>
          )}
          <Button type="button" variant="secondary" onClick={() => open("plan")}>
            Set plan to {otherPlan}<span className="sr-only"> for {who}</span>
          </Button>
          <Button type="button" variant="secondary" onClick={() => open("export")}>
            Export data<span className="sr-only"> of {who}</span>
          </Button>
          <Button type="button" variant="danger" onClick={() => open("delete")}>
            Delete account<span className="sr-only"> of {who}</span>
          </Button>
        </div>
      ) : mode === "export" ? (
        <ExportForm user={user} onDone={() => setMode(null)} />
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
          {mode === "delete" ? (
            <>
              <p className="text-sm">
                Permanently delete the account of {who}, for a request from its owner or for an account that must not exist? Their bets, watchlist, alerts, notifications, sync connections and community data are deleted with it. This cannot be undone.
              </p>
              <Field id={`delete-reason-${user.id}`} name="reason" label="Reason" hint="Required, such as the reference of the owner's request. Saved in the audit log after the account is gone. Don't include the email address." maxLength={500} required />
              <Field
                id={`delete-confirm-${user.id}`}
                name="confirm_email"
                label="Type the account's email address to confirm"
                autoComplete="off"
                maxLength={320}
                value={typedEmail}
                onChange={(e) => setTypedEmail(e.target.value)}
                required
              />
            </>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant={mode === "suspend" || mode === "delete" ? "danger" : "primary"} disabled={pending || (mode === "delete" && !sameAddress(typedEmail, user.email))}>
              {pending
                ? "Saving"
                : mode === "suspend"
                  ? "Confirm suspension"
                  : mode === "unsuspend"
                    ? "Confirm unsuspend"
                    : mode === "delete"
                      ? "Delete account permanently"
                      : `Confirm plan: ${otherPlan}`}
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

type ReportDecision = "dismiss" | "hide_content" | "remove_content" | "suspend_author";

const DECISIONS: { value: ReportDecision; label: string; confirm: string; danger: boolean }[] = [
  { value: "dismiss", label: "Dismiss", confirm: "Confirm: dismiss report", danger: false },
  { value: "hide_content", label: "Hide content", confirm: "Confirm: hide content", danger: true },
  { value: "remove_content", label: "Remove content", confirm: "Confirm: remove content", danger: true },
  { value: "suspend_author", label: "Suspend author", confirm: "Confirm: suspend author", danger: true },
];

function decisionText(decision: ReportDecision, target: string, author: string): string {
  if (decision === "dismiss") return `Dismiss this report? The ${target} stays as it is. Other open reports on it stay open.`;
  if (decision === "suspend_author") return `Suspend ${author}? Their sessions stop working and they can\u2019t log in. Their data is kept. An administrator can\u2019t be suspended.`;
  const verb = decision === "hide_content" ? "Hide" : "Remove";
  return `${verb} this ${target}? It disappears from every public view, and its author sees \u201cRemoved by moderators.\u201d in its place. Every other open report on it is closed with the same decision. Editing by its author does not bring it back: only Restore does. Hiding and removing behave the same today.`;
}

const ReportResultContext = createContext<(message: string) => void>(() => {});

/**
 * Wraps the report queue. A resolved report leaves the open queue when the page is refreshed,
 * so the outcome of the last decision is shown here, above the list, where it stays.
 */
export function ReportQueue({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  return (
    <ReportResultContext.Provider value={setMessage}>
      <div aria-live="polite" className={message ? "border-b border-line p-4 sm:px-5" : undefined}>
        {message ? <Notice tone="accent" role="status">{message}</Notice> : null}
      </div>
      {children}
    </ReportResultContext.Provider>
  );
}

/**
 * Decides one report: pick a decision, write the required note, confirm. The decision is a
 * server action; the result is shown in the queue (see `ReportQueue`) and the queue is refreshed.
 */
export function ReportActions({ report }: { report: { id: string; targetType: string; authorHandle: string | null; targetExists: boolean } }) {
  const announce = useContext(ReportResultContext);
  const [mode, setMode] = useState<ReportDecision | null>(null);
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminReportAction(previous, form);
    if (next.ok) {
      setMode(null);
      announce(next.ok);
      return {};
    }
    return next;
  }, {} as AdminActionState);
  const decision = DECISIONS.find((entry) => entry.value === mode);
  const author = report.authorHandle ? `@${report.authorHandle}` : "the author";

  return (
    <div className="space-y-3">
      {decision ? (
        <form action={action} className="space-y-3 rounded-cell border border-line-strong p-3" aria-label={`Confirm decision on report ${report.id.slice(0, 8)}`}>
          <input type="hidden" name="report_id" value={report.id} />
          <input type="hidden" name="action" value={decision.value} />
          <p className="max-w-prose text-sm">{decisionText(decision.value, report.targetType, author)}</p>
          <Field id={`note-${report.id}`} name="note" label="Note" hint="Required. Saved in the audit log, not shown to the reporter or the author." maxLength={500} required />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant={decision.danger ? "danger" : "primary"} disabled={pending}>
              {pending ? "Saving" : decision.confirm}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMode(null)} disabled={pending}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          {DECISIONS.filter((entry) => report.targetExists || entry.value === "dismiss" || entry.value === "suspend_author").map((entry) => (
            <Button key={entry.value} type="button" variant={entry.value === "suspend_author" ? "danger" : "secondary"} onClick={() => setMode(entry.value)}>
              {entry.label}
              <span className="sr-only">, report {report.id.slice(0, 8)}</span>
            </Button>
          ))}
        </div>
      )}
      <Result state={state} />
    </div>
  );
}

/**
 * Makes hidden or removed content visible again (`POST /v1/admin/community/restore`), after a
 * required note and a second click. Every open report on the content is closed as restored.
 */
export function RestoreAction({ target, label }: { target: { type: string; id: string; status: string }; label: string }) {
  const announce = useContext(ReportResultContext);
  const [confirming, setConfirming] = useState(false);
  const [state, action, pending] = useActionState(async (previous: AdminActionState, form: FormData) => {
    const next = await adminRestoreAction(previous, form);
    if (next.ok) {
      setConfirming(false);
      announce(next.ok);
      return {};
    }
    return next;
  }, {} as AdminActionState);
  const noun = target.type === "profile" ? "profile" : target.type === "comment" ? "comment" : "pick";

  return (
    <div className="space-y-3">
      {confirming ? (
        <form action={action} className="space-y-3 rounded-cell border border-line-strong p-3" aria-label={`Confirm restoring the ${noun}, ${label}`}>
          <input type="hidden" name="target_type" value={target.type} />
          <input type="hidden" name="target_id" value={target.id} />
          <p className="max-w-prose text-sm">
            Restore this {noun}? It is {target.status} now. It becomes visible again to everyone who could see it before, and every open report on it is closed as restored.
          </p>
          <Field id={`restore-note-${label.replace(/\W+/g, "-")}`} name="note" label="Note" hint="Required. Saved on the reports it closes and in the audit log." maxLength={500} required />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={pending}>
              {pending ? "Saving" : `Confirm: restore ${noun}`}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setConfirming(false)} disabled={pending}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <Button type="button" variant="secondary" onClick={() => setConfirming(true)}>
          Restore {noun}
          <span className="sr-only">, {label}</span>
        </Button>
      )}
      <Result state={state} />
    </div>
  );
}
