import type { Metadata } from "next";
import Link from "next/link";
import { ChangePasswordForm, ExportDataButton } from "@/components/app/account-forms";
import { DeleteAccountForm } from "@/components/app/delete-account";
import { NotificationPreferences, StakeReminderForm } from "@/components/app/notification-settings";
import { api } from "@/lib/api";
import type { Schemas } from "@oddvex/types";
import { OddsFormatToggle } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { ButtonLink, Panel, PanelHeader } from "@/components/ui/primitives";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Settings" };

export default async function SettingsPage() {
  const user = await currentUser();
  const [prefs, reminder] = user
    ? await Promise.all([
        api<Schemas["NotificationPreferencesOut"]>("/v1/me/notification-preferences", { auth: true }).catch(() => null),
        api<Schemas["StakeReminderOut"]>("/v1/me/stake-reminder", { auth: true }).catch(() => null),
      ])
    : [null, null];
  return (
    <>
      <PageHeader title="Settings" />
      <div className="max-w-2xl space-y-5">
        <Panel>
          <PanelHeader title="Display" description="Saved in this browser." />
          <div className="space-y-4 p-4 sm:p-5">
            <div className="flex items-center justify-between gap-4">
              <span>Odds format</span>
              <OddsFormatToggle />
            </div>
            <div className="flex items-center justify-between gap-4">
              <span>Theme</span>
              <ThemeToggle />
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Account" />
          <div className="p-4 sm:p-5">
            {user ? (
              <dl className="grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
                <dt className="text-muted">Name</dt>
                <dd>{user.display_name}</dd>
                <dt className="text-muted">Email</dt>
                <dd className="break-all">{user.email}</dd>
              </dl>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-muted">You are not logged in.</p>
                <ButtonLink href="/login?next=/app/settings" variant="secondary" size="sm">
                  Log in
                </ButtonLink>
              </div>
            )}
          </div>
        </Panel>

        {prefs ? (
          <Panel aria-labelledby="settings-notifications">
            <PanelHeader id="settings-notifications" title="Notifications" description="Choose what OddVex tells you about." />
            <NotificationPreferences initial={prefs.in_app} />
          </Panel>
        ) : null}

        {reminder ? (
          <Panel aria-labelledby="settings-stake">
            <PanelHeader id="settings-stake" title="Weekly staking reminder" />
            <StakeReminderForm reminder={reminder} />
          </Panel>
        ) : null}

        <Panel>
          <PanelHeader title="Play within your limits" />
          <p className="p-4 text-sm leading-relaxed text-muted sm:p-5">
            If betting stops being fun, free and confidential help is available 24/7. Call or text{" "}
            <a href="tel:18004262537" className="text-ink underline">1-800-GAMBLER</a>, or read our{" "}
            <Link href="/responsible-gambling" className="text-ink underline">responsible gambling page</Link>.
          </p>
        </Panel>

        {user ? (
          <>
            <Panel>
              <PanelHeader title="Password" description="Changing it signs out every other device." />
              <div className="p-4 sm:p-5">
                <ChangePasswordForm />
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Your data" description="A JSON file with your account details, bets, watchlist, sync history and security log." />
              <div className="p-4 sm:p-5">
                <ExportDataButton />
              </div>
            </Panel>
          </>
        ) : null}

        {user ? (
          <Panel>
            <PanelHeader title="Delete account" description="Removes your account, every bet you logged and any sync connections. This can't be undone." />
            <div className="p-4 sm:p-5">
              <DeleteAccountForm />
            </div>
          </Panel>
        ) : null}
      </div>
    </>
  );
}
