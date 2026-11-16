import type { Metadata } from "next";
import type { Schemas } from "@oddvex/types";
import { EmptyState, Notice, Panel, PanelHeader } from "@/components/ui/primitives";
import { adminGet, requireAdmin } from "@/lib/admin";
import { formatDateTime, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Admin: email outbox" };

export default async function AdminOutboxPage() {
  await requireAdmin();
  const outbox = await adminGet<Schemas["AdminOutboxListOut"]>("/v1/admin/email-outbox", { limit: 100 });
  return (
    <div className="space-y-5">
      <Notice tone="warn" title="Nothing is actually sent">
        No email provider is connected. Each message below was written to the outbox table and went nowhere (delivery mode:{" "}
        <span className="num">{outbox.delivery}</span>). Message bodies and their one-time links are not shown here.
      </Notice>
      <Panel aria-labelledby="admin-outbox">
        <PanelHeader id="admin-outbox" title="Email outbox" description={`The latest ${outbox.items.length} queued ${outbox.items.length === 1 ? "message" : "messages"}, newest first`} />
        {outbox.items.length === 0 ? (
          <EmptyState title="The outbox is empty">Confirmation and password reset messages appear here when they are queued.</EmptyState>
        ) : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
            <table className="w-full min-w-[44rem] border-collapse text-sm">
              <caption className="sr-only">Queued emails. None was sent.</caption>
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Queued</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">To</th>
                  <th scope="col" className="px-2 py-2.5 font-medium">Template</th>
                  <th scope="col" className="px-4 py-2.5 font-medium sm:px-5">Subject</th>
                </tr>
              </thead>
              <tbody>
                {outbox.items.map((email) => (
                  <tr key={email.id} className="border-t border-line">
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted sm:px-5">
                      <time dateTime={email.created_at}>{formatDateTime(email.created_at)}</time>
                    </td>
                    <td className="break-all px-2 py-2.5">{email.to}</td>
                    <td className="px-2 py-2.5 text-muted">{titleCase(email.template)}</td>
                    <td className="px-4 py-2.5 text-muted sm:px-5">{email.subject}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
