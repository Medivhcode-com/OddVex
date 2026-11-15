import type { Metadata } from "next";
import { AssistantChat } from "@/components/app/assistant-chat";
import { PageHeader } from "@/components/app/page-header";
import { Panel } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { EventSummary, PropBoardRow } from "@/lib/types";

export const metadata: Metadata = { title: "OddVex AI" };

export default async function AssistantPage() {
  // Seed examples with names that exist in today's data so the first tap gets a real answer.
  const [events, props] = await Promise.all([
    api<EventSummary[]>("/v1/events", { query: { status: "upcoming" } }).catch(() => []),
    api<PropBoardRow[]>("/v1/props").catch(() => []),
  ]);
  const team = events[0]?.home_team.name;
  const prop = props[0];
  const examples = [
    team ? `Who has the best price on the ${team}?` : null,
    prop ? `How has ${prop.player.name} done on ${prop.market.replace(/_/g, " ")} lately?` : null,
    "What is expected value?",
    "How do you remove the vig?",
    "How are my bets doing?",
  ].filter((example): example is string => Boolean(example));

  return (
    <>
      <PageHeader
        title="OddVex AI"
        description="Answers come only from OddVex data and its calculation engine, with sources listed. It doesn't make picks or predict outcomes."
      />
      <Panel>
        <AssistantChat examples={examples} />
      </Panel>
    </>
  );
}
