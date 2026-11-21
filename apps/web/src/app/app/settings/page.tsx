import type { Metadata } from "next";
import Link from "next/link";
import { ChangePasswordForm, ExportDataButton } from "@/components/app/account-forms";
import { ResendVerification } from "@/components/app/auth-forms";
import { DeleteAccountForm } from "@/components/app/delete-account";
import { NotificationPreferences, StakeReminderForm } from "@/components/app/notification-settings";
import { api } from "@/lib/api";
import type { Schemas } from "@oddvex/types";
import { OddsFormatToggle } from "@/components/app/odds-format";
import { PageHeader } from "@/components/app/page-header";
import { HelplineLink } from "@/components/ui/helpline";
import { Badge, Button, ButtonLink, Panel, PanelHeader } from "@/components/ui/primitives";
import { titleCase } from "@/lib/format";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { logoutEverywhereAction } from "@/lib/auth-actions";
import { flagOn, getFlags } from "@/lib/flags";
import { currentUser } from "@/lib/session";
import { HELPLINE } from "@/lib/site";

export const metadata: Metadata = { title: "Settings" };

export default async function SettingsPage() {
  const user = await currentUser();
  const [prefs, reminder, entitlements] = user
    ? await Promise.all([
        api<Schemas["NotificationPreferencesOut"]>("/v1/me/notification-preferences", { auth: true }).catch(() => null),
        api<Schemas["StakeReminderOut"]>("/v1/me/stake-reminder", { auth: true }).catch(() => null),
        api<Schemas["EntitlementsOut"]>("/v1/me/entitlements", { auth: true }).catch(() => null),
      ])
    : [null, null, null];
  const community = flagOn(await getFlags(), "community");
  const plan = entitlements?.plan ?? user?.plan ?? null;
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

        <Panel aria-labelledby="settings-account">
          <PanelHeader id="settings-account" title="Account" />
          <div className="p-4 sm:p-5">
            {user ? (
              <div className="space-y-4">
                <dl className="grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
                  <dt className="text-muted">Name</dt>
                  <dd>{user.display_name}</dd>
                  <dt className="text-muted">Email</dt>
                  <dd className="min-w-0">
                    <span className="break-all">{user.email}</span>
                    <span className="mt-1 block">
                      {user.email_verified ? <Badge tone="accent">Email verified</Badge> : <Badge tone="warn">Email not verified</Badge>}
                    </span>
                  </dd>
                  <dt className="text-muted">Plan</dt>
                  <dd>
                    <span>{plan ? titleCase(plan) : "Not available right now"}</span>
                    {entitlements?.preview ? <span className="mt-1 block text-muted">Preview: every feature is included</span> : null}
                  </dd>
                </dl>
                {user.email_verified ? null : (
                  <div className="space-y-2 border-t border-line pt-4">
                    <p className="text-sm text-muted">Confirming shows the address is yours. Nothing in OddVex is locked until you do.</p>
                    <ResendVerification />
                  </div>
                )}
              </div>
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
            <NotificationPreferences initial={prefs.in_app} community={community} />
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
            If betting stops being fun, the {HELPLINE.name} is confidential and answers 24 hours a day, every day. Call{" "}
            <HelplineLink className="text-ink underline" /> or text{" "}
            <a href={HELPLINE.sms} className="text-ink underline">{HELPLINE.textTo}</a> ({HELPLINE.textDigits}), or read our{" "}
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
            <Panel aria-labelledby="settings-sessions">
              <PanelHeader id="settings-sessions" title="Sessions" description="Ends every session of this account, on this device and any other. You then log in again." />
              <form action={logoutEverywhereAction} className="space-y-3 p-4 sm:p-5">
                <Button type="submit" variant="secondary">
                  Log out of all devices
                </Button>
                <p className="text-sm text-muted">OddVex does not keep separate sessions per device yet, so the Log out button at the top of the page does the same.</p>
              </form>
            </Panel>
            <Panel>
              <PanelHeader title="Your data" description="A JSON file with your account details, bets, watchlist, alerts, notifications, staking reminder, sync history, community data and your own security log entries. It never contains your password." />
              <div className="p-4 sm:p-5">
                <ExportDataButton />
              </div>
            </Panel>
          </>
        ) : null}

        {user ? (
          <Panel>
            <PanelHeader
              title="Delete account"
              description={`Removes your account, every bet you logged${community ? ", any sync connections and everything you posted in the community, graded picks included" : " and any sync connections"}. This can't be undone.`}
            />
            <div className="p-4 sm:p-5">
              <DeleteAccountForm />
            </div>
          </Panel>
        ) : null}
      </div>
    </>
  );
}
