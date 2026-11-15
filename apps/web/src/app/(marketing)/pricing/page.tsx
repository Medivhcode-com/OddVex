import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/chrome";
import { ButtonLink, Notice, Panel } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Pricing",
  description: "OddVex is free during the preview. Paid plans have not launched and no payment details are collected.",
  alternates: { canonical: "/pricing" },
};

export default function Page() {
  return (
    <>
      <PageIntro
        title="Free while OddVex is in preview"
        lede="There is nothing to buy yet. Every tool in the preview is open, and we don't ask for a card."
      >
        <ButtonLink href="/signup" size="lg">
          Create a free account
        </ButtonLink>
      </PageIntro>
      <div className="mx-auto grid max-w-6xl gap-4 px-4 sm:px-6 md:grid-cols-2">
        <Panel className="p-6">
          <h2 className="text-lg font-semibold">Preview</h2>
          <p className="num mt-2 text-3xl font-medium">$0</p>
          <p className="mt-1 text-sm text-muted">No card, no trial clock.</p>
          <ul className="mt-5 list-disc space-y-1.5 pl-5 text-muted">
            <li>Games, odds comparison and line history</li>
            <li>Player prop analyzer and prop board</li>
            <li>All calculators and parlay research</li>
            <li>Bet tracker with performance breakdowns</li>
            <li>OddVex AI</li>
          </ul>
        </Panel>
        <Panel className="p-6">
          <h2 className="text-lg font-semibold">Premium</h2>
          <p className="mt-2 text-3xl font-medium text-muted">Not available yet</p>
          <p className="mt-1 text-sm text-muted">Pricing has not been set.</p>
          <p className="mt-5 text-muted">
            A paid plan is planned for heavier research: longer odds history, advanced prop filters, alerts and higher
            assistant limits. When it launches, the price, renewal terms and how to cancel will be shown here before you
            are asked to pay for anything.
          </p>
        </Panel>
      </div>
      <div className="mx-auto mt-6 max-w-6xl px-4 sm:px-6">
        <Notice title="Core research stays free">
          Comparing prices and tracking your own bets will remain available without paying.
        </Notice>
      </div>
    </>
  );
}
