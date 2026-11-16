import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { Schemas } from "@oddvex/types";
import { Comments, DeletePickButton, ReportButton } from "@/components/app/community/actions";
import { CommunityHeader, SignedOut } from "@/components/app/community/chrome";
import { PickCard } from "@/components/app/community/pick-card";
import { Panel, PanelHeader } from "@/components/ui/primitives";
import { api, apiOrNull } from "@/lib/api";
import { COMMUNITY_HOME, communityContext, pickHref } from "@/lib/community";
import { VERIFIED_NOTE, type Pick } from "@/lib/community-copy";
import type { EventDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Pick" };

const ID = /^[A-Za-z0-9_-]{1,64}$/;

export default async function PickPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const context = await communityContext();
  if (!ID.test(id)) notFound();
  if (!context.user) return <SignedOut next={pickHref(id)} />;
  if (!context.me) redirect(COMMUNITY_HOME);

  const pick = await apiOrNull<Pick>(`/v1/community/picks/${encodeURIComponent(id)}`, { auth: true });
  if (!pick) notFound();
  const [comments, event] = await Promise.all([
    api<Schemas["CommentPageOut"]>(`/v1/community/picks/${encodeURIComponent(id)}/comments`, { auth: true, query: { limit: 20 } }),
    pick.is_mine && pick.status === "pending" ? apiOrNull<EventDetail>(`/v1/events/${encodeURIComponent(pick.event_id)}`).catch(() => null) : null,
  ]);
  // The API decides; this only chooses between offering the button and explaining the lock.
  const deletable = pick.is_mine && pick.status === "pending" && event?.status === "upcoming";

  return (
    <>
      <Link href={COMMUNITY_HOME} className="text-sm text-muted underline underline-offset-4 hover:text-ink">
        Community feed
      </Link>
      <div className="mt-3">
        <CommunityHeader title={`Pick by @${pick.author.handle}`} description={VERIFIED_NOTE} current="pick" me={context.me} leaderboard={context.leaderboard} />
      </div>
      <div className="max-w-3xl space-y-5">
        <Panel>
          <PickCard pick={pick} heading="h2" full />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-2 border-t border-line px-4 py-3 sm:px-5">
            {pick.is_mine ? <DeletePickButton pickId={pick.id} locked={!deletable} /> : <ReportButton targetType="pick" targetId={pick.id} what="this pick" />}
          </div>
        </Panel>
        <Panel aria-labelledby="comments" id="comments-panel">
          <PanelHeader id="comments" title="Comments" description="Newest first. Plain text only." />
          <Comments
            pickId={pick.id}
            initial={comments.items}
            next={comments.next_before ?? null}
            total={pick.comment_count}
            canPost={context.me.can_post && pick.moderation_status === "visible"}
            cannotPostReason={
              pick.moderation_status !== "visible"
                ? "Comments are closed on a pick that moderators removed."
                : "Your profile is private, so you can read comments but not add one. Make it public in the community settings to comment."
            }
            moderator={context.user.role === "admin"}
          />
        </Panel>
      </div>
    </>
  );
}
