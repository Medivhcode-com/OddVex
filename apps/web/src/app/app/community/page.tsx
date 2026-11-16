import type { Metadata } from "next";
import Link from "next/link";
import type { Schemas } from "@oddvex/types";
import { CommunityHeader, Guidelines, SignedOut } from "@/components/app/community/chrome";
import { PickList } from "@/components/app/community/pick-card";
import { ProfileForm } from "@/components/app/community/profile-form";
import { PageHeader } from "@/components/app/page-header";
import { Notice, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { communityContext, getGuidelines, PAGE_SIZE } from "@/lib/community";
import { VERIFIED_NOTE } from "@/lib/community-copy";
import { pick } from "@/lib/leagues";

export const metadata: Metadata = { title: "Community" };

const SCOPES = ["following", "everyone"] as const;

export default async function CommunityPage({ searchParams }: { searchParams: Promise<{ scope?: string; deleted?: string }> }) {
  const context = await communityContext();
  if (!context.user) return <SignedOut next="/app/community" />;

  // First visit: the guidelines, then the profile form. Nothing else until a profile exists.
  if (!context.me) {
    const guidelines = await getGuidelines();
    return (
      <>
        <PageHeader title="Community" description="Read the guidelines, then create a profile. A profile is opt-in and can stay private." />
        <div className="max-w-3xl space-y-5">
          <Panel aria-labelledby="guidelines-heading">
            <PanelHeader id="guidelines-heading" title="Community guidelines" description="These apply to every handle, bio, pick and comment." />
            <Guidelines guidelines={guidelines} />
          </Panel>
          <Panel aria-labelledby="create-profile-heading">
            <PanelHeader id="create-profile-heading" title="Create your profile" description="By creating a profile you agree to follow the guidelines above." />
            <ProfileForm mode="create" />
          </Panel>
        </div>
      </>
    );
  }

  const params = await searchParams;
  const scope = pick(params.scope, SCOPES, "following");
  const page = await api<Schemas["PickPageOut"]>("/v1/community/feed", { auth: true, query: { scope, limit: PAGE_SIZE } });

  return (
    <>
      <CommunityHeader
        title="Community"
        description="Picks from other people, newest first. Order is by time only, never by results or popularity."
        current="feed"
        me={context.me}
        leaderboard={context.leaderboard}
      />
      <div className="space-y-5">
        {params.deleted === "1" ? (
          <Notice tone="accent" role="status">
            Pick deleted.
          </Notice>
        ) : null}
        {context.me.can_post ? null : (
          <Notice tone="second" title={context.me.is_public ? "Your profile is hidden" : "Your profile is private"}>
            {context.me.is_public
              ? "Moderators hid your profile, so you can browse but can't post. Changing the handle or the bio makes it visible again. "
              : "You can browse, like and report. To post picks, comment or follow people, make your profile public. "}
            <Link href="/app/community/settings">Open community settings</Link>
          </Notice>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Segmented
            label="Feed scope"
            current={scope}
            options={[
              { value: "following", label: "Following", href: "/app/community" },
              { value: "everyone", label: "Everyone", href: "/app/community?scope=everyone" },
            ]}
          />
          {context.me.can_post ? (
            <p className="text-sm text-muted">
              To share a pick, open an upcoming game.{" "}
              <Link href="/app/games" className="text-ink underline underline-offset-4">
                Browse games
              </Link>
            </p>
          ) : null}
        </div>
        <Panel aria-labelledby="feed-heading">
          <PanelHeader id="feed-heading" title={scope === "following" ? "Picks from people you follow" : "Picks from everyone"} description={VERIFIED_NOTE} />
          <PickList
            key={scope}
            label={scope === "following" ? "Picks from people you follow" : "Picks from everyone"}
            initial={page.items}
            next={page.next_before ?? null}
            path={`/v1/community/feed?scope=${scope}&limit=${PAGE_SIZE}`}
            emptyTitle={scope === "following" ? "No picks from people you follow yet" : "No picks yet"}
            emptyBody={
              scope === "following"
                ? "Switch to Everyone to find profiles to follow. Picks from people you follow appear here."
                : "Nobody has shared a pick yet. Open an upcoming game to share the first one."
            }
          />
        </Panel>
        <p className="max-w-prose text-sm text-muted">
          A pick is one person&rsquo;s opinion about a game. It is not betting advice and not a prediction from OddVex. Sports betting involves risk of financial loss.
        </p>
      </div>
    </>
  );
}
