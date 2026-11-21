import type { Metadata } from "next";
import Link from "next/link";
import type { Schemas } from "@oddvex/types";
import { AccountList, UserActions } from "@/components/app/admin-controls";
import { Badge, Button, EmptyState, Field, Panel, PanelHeader, SelectField } from "@/components/ui/primitives";
import { adminGet, requireAdmin } from "@/lib/admin";
import { withQuery } from "@/lib/api";
import { formatDateTime, titleCase } from "@/lib/format";
import { pick } from "@/lib/leagues";

export const metadata: Metadata = { title: "Admin: users" };

const PAGE_SIZE = 20;

export default async function AdminUsersPage({ searchParams }: { searchParams: Promise<{ q?: string; status?: string; plan?: string; offset?: string }> }) {
  await requireAdmin();
  const params = await searchParams;
  const q = (params.q ?? "").trim().slice(0, 120);
  const status = pick(params.status, ["all", "active", "suspended"], "all");
  const plan = pick(params.plan, ["all", "free", "premium"], "all");
  const offset = Math.max(0, Math.floor(Number(params.offset) || 0));
  const list = await adminGet<Schemas["AdminUserListOut"]>("/v1/admin/users", {
    q: q || undefined,
    status: status === "all" ? undefined : status,
    plan: plan === "all" ? undefined : plan,
    limit: PAGE_SIZE,
    offset,
  });
  const href = (nextOffset: number) =>
    withQuery("/app/admin/users", { q, status: status === "all" ? undefined : status, plan: plan === "all" ? undefined : plan, offset: nextOffset || undefined });
  const first = list.total === 0 ? 0 : list.offset + 1;
  const last = list.offset + list.items.length;
  const filtered = Boolean(q) || status !== "all" || plan !== "all";

  return (
    <div className="space-y-5">
      <Panel aria-labelledby="admin-users-filter">
        <PanelHeader id="admin-users-filter" title="Find accounts" description="Search by name or email. Filters are kept in the address, so a view can be bookmarked." />
        <form action="/app/admin/users" method="get" className="flex flex-wrap items-end gap-3 p-4 sm:p-5">
          <Field id="admin-q" name="q" label="Name or email" defaultValue={q} maxLength={120} className="min-w-0 flex-1 basis-56" />
          <SelectField id="admin-status" name="status" label="Status" defaultValue={status} className="w-36">
            <option value="all">Any status</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </SelectField>
          <SelectField id="admin-plan" name="plan" label="Plan" defaultValue={plan} className="w-36">
            <option value="all">Any plan</option>
            <option value="free">Free</option>
            <option value="premium">Premium</option>
          </SelectField>
          <Button type="submit" variant="secondary">
            Apply
          </Button>
          {filtered ? (
            <Link href="/app/admin/users" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
              Clear
            </Link>
          ) : null}
        </form>
      </Panel>

      <Panel aria-labelledby="admin-users">
        <PanelHeader
          id="admin-users"
          title="Accounts"
          description={list.total === 0 ? "No accounts match" : `Showing ${first} to ${last} of ${list.total}, newest first`}
        />
        <AccountList>
        {list.items.length === 0 ? (
          <EmptyState title="No accounts match these filters">Try a shorter search, or clear the filters.</EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {list.items.map((user) => (
              <li key={user.id} className="space-y-3 px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                  <div className="min-w-0">
                    <h3 className="font-medium">{user.display_name}</h3>
                    <p className="break-all text-sm text-muted">{user.email}</p>
                  </div>
                  <p className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={user.status === "suspended" ? "error" : "neutral"}>{user.status === "suspended" ? "Suspended" : titleCase(user.status)}</Badge>
                    <Badge tone={user.plan === "premium" ? "second" : "neutral"}>Plan: {user.plan}</Badge>
                    {user.role === "admin" ? <Badge tone="second">Administrator</Badge> : null}
                    <Badge tone={user.email_verified ? "neutral" : "warn"}>{user.email_verified ? "Email verified" : "Email not verified"}</Badge>
                  </p>
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-muted">Bets tracked</dt>
                    <dd className="num">{user.bet_count}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Joined</dt>
                    <dd><time dateTime={user.created_at}>{formatDateTime(user.created_at)}</time></dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Last login</dt>
                    <dd>{user.last_login_at ? <time dateTime={user.last_login_at}>{formatDateTime(user.last_login_at)}</time> : "Never"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Internal ID</dt>
                    <dd>
                      <Link href={withQuery("/app/admin/audit", { user_id: user.id })} className="num underline underline-offset-4">
                        {user.id.slice(0, 8)}
                        <span className="sr-only">, audit entries for {user.display_name}</span>
                      </Link>
                    </dd>
                  </div>
                </dl>
                <UserActions user={{ id: user.id, display_name: user.display_name, email: user.email, role: user.role, status: user.status, plan: user.plan }} />
              </li>
            ))}
          </ul>
        )}
        </AccountList>
        {list.total > PAGE_SIZE ? (
          <nav aria-label="Pages of accounts" className="flex items-center justify-between gap-3 border-t border-line px-4 py-2 sm:px-5">
            {offset > 0 ? (
              <Link href={href(Math.max(0, offset - PAGE_SIZE))} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Previous
              </Link>
            ) : (
              <span />
            )}
            {last < list.total ? (
              <Link href={href(offset + PAGE_SIZE)} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
                Next
              </Link>
            ) : null}
          </nav>
        ) : null}
      </Panel>
    </div>
  );
}
