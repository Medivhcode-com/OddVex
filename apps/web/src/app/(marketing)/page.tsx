import Link from "next/link";
import { SampleBoard } from "@/components/marketing/sample-board";
import { ButtonLink, Panel } from "@/components/ui/primitives";
import { Sparkline } from "@/components/ui/charts";
import { SITE } from "@/lib/site";

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: SITE.name,
  applicationCategory: "SportsApplication",
  operatingSystem: "Web, iOS, Android",
  description: SITE.description,
  url: SITE.url,
  publisher: { "@type": "Organization", name: SITE.company },
};

export default function HomePage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:gap-14 lg:pt-24">
        <div className="min-w-0">
          <h1 className="text-display font-semibold">
            Every line.
            <br />A smarter perspective.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            OddVex puts every sportsbook&rsquo;s price side by side, shows you what those prices imply once the vig is
            removed, and keeps an honest record of how your bets actually perform.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/app" size="lg">
              Open the app
            </ButtonLink>
            <ButtonLink href="/features" variant="secondary" size="lg">
              See how it works
            </ButtonLink>
          </div>
          <p className="mt-5 max-w-md text-sm text-muted">
            Research and analytics only. OddVex never takes a wager, and nothing on it is a guarantee. For adults 21+.
          </p>
        </div>
        <div className="min-w-0">
          <SampleBoard />
        </div>
      </section>

      <section aria-labelledby="why" className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[0.8fr_1.2fr]">
          <h2 id="why" className="text-title font-semibold">
            The same bet rarely costs the same twice.
          </h2>
          <div className="space-y-5 text-lg leading-relaxed text-muted">
            <p>
              Two books can post <span className="num text-ink">+136</span> and{" "}
              <span className="num text-ink">+142</span> on the same team in the same minute. Over a season that gap is
              the difference between a number you can live with and one you can&rsquo;t.
            </p>
            <p>
              Most tools bury that under picks and promos. OddVex shows the prices, how old each one is, and the math
              behind every figure, so you can check the work instead of trusting it.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="tools" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 id="tools" className="max-w-2xl text-title font-semibold">
          Four tools that share one set of numbers
        </h2>
        <div className="mt-10 grid gap-4 md:grid-cols-6">
          <Panel as="article" className="p-6 md:col-span-4">
            <h3 className="text-lg font-semibold">Odds comparison</h3>
            <p className="mt-2 max-w-lg text-muted">
              Moneylines, spreads and totals across books in one table. The best price is marked, suspended markets say
              so, and every price carries its age.
            </p>
            <dl className="mt-6 grid grid-cols-3 gap-4 border-t border-line pt-5 text-sm">
              {[
                ["Best price", "+142", "Cardinal"],
                ["Implied", "41.3%", "at +142"],
                ["No-vig", "40.4%", "market consensus"],
              ].map(([label, value, hint]) => (
                <div key={label}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="num mt-1 text-xl font-medium">{value}</dd>
                  <dd className="text-xs text-muted">{hint}</dd>
                </div>
              ))}
            </dl>
            <Link href="/odds-comparison" className="mt-6 inline-block text-sm font-medium underline underline-offset-4">
              How odds comparison works
            </Link>
          </Panel>

          <Panel as="article" className="p-6 md:col-span-2">
            <h3 className="text-lg font-semibold">Line movement</h3>
            <p className="mt-2 text-muted">See where a price opened, where it sits and which book moved first.</p>
            <div className="mt-6 flex items-end justify-between gap-3">
              <Sparkline
                values={[128, 128, 132, 130, 136, 140, 142]}
                width={150}
                height={48}
                tone="accent"
                summary="Sample line moving from +128 to +142 over two days"
              />
              <p className="num text-sm text-muted">
                +128 to <span className="text-ink">+142</span>
              </p>
            </div>
          </Panel>

          <Panel as="article" className="p-6 md:col-span-3">
            <h3 className="text-lg font-semibold">Player prop analyzer</h3>
            <p className="mt-2 text-muted">
              Game logs against the posted line: last 5, 10 or 20, home and away, against tonight&rsquo;s opponent. Hit
              rates come with their sample size and a confidence range, because seven of ten is not seventy percent.
            </p>
            <Link href="/player-props" className="mt-5 inline-block text-sm font-medium underline underline-offset-4">
              How prop research works
            </Link>
          </Panel>

          <Panel as="article" className="p-6 md:col-span-3">
            <h3 className="text-lg font-semibold">Bet tracker</h3>
            <p className="mt-2 text-muted">
              Log straight bets, parlays and futures in any odds format. OddVex settles the math and reports profit,
              ROI and closing line value by sport, market and book.
            </p>
            <Link href="/bet-tracking" className="mt-5 inline-block text-sm font-medium underline underline-offset-4">
              How tracking works
            </Link>
          </Panel>
        </div>
      </section>

      <section aria-labelledby="ai" className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 id="ai" className="text-title font-semibold">
              An assistant that shows its sources
            </h2>
            <p className="mt-4 max-w-lg text-lg leading-relaxed text-muted">
              Ask OddVex AI for the best price on a team, a player&rsquo;s recent form or what your tracker says about
              your parlays. It answers only from OddVex data, cites what it used and when that data was last updated,
              and says so when it doesn&rsquo;t know.
            </p>
            <ButtonLink href="/ai" variant="secondary" className="mt-6">
              What OddVex AI can do
            </ButtonLink>
          </div>
          <div className="rounded-panel border border-line bg-bg p-5">
            <p className="ml-auto w-fit max-w-[85%] rounded-panel rounded-br-sm bg-raised px-4 py-2.5 text-sm">
              Who has the best price on the Tides tonight?
            </p>
            <div className="mt-3 max-w-[92%] rounded-panel rounded-bl-sm border border-line bg-surface px-4 py-3 text-sm">
              <p>
                Cardinal has the best moneyline on the Harbor City Tides at <span className="num">+142</span>. Summit
                shows <span className="num">+130</span>, but that price is 9 minutes old.
              </p>
              <p className="mt-2 border-t border-line pt-2 text-xs text-muted">
                Source: odds comparison, updated 42s ago. Sample conversation with fictional data.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="principles" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 id="principles" className="max-w-2xl text-title font-semibold">
          What we won&rsquo;t do
        </h2>
        <ul className="mt-8 grid gap-x-10 gap-y-6 md:grid-cols-3">
          {[
            ["Promise wins", "No locks, no guaranteed picks, no invented accuracy figures. A historical hit rate is a record of the past."],
            ["Hide the math", "Every probability, edge and payout can be traced to a formula on the methodology page."],
            ["Pass off old prices", "A price without a timestamp is a rumor. Stale and suspended markets are labelled and left out of best-price marks."],
          ].map(([title, body]) => (
            <li key={title} className="border-t border-line-strong pt-4">
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-1.5 text-muted">{body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="rounded-panel border border-line bg-surface px-6 py-12 sm:px-12">
          <h2 className="max-w-xl text-title font-semibold">Look at tonight&rsquo;s board.</h2>
          <p className="mt-3 max-w-xl text-muted">
            The preview runs on synthetic data while licensed feeds are being arranged, and it is labelled that way
            everywhere. The tools and the math are the real thing.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <ButtonLink href="/app" size="lg">
              Open the app
            </ButtonLink>
            <ButtonLink href="/signup" variant="secondary" size="lg">
              Create an account
            </ButtonLink>
          </div>
        </div>
      </section>
    </>
  );
}
