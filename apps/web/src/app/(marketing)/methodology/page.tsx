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
        <h2 id="edge-vs-consensus">Edge vs consensus</h2>
        <p>
          The value screen takes one outcome at a time. It finds the best price among books that are open, not stale
          and on the same line, then averages the no-vig probability of that outcome across the <em>other</em> books.
          The book with the best price is left out, because its own long price would pull the average towards the
          price being tested. At least two other books are required, or nothing is shown for that outcome.
        </p>
        <Formula>{`consensus  = mean of no_vig(outcome) over the other books
edge       = consensus × decimal_best − 1
break-even = 1 / decimal_best`}</Formula>
        <p>
          Example: book A offers 2.10, and books B and C have no-vig probabilities of 48.72% and 50.00% for the same
          outcome. The consensus is 49.36%, the break-even at 2.10 is 47.62%, and the edge is 0.49359 × 2.10 − 1 =
          +3.65%. That figure is the expected return per $1 staked <em>if the consensus were the true probability</em>.
          It often is not: the consensus is an average of a few books and can be wrong, the book with the best price
          may simply be slow to move, limits and availability differ by sportsbook, and prices change. A price above
          the consensus is not proof of an edge, and it is not a prediction. On the synthetic data in this preview
          every book is the same model plus a margin and noise, so no row reflects a real edge.
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
