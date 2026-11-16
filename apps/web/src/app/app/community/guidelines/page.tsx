import type { Metadata } from "next";
import { CommunityHeader, Guidelines } from "@/components/app/community/chrome";
import { Panel, PanelHeader } from "@/components/ui/primitives";
import { communityContext, getGuidelines } from "@/lib/community";

export const metadata: Metadata = { title: "Community guidelines" };

/** Readable without an account, like the API route behind it. */
export default async function CommunityGuidelinesPage() {
  const context = await communityContext();
  const guidelines = await getGuidelines();
  return (
    <>
      <CommunityHeader title="Community guidelines" current="guidelines" me={context.me} leaderboard={context.leaderboard} />
      <Panel aria-labelledby="guidelines-heading" className="max-w-3xl">
        <PanelHeader id="guidelines-heading" title="The rules" description="These apply to every handle, bio, pick and comment." />
        <Guidelines guidelines={guidelines} />
      </Panel>
    </>
  );
}
