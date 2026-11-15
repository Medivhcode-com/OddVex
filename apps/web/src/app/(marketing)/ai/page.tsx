import type { Metadata } from "next";
import { FeaturePage } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "OddVex AI",
  description: "A sports research assistant that answers only from OddVex data and cites its sources and their freshness.",
  alternates: { canonical: "/ai" },
};

export default function Page() {
  return (
    <FeaturePage
      copy={{
        title: "Ask a question, get the numbers and where they came from",
        lede: "OddVex AI finds prices, explains the math and summarizes your tracker in plain English. It can only use OddVex's own data tools, and every answer lists what it used.",
        cta: { href: "/app/assistant", label: "Ask OddVex AI" },
        points: [
          { title: "Grounded in data tools", body: "A question is routed to a specific tool, such as odds comparison or your bet summary. The answer is written from that tool's output and nothing else." },
          { title: "Numbers are computed, never composed", body: "Probabilities, edges and payouts come from the same tested calculation engine the rest of the app uses. The language layer is not allowed to produce a figure." },
          { title: "Sources and freshness on every answer", body: "Each reply lists the data it used and when that data was last updated, so a stale answer is visible as stale." },
          { title: "It says when it doesn't know", body: "If no tool can answer, OddVex AI tells you and suggests where to look. It does not fill gaps with a guess." },
          { title: "What it can do today", body: "Find the best price for a team, explain expected value and no-vig odds, summarize a player's hit rate, describe line movement and summarize your tracked bets." },
          { title: "What comes later", body: "The current version uses rule-based routing and templated explanations. A language model for more natural conversation is planned behind the same guardrails." },
        ],
        limits: [
          "OddVex AI does not make picks and does not predict outcomes.",
          "It has no injury, lineup or news data in the preview and will not claim to.",
          "Answers about your bets require you to be logged in and only ever use your own data.",
        ],
      }}
    />
  );
}
