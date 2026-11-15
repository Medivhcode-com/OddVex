import type { Metadata } from "next";
import { PageIntro, Prose } from "@/components/marketing/chrome";

export const metadata: Metadata = {
  title: "Data sources and methodology",
  description: "Where OddVex data comes from and exactly how every probability, edge and payout is calculated.",
  alternates: { canonical: "/methodology" },
};

function Formula({ children }: { children: React.ReactNode }) {
  return <pre tabIndex={0} role="region" aria-label="Formula" className="num mb-4 max-w-full overflow-x-auto rounded-cell border border-line bg-surface px-4 py-3 text-sm text-ink">{children}</pre>;
}

export default function Page() {
  return (
    <>
      <PageIntro
        title="Data sources and methodology"
        lede="Every number in OddVex comes from one tested calculation engine. This page states the formulas so you can reproduce any of them by hand."
      />
      <Prose>
        <h2>Data sources</h2>
        <p>
          <strong>The preview uses synthetic data.</strong> Teams, players, sportsbooks, prices, scores and game logs are
          generated for testing and are fictional. No licensed odds or statistics provider is connected. When one is,
          this page will name it and each screen will show the source and time of its data.
        </p>
        <h2>Freshness</h2>
        <p>
          Each price records when it was last updated. A price older than 2 minutes for a live game, or 15 minutes
          before a game starts, is labelled stale. Stale and suspended prices are excluded from best-price marks and
          from the consensus.
        </p>
        <h2>Odds conversion</h2>
        <Formula>{`decimal = 1 + american / 100        (american > 0)
decimal = 1 + 100 / |american|      (american < 0)
implied probability = 1 / decimal`}</Formula>
        <h2>No-vig probability</h2>
        <p>
          The implied probabilities of all outcomes in a market sum to more than 1. The excess is the overround. OddVex
          removes it proportionally:
        </p>
        <Formula>{`overround = sum(implied_i) - 1
no_vig_i  = implied_i / sum(implied_i)`}</Formula>
        <p>
          Example: both sides at −110 imply 52.38% each, an overround of 4.76%, and a no-vig probability of 50% each.
          The proportional method is simple and widely used. Other methods exist and can differ slightly on lopsided
          markets. The consensus shown in odds comparison is the average of each open, non-stale book&rsquo;s no-vig
          probability.
        </p>
        <h2>Expected value</h2>
        <Formula>{`EV per $1 staked = p × (decimal − 1) − (1 − p)`}</Formula>
        <p>
          Example: +150 with a 45% chance of winning gives 0.45 × 1.5 − 0.55 = +0.125, or +12.5%. The result is only as
          good as the probability <em>p</em> you supply. A positive number is not evidence that an edge exists.
        </p>
        <h2>Closing line value</h2>
        <Formula>{`CLV = decimal_taken / decimal_closing − 1`}</Formula>
        <p>Positive means you took a better price than the market closed at.</p>
        <h2>Hit rates</h2>
        <p>
          A hit rate is the share of games in the chosen window where the player finished over the line. Pushes are
          excluded from the count. It is shown with a 95% Wilson score interval, which behaves sensibly for small
          samples. A hit rate is a historical record and not a forecast.
        </p>
        <h2>Parlays</h2>
        <p>
          The combined price of a parlay is the product of its legs&rsquo; decimal odds, with pushed or voided legs
          removed. A combined probability is only shown when every leg is from a different event, and it is labelled as
          assuming independence. For legs from the same event OddVex shows a correlation warning and no probability,
          because multiplying dependent probabilities gives a wrong answer.
        </p>
        <h2>Settlement</h2>
        <p>
          Won returns stake × decimal. Lost returns nothing. Push and void return the stake. Half won and half lost
          settle half the stake each way. Cash-out records the amount you received.
        </p>
        <h2>What OddVex does not do</h2>
        <p>
          OddVex does not publish model projections or win probabilities of its own in this version. When it does, each
          model will ship with its method, test results, calibration and limits.
        </p>
      </Prose>
    </>
  );
}
