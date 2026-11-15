import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { PageHeader } from "@/components/app/page-header";
import { Badge, EmptyState, Panel, PanelHeader, Stat } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatAge, titleCase } from "@/lib/format";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Admin" };

/**
 * Read-only operations overview for staff. Access is decided by the API from the account's role;
 * everyone else gets a 404 so the page's existence is not advertised.
 */
export default async function AdminPage() {
  const user = await currentUser();
  if (!user || user.role !== "admin") notFound();
  let overview: Schemas["AdminOverviewOut"];
  try {
    overview = await api<Schemas["AdminOverviewOut"]>("/v1/admin/overview", { auth: true });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) notFound();
    throw error;
  }
  const health = overview.provider_health;
  const healthy = health.status === "ok";

  return (
    <>
      <PageHeader title="Admin" description="A read-only view of the service. Every sensitive action by any account is written to the audit log below." />
      <div className="space-y-5">
        <Panel aria-labelledby="admin-service">
          <PanelHeader id="admin-service" title="Service" description={`Version ${overview.version}, ${overview.environment} environment`} />
          <dl className="grid grid-cols-2 gap-4 p-4 sm:p-5 md:grid-cols-4">
            <Stat label="Accounts" value={overview.user_count} />
            <Stat label="Bets tracked" value={overview.bet_count} />
            <Stat label="Sync connections" value={overview.sync_connection_count} />
            <div>
              <dt className="text-sm text-muted">Data provider</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2">
                <span className="font-medium">{titleCase(health.provider)}</span>
                <Badge tone={healthy ? "accent" : "warn"}>{healthy ? "Responding" : titleCase(health.status)}</Badge>
              </dd>
              <dd className="mt-1 text-xs text-muted">
                {titleCase(health.data_mode)} data, checked {formatAge(health.checked_at)}. {health.detail}
              </dd>
            </div>
          </dl>
        </Panel>

        <Panel aria-labelledby="admin-audit">
          <PanelHeader id="admin-audit" title="Recent audit log" description="Newest first. Account identifiers are internal IDs, not emails." />
          {overview.recent_audit.length === 0 ? (
            <EmptyState title="No audited actions yet">Sign-ins, bet settlements, deletions and exports appear here.</EmptyState>
          ) : (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
              <table className="w-full min-w-[40rem] border-collapse text-sm">
                <caption className="sr-only">Recent audit log entries</caption>
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">When</th>
                    <th scope="col" className="px-2 py-2.5 font-medium">Action</th>
                    <th scope="col" className="px-2 py-2.5 font-medium">Subject</th>
                    <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Account</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.recent_audit.map((entry) => (
                    <tr key={entry.id} className="border-t border-line">
                      <td className="whitespace-nowrap px-4 py-2.5 text-muted sm:px-5">
                        <time dateTime={entry.created_at}>{formatAge(entry.created_at)}</time>
                      </td>
                      <td className="num px-2 py-2.5">{entry.action}</td>
                      <td className="px-2 py-2.5 text-muted">
                        {entry.entity_type ?? "none"}
                        {entry.entity_id ? <span className="num"> {entry.entity_id.slice(0, 8)}</span> : null}
                      </td>
                      <td className="num px-4 py-2.5 text-muted sm:px-5">{entry.user_id ? entry.user_id.slice(0, 8) : "none"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
