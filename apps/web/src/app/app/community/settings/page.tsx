import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { UnblockButton } from "@/components/app/community/actions";
import { CommunityHeader, SignedOut } from "@/components/app/community/chrome";
import { ProfileForm } from "@/components/app/community/profile-form";
import { EmptyState, Notice, Panel, PanelHeader } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { COMMUNITY_HOME, communityContext, profileHref } from "@/lib/community";
import { formatDay } from "@/lib/format";

export const metadata: Metadata = { title: "Community settings" };

export default async function CommunitySettingsPage() {
  const context = await communityContext();
  if (!context.user) return <SignedOut next="/app/community/settings" />;
  if (!context.me) redirect(COMMUNITY_HOME);
  const me = context.me;
  const blocks = await api<Schemas["BlockListOut"]>("/v1/community/blocks", { auth: true });

  return (
    <>
      <CommunityHeader title="Community settings" description="Your profile, the profiles you blocked and what happens to your community data." current="settings" me={me} leaderboard={context.leaderboard} />
      <div className="max-w-3xl space-y-5">
        {me.moderation_status !== "visible" ? (
          <Notice tone="warn" title={me.moderation_note ?? "Removed by moderators."}>
            Other people can&rsquo;t see your profile and you can&rsquo;t post. If you change the handle or the bio, the profile stays hidden and goes back to a moderator for review. Only a moderator can make it visible again.
          </Notice>
        ) : null}
        <Panel aria-labelledby="settings-profile">
          <PanelHeader id="settings-profile" title="Profile" description="Changing the handle changes the address of your profile page." />
          <ProfileForm mode="edit" initial={{ handle: me.handle, bio: me.bio ?? null, is_public: me.is_public }} />
        </Panel>

        <Panel aria-labelledby="settings-blocked">
          <PanelHeader id="settings-blocked" title="Blocked profiles" description="You and a blocked profile can't see each other's profile, picks or comments. They are not told." />
          {blocks.items.length === 0 ? (
            <EmptyState title="You haven't blocked anyone">Block a profile from its profile page.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {blocks.items.map((entry) => (
                <li key={entry.handle} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 sm:px-5">
                  <p className="min-w-0">
                    <Link href={profileHref(entry.handle)} className="font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                      @{entry.handle}
                    </Link>
                    <span className="block text-sm text-muted">
                      Blocked <time dateTime={entry.since}>{formatDay(entry.since)}</time>
                    </span>
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <UnblockButton handle={entry.handle} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel aria-labelledby="settings-data">
          <PanelHeader id="settings-data" title="Leaving the community" />
          <div className="space-y-3 p-4 text-sm leading-relaxed text-muted sm:p-5">
            <p className="max-w-prose">
              To step back without deleting anything, make your profile private above. Nobody can then find your profile or your picks, and you can make it public again later.
            </p>
            <p className="max-w-prose">
              Deleting your OddVex account removes your community profile, your follows in both directions, your likes, your blocks, the reports you made, your comments and
              every pick you posted, graded ones included. Comments and likes other people left on your picks are removed with them. No public record is left behind. This
              can&rsquo;t be undone.
            </p>
            <p className="max-w-prose">
              There is no way to delete only the community profile yet. Account deletion and a copy of your data are in{" "}
              <Link href="/app/settings" className="text-ink underline">
                account settings
              </Link>
              .
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
