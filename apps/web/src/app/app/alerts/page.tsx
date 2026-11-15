import type { Metadata } from "next";
import type { Schemas } from "@oddvex/types";
import { AlertRuleList, NotificationList } from "@/components/app/alerts-panels";
import { PageHeader } from "@/components/app/page-header";
import { ButtonLink, EmptyState, Panel, PanelHeader } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Alerts" };

const ORDER = { active: 0, triggered: 1, paused: 2, expired: 3 } as const;

export default async function AlertsPage() {
  const user = await currentUser();
  if (!user) {
    return (
      <>
        <PageHeader title="Alerts" description="Get told when a price reaches your number, a line moves, a game is about to start or a final score is in." />
        <Panel>
          <EmptyState
            title="Log in to set alerts"
            action={
              <div className="flex gap-3">
                <ButtonLink href="/signup?next=/app/alerts">Create an account</ButtonLink>
                <ButtonLink href="/login?next=/app/alerts" variant="secondary">
                  Log in
                </ButtonLink>
              </div>
            }
          >
            Alerts appear inside OddVex. They are not sent by push or email.
          </EmptyState>
        </Panel>
      </>
    );
  }

  const [notifications, alerts] = await Promise.all([
    api<Schemas["NotificationListOut"]>("/v1/notifications", { auth: true, query: { limit: 50 } }),
    api<Schemas["AlertListOut"]>("/v1/alerts", { auth: true }),
  ]);
  const rules = [...alerts.items].sort((a, b) => ORDER[a.state] - ORDER[b.state] || b.created_at.localeCompare(a.created_at));

  return (
    <>
      <PageHeader title="Alerts" description="Alerts report what changed. They are information, not a suggestion to bet." />
      <div className="space-y-5">
        <Panel aria-labelledby="notifications-heading">
          <PanelHeader
            id="notifications-heading"
            title="Notifications"
            description={notifications.unread_count ? `${notifications.unread_count} unread` : "All read"}
          />
          <NotificationList items={notifications.items} unread={notifications.unread_count} />
        </Panel>
        <Panel aria-labelledby="rules-heading">
          <PanelHeader id="rules-heading" title="Your alerts" description={`${rules.filter((rule) => rule.state === "active").length} active`} />
          <AlertRuleList rules={rules} />
        </Panel>
      </div>
    </>
  );
}
