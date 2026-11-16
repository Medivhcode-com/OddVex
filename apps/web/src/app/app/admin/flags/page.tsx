import type { Metadata } from "next";
import type { Schemas } from "@oddvex/types";
import { FlagToggle } from "@/components/app/admin-controls";
import { Badge, EmptyState, Notice, Panel, PanelHeader } from "@/components/ui/primitives";
import { adminGet, flagWarning, requireAdmin } from "@/lib/admin";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = { title: "Admin: flags" };

export default async function AdminFlagsPage() {
  await requireAdmin();
  const { items } = await adminGet<Schemas["AdminFlagListOut"]>("/v1/admin/flags");
  return (
    <div className="space-y-5">
      <Notice tone="second" title="Flags apply to everyone">
        A flag is a global switch, not a per-account setting. A feature whose flag is off disappears from the navigation and its pages answer as not found.
      </Notice>
      <Panel aria-labelledby="admin-flags">
        <PanelHeader id="admin-flags" title="Feature flags" description="Defaults live in the API's code. A change here overrides the default and is written to the audit log." />
        {items.length === 0 ? (
          <EmptyState title="No feature flags are defined" />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((flag) => {
              const warning = flagWarning(flag.key);
              return (
                <li key={flag.key} className="space-y-3 px-4 py-4 sm:px-5">
                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                    <h3 className="num font-medium">{flag.key}</h3>
                    <p className="flex flex-wrap items-center gap-1.5">
                      <Badge tone={flag.enabled ? "accent" : "neutral"}>{flag.enabled ? "On" : "Off"}</Badge>
                      <Badge>{flag.overridden ? `Overridden, default ${flag.default ? "on" : "off"}` : "Default"}</Badge>
                    </p>
                  </div>
                  <p className="max-w-prose text-sm text-muted">{flag.description}</p>
                  {warning ? <p className="max-w-prose text-sm text-warn">Needs review before it is turned on. {warning}</p> : null}
                  {flag.updated_at ? (
                    <p className="text-xs text-muted">
                      Last changed <time dateTime={flag.updated_at}>{formatDateTime(flag.updated_at)}</time>
                    </p>
                  ) : null}
                  <FlagToggle flag={{ key: flag.key, enabled: flag.enabled }} warning={warning} />
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
