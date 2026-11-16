import type { Metadata } from "next";
import Link from "next/link";
import type { Schemas } from "@oddvex/types";
import { ReportActions, ReportQueue } from "@/components/app/admin-controls";
import { Badge, EmptyState, Panel, PanelHeader, Segmented, Stat } from "@/components/ui/primitives";
import { adminGet, requireAdmin } from "@/lib/admin";
import { withQuery } from "@/lib/api";
import { reasonLabel } from "@/lib/community-copy";
import { requireFlag } from "@/lib/flags";
import { formatDateTime, titleCase } from "@/lib/format";
import { pick } from "@/lib/leagues";

export const metadata: Metadata = { title: "Admin: community" };

const PAGE_SIZE = 20;
const TARGET: Record<string, string> = { pick: "Pick", comment: "Comment", profile: "Profile" };
const ACTION: Record<string, string> = { dismiss: "Dismissed", hide_content: "Content hidden", remove_content: "Content removed", suspend_author: "Author suspended" };

function Party({ label, party }: { label: string; party: Schemas["AdminReportPartyOut"] }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="break-words">
        {party.handle ? `@${party.handle}` : "No profile"}
        {party.status !== "active" ? <span className="text-muted">, account {party.status}</span> : null}{" "}
        <Link href={withQuery("/app/admin/audit", { user_id: party.user_id })} className="num text-muted underline underline-offset-4">
          {party.user_id.slice(0, 8)}
          <span className="sr-only">, audit entries for this account</span>
        </Link>
      </dd>
    </div>
  );
}

/** Community moderation: counts and the report queue. Exists only while the `community` flag is on. */
export default async function AdminCommunityPage({ searchParams }: { searchParams: Promise<{ status?: string; offset?: string }> }) {
  await requireAdmin();
  await requireFlag("community");
  const params = await searchParams;
  const status = pick(params.status, ["open", "resolved"], "open");
  const offset = Math.max(0, Math.floor(Number(params.offset) || 0));
  const [overview, list] = await Promise.all([
    adminGet<Schemas["AdminCommunityOverviewOut"]>("/v1/admin/community/overview"),
    adminGet<Schemas["AdminReportListOut"]>("/v1/admin/community/reports", { status, limit: PAGE_SIZE, offset }),
  ]);
  const href = (next: { status?: string; offset?: number }) => withQuery("/app/admin/community", { status: (next.status ?? status) === "open" ? undefined : (next.status ?? status), offset: next.offset || undefined });
  const first = list.total === 0 ? 0 : list.offset + 1;
  const last = list.offset + list.items.length;

  return (
    <div className="space-y-5">
      <Panel aria-labelledby="admin-community-overview">
        <PanelHeader id="admin-community-overview" title="Community overview" description="Counts across the whole community." />
        <dl className="grid grid-cols-2 gap-4 p-4 sm:p-5 md:grid-cols-4">
          <Stat label="Open reports" value={overview.open_reports} />
          <Stat label="Profiles" value={overview.profiles} hint={`${overview.public_profiles} public`} />
          <Stat label="Picks" value={overview.picks} hint={`${overview.graded_picks} graded`} />
          <Stat label="Comments" value={overview.comments} />
          <Stat label="Hidden or removed items" value={overview.hidden_or_removed_items} />
        </dl>
      </Panel>

      <Segmented
        label="Report status"
        current={status}
        options={[
          { value: "open", label: "Open", href: href({ status: "open", offset: 0 }) },
          { value: "resolved", label: "Resolved", href: href({ status: "resolved", offset: 0 }) },
        ]}
      />

      <Panel aria-labelledby="admin-community-reports">
        <PanelHeader
          id="admin-community-reports"
          title="Report queue"
          description={list.total === 0 ? `No ${status} reports` : `Showing ${first} to ${last} of ${list.total} ${status} reports. Reported text is shown as plain text, exactly as stored.`}
        />
        <ReportQueue>
        {list.items.length === 0 ? (
          <EmptyState title={status === "open" ? "No open reports" : "No resolved reports"}>{status === "open" ? "New reports from members appear here." : "Decisions appear here once a report is resolved."}</EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {list.items.map((report) => (
              <li key={report.id} className="space-y-3 px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                  <h3 className="font-medium">
                    {TARGET[report.target_type] ?? titleCase(report.target_type)} reported for {reasonLabel(report.reason).toLowerCase()}
                  </h3>
                  <p className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={report.status === "open" ? "warn" : "neutral"}>{report.status === "open" ? "Open" : "Resolved"}</Badge>
                    <Badge>Target: {TARGET[report.target_type] ?? report.target_type}</Badge>
                    {report.target_exists ? null : <Badge>Target deleted</Badge>}
                    {report.target_moderation_status && report.target_moderation_status !== "visible" ? <Badge tone="second">Now {report.target_moderation_status}</Badge> : null}
                  </p>
                </div>
                {report.target_summary ? <p className="break-words text-sm text-muted">{report.target_summary}</p> : null}
                <div>
                  <p className="text-xs text-muted">Reported content</p>
                  {report.target_text ? (
                    <blockquote className="mt-1 max-w-prose whitespace-pre-line break-words rounded-cell border border-line bg-bg px-3 py-2 text-sm">
                      {report.target_text}
                    </blockquote>
                  ) : (
                    <p className="mt-1 text-sm text-muted">{report.target_exists ? "This item has no text." : "The item no longer exists."}</p>
                  )}
                </div>
                <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2 md:grid-cols-4">
                  <div>
                    <dt className="text-xs text-muted">Reason</dt>
                    <dd>{reasonLabel(report.reason)}</dd>
                  </div>
                  <Party label="Reporter" party={report.reporter} />
                  <Party label="Author" party={report.author} />
                  <div>
                    <dt className="text-xs text-muted">Reported</dt>
                    <dd>
                      <time dateTime={report.created_at}>{formatDateTime(report.created_at)}</time>
                    </dd>
                  </div>
                </dl>
                {report.details ? (
                  <div>
                    <p className="text-xs text-muted">Reporter&rsquo;s details</p>
                    <p className="mt-1 max-w-prose whitespace-pre-line break-words text-sm">{report.details}</p>
                  </div>
                ) : null}
                {report.status === "resolved" ? (
                  <p className="max-w-prose break-words text-sm">
                    <span className="font-medium">{ACTION[report.resolution_action ?? ""] ?? "Resolved"}</span>
                    {report.resolved_at ? (
                      <>
                        {" "}
                        on <time dateTime={report.resolved_at}>{formatDateTime(report.resolved_at)}</time>
                      </>
                    ) : null}
                    . Note: {report.resolution_note ?? "none"}
                  </p>
                ) : (
                  <ReportActions report={{ id: report.id, targetType: report.target_type, authorHandle: report.author.handle ?? null, targetExists: report.target_exists }} />
                )}
              </li>
            ))}
          </ul>
        )}
        </ReportQueue>
        {list.total > PAGE_SIZE ? (
          <nav aria-label="Pages of reports" className="flex items-center justify-between gap-3 border-t border-line px-4 py-2 sm:px-5">
            {offset > 0 ? (
              <Link href={href({ offset: Math.max(0, offset - PAGE_SIZE) })} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Previous
              </Link>
            ) : (
              <span />
            )}
            {last < list.total ? (
              <Link href={href({ offset: offset + PAGE_SIZE })} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Next
              </Link>
            ) : null}
          </nav>
        ) : null}
      </Panel>
    </div>
  );
}
