import { AdminTabs } from "@/components/app/admin-controls";
import { PageHeader } from "@/components/app/page-header";
import { requireAdmin } from "@/lib/admin";
import { flagOn, getFlags } from "@/lib/flags";

/**
 * The admin section. Access is decided by the API from the account's role; everyone else gets
 * a 404 (from the proxy, and again from each page, because a layout is not re-rendered when
 * moving between its pages).
 */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requireAdmin();
  const community = flagOn(await getFlags(), "community");
  return (
    <>
      <PageHeader title="Admin" description={`Service status, accounts, feature flags, the audit log${community ? ", the email outbox and community moderation" : " and the email outbox"}. Every change made here is written to the audit log.`} />
      <AdminTabs community={community} />
      {children}
    </>
  );
}
