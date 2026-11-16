import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { BlockButton, FollowButton, ReportButton } from "@/components/app/community/actions";
import { CommunityHeader, RecordPanel, SignedOut } from "@/components/app/community/chrome";
import { PickList } from "@/components/app/community/pick-card";
import { Badge, ButtonLink, EmptyState, Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api, apiOrNull } from "@/lib/api";
import { COMMUNITY_HOME, communityContext, PAGE_SIZE, profileHref } from "@/lib/community";
import { countLabel, formatJoined, VERIFIED_NOTE, type Profile } from "@/lib/community-copy";
import { formatDay } from "@/lib/format";
import { pick } from "@/lib/leagues";

type Props = { params: Promise<{ handle: string }>; searchParams: Promise<{ tab?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const handle = (await params).handle;
  return { title: /^[A-Za-z0-9_]{3,20}$/.test(handle) ? `@${handle.toLowerCase()}` : "Profile" };
}

const TABS = ["picks", "followers", "following"] as const;

function FollowList({ list, kind }: { list: Schemas["FollowListOut"]; kind: "followers" | "following" }) {
  if (list.items.length === 0) {
    return (
      <EmptyState title={kind === "followers" ? "No followers yet" : "You don't follow anyone yet"}>
        {kind === "followers" ? "People who follow you appear here." : "Open the Everyone feed to find profiles to follow."}
      </EmptyState>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {list.items.map((entry) => (
        <li key={entry.handle} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 sm:px-5">
          <div className="min-w-0">
            <Link href={profileHref(entry.handle)} className="inline-flex min-h-11 items-center font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink">
              @{entry.handle}
            </Link>
            {entry.bio ? <p className="max-w-prose whitespace-pre-line break-words text-sm text-muted">{entry.bio}</p> : null}
          </div>
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {kind === "followers" && entry.is_following ? <Badge>You follow them</Badge> : null}
            <span>
              Since <time dateTime={entry.since}>{formatDay(entry.since)}</time>
            </span>
          </p>
        </li>
      ))}
    </ul>
  );
}

export default async function ProfilePage({ params, searchParams }: Props) {
  const handle = (await params).handle.toLowerCase();
  const context = await communityContext();
  if (!/^[a-z0-9_]{3,20}$/.test(handle)) notFound();
  if (!context.user) return <SignedOut next={profileHref(handle)} />;
  if (!context.me) redirect(COMMUNITY_HOME);

  const mine = context.me.handle === handle;
  const profile: Profile | null = mine ? context.me : await apiOrNull<Profile>(`/v1/community/profiles/${encodeURIComponent(handle)}`, { auth: true });
  if (!profile) notFound();

  const tab = mine ? pick((await searchParams).tab, TABS, "picks") : "picks";
  const base = profileHref(handle);
  const [picks, follows] = await Promise.all([
    tab === "picks" && !profile.is_blocked ? api<Schemas["PickPageOut"]>("/v1/community/picks", { auth: true, query: { handle, limit: PAGE_SIZE } }) : null,
    tab !== "picks" ? api<Schemas["FollowListOut"]>(`/v1/community/${tab}`, { auth: true }) : null,
  ]);

  return (
    <>
      <CommunityHeader
        title={`@${profile.handle}`}
        description={`Joined ${formatJoined(profile.joined)}`}
        current={mine ? "profile" : "pick"}
        me={context.me}
        leaderboard={context.leaderboard}
        actions={
          mine ? (
            <ButtonLink href="/app/community/settings" variant="secondary">
              Edit profile
            </ButtonLink>
          ) : null
        }
      />
      <div className="space-y-5">
        <Panel aria-labelledby="profile-about">
          <PanelHeader id="profile-about" title="About" />
          <div className="space-y-4 p-4 sm:p-5">
            {mine && !context.me.is_public ? <Notice tone="second">Your profile is private. Only you can see this page.</Notice> : null}
            {mine && context.me.moderation_status !== "visible" ? (
              <Notice tone="warn" title={context.me.moderation_note ?? "Removed by moderators."}>
                Other people can&rsquo;t see your profile. Changing the handle or the bio makes it visible again.
              </Notice>
            ) : null}
            {profile.bio ? <p className="max-w-prose whitespace-pre-line break-words">{profile.bio}</p> : <p className="text-sm text-muted">No bio.</p>}
            <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
              <div>
                <dt className="text-xs text-muted">Followers</dt>
                <dd className="num text-base font-medium">{profile.follower_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Following</dt>
                <dd className="num text-base font-medium">{profile.following_count}</dd>
              </div>
            </dl>
            {mine ? null : (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
                {profile.is_blocked ? null : <FollowButton key={String(profile.is_following)} handle={profile.handle} following={profile.is_following} />}
                <BlockButton handle={profile.handle} blocked={profile.is_blocked} />
                <ReportButton targetType="profile" targetId={profile.handle} what="this profile" />
              </div>
            )}
          </div>
        </Panel>

        {profile.is_blocked ? (
          <Notice tone="second" title="You blocked this profile">
            Its picks and comments are hidden from you, and yours are hidden from it. Unblock it to see them again. Unblocking does not restore a follow.
          </Notice>
        ) : (
          <>
            <Panel aria-labelledby="profile-record">
              <PanelHeader id="profile-record" title="Graded record" description={VERIFIED_NOTE} />
              <RecordPanel record={profile.record} />
            </Panel>

            {mine ? (
              <Segmented
                label="Profile lists"
                current={tab}
                options={[
                  { value: "picks", label: "Picks", href: base },
                  { value: "followers", label: countLabel(profile.follower_count, "follower", "followers"), href: `${base}?tab=followers` },
                  { value: "following", label: `${profile.following_count} following`, href: `${base}?tab=following` },
                ]}
              />
            ) : null}

            {picks ? (
              <Panel aria-labelledby="profile-picks">
                <PanelHeader id="profile-picks" title="Picks" description="Newest first. Picks can't be edited, and can't be deleted after the game starts." />
                <PickList
                  label={`Picks by @${profile.handle}`}
                  initial={picks.items}
                  next={picks.next_before ?? null}
                  path={`/v1/community/picks?handle=${encodeURIComponent(handle)}&limit=${PAGE_SIZE}`}
                  emptyTitle="No picks yet"
                  emptyBody={mine ? "Open an upcoming game to share your first pick." : undefined}
                />
              </Panel>
            ) : null}
            {follows && tab !== "picks" ? (
              <Panel aria-labelledby="profile-follows">
                <PanelHeader
                  id="profile-follows"
                  title={tab === "followers" ? "Followers" : "Following"}
                  description="Only you can see these lists. They include public, active profiles only."
                />
                <FollowList list={follows} kind={tab} />
              </Panel>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}
