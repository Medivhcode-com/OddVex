import type { Metadata } from "next";
import Link from "next/link";
import type { Schemas } from "@oddvex/types";
import { Button, EmptyState, Field, Panel, PanelHeader } from "@/components/ui/primitives";
import { adminGet, requireAdmin } from "@/lib/admin";
import { withQuery } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = { title: "Admin: audit log" };

const PAGE_SIZE = 50;
/** Never shown, whatever an entry's details hold. Emails belong to the Users and Outbox tabs only. */
const HIDDEN_KEY = /pass|token|hash|secret|email|authorization|cookie/i;

function plain(value: unknown): string | null {
  if (typeof value === "string") return value.includes("@") ? null : value.slice(0, 200);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

/** The reason and the before/after values of a change, as short text. Anything else in `details` is left out. */
function describeDetails(details: Record<string, unknown> | null | undefined): string[] {
  if (!details) return [];
  const out: string[] = [];
  const before = details.before && typeof details.before === "object" ? (details.before as Record<string, unknown>) : {};
  const after = details.after && typeof details.after === "object" ? (details.after as Record<string, unknown>) : {};
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (HIDDEN_KEY.test(key)) continue;
    const from = plain(before[key]);
    const to = plain(after[key]);
    if (from !== null || to !== null) out.push(`${key}: ${from ?? "none"} to ${to ?? "none"}`);
  }
  const reason = plain(details.reason);
  if (reason) out.push(`Reason: ${reason}`);
  return out;
}

export default async function AdminAuditPage({ searchParams }: { searchParams: Promise<{ action?: string; user_id?: string; before?: string }> }) {
  await requireAdmin();
  const params = await searchParams;
  const action = (params.action ?? "").trim().slice(0, 64);
  const userId = (params.user_id ?? "").trim().slice(0, 64);
  const before = (params.before ?? "").trim().slice(0, 80);
  const page = await adminGet<Schemas["AdminAuditPageOut"]>("/v1/admin/audit", {
    action: action || undefined,
    user_id: userId || undefined,
    before: before || undefined,
    limit: PAGE_SIZE,
  });
  const filtered = Boolean(action || userId);

  return (
    <div className="space-y-5">
      <Panel aria-labelledby="admin-audit-filter">
        <PanelHeader id="admin-audit-filter" title="Filter the log" description="Both filters match exactly. The account filter finds entries an account caused and entries about it." />
        <form action="/app/admin/audit" method="get" className="flex flex-wrap items-end gap-3 p-4 sm:p-5">
          <Field id="audit-action" name="action" label="Action" defaultValue={action} maxLength={64} hint="For example admin.user_suspended" className="min-w-0 flex-1 basis-56" />
          <Field id="audit-user" name="user_id" label="Account ID" defaultValue={userId} maxLength={64} hint="The internal ID from the Users tab" className="min-w-0 flex-1 basis-56" />
          <div className="flex items-center gap-3 self-start pt-[1.875rem]">
            <Button type="submit" variant="secondary">
              Apply
            </Button>
            {filtered ? (
              <Link href="/app/admin/audit" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Clear
              </Link>
            ) : null}
          </div>
        </form>
      </Panel>

      <Panel aria-labelledby="admin-audit-log">
        <PanelHeader
          id="admin-audit-log"
          title="Audit log"
          description={`${before ? "Older entries" : "Newest first"}. Accounts are shown as internal IDs, not emails.`}
          action={
            before ? (
              <Link href={withQuery("/app/admin/audit", { action, user_id: userId })} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Back to newest
              </Link>
            ) : undefined
          }
        />
        {page.items.length === 0 ? (
          <EmptyState title={filtered ? "No entries match these filters" : "No audited actions yet"}>
            {filtered ? "Action names and account IDs must match exactly." : "Sign-ins, admin changes, bet settlements, deletions and exports appear here."}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
            <table className="w-full min-w-[46rem] border-collapse text-sm">
              <caption className="sr-only">Audit log entries</caption>
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">When</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">Action</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">Subject</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">By account</th>
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Details</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((entry) => {
                  const details = describeDetails(entry.details);
                  return (
                    <tr key={entry.id} className="border-t border-line align-top">
                      <td className="whitespace-nowrap px-4 py-2.5 text-muted sm:px-5">
                        <time dateTime={entry.created_at}>{formatDateTime(entry.created_at)}</time>
                      </td>
                      <td className="num px-2 py-2.5">{entry.action}</td>
                      <td className="px-2 py-2.5 text-muted">
                        {entry.entity_type ?? "none"}
                        {entry.entity_id ? <span className="num"> {entry.entity_id.slice(0, 20)}</span> : null}
                      </td>
                      <td className="num px-2 py-2.5 text-muted">{entry.user_id ? entry.user_id.slice(0, 8) : "none"}</td>
                      <td className="px-4 py-2.5 text-muted sm:px-5">
                        {details.length ? (
                          <ul className="space-y-0.5">
                            {details.map((line) => (
                              <li key={line}>{line}</li>
                            ))}
                          </ul>
                        ) : (
                          <span aria-hidden="true">&ndash;</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {page.next_before ? (
          <div className="border-t border-line px-4 py-2 sm:px-5">
            <Link href={withQuery("/app/admin/audit", { action, user_id: userId, before: page.next_before })} className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">
              Load older
            </Link>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
