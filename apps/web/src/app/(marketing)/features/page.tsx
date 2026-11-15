import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/chrome";
import { Badge, ButtonLink } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Features",
  description: "Everything in OddVex today and what is planned next: odds comparison, prop research, calculators, bet tracking and OddVex AI.",
  alternates: { canonical: "/features" },
};

const AREAS: { name: string; href?: string; live: boolean; body: string }[] = [
  { name: "Games and live scores", href: "/app/games", live: true, body: "Live, upcoming and final games by league with status, score and the best moneyline on each side." },
  { name: "Odds comparison", href: "/odds-comparison", live: true, body: "Moneyline, spread and total across books with best price, no-vig consensus, freshness and line history." },
  { name: "Player prop analyzer", href: "/player-props", live: true, body: "Game logs against the line, windows and splits, and hit rates with confidence ranges." },
  { name: "Calculators", href: "/app/tools", live: true, body: "Odds converter, no-vig, expected value and closing line value, each showing its working." },
  { name: "Parlay research", href: "/app/parlay", live: true, body: "Combined price and payout for any legs, with a warning when legs are correlated instead of a made-up probability." },
  { name: "Bet tracker", href: "/bet-tracking", live: true, body: "Log, settle and analyze bets with profit, ROI, closing line value and breakdowns." },
  { name: "OddVex AI", href: "/ai", live: true, body: "Answers from OddVex data tools with sources and freshness. Rule-based in this version." },
  { name: "Sportsbook sync", live: false, body: "The sync layer is built against a mock provider. Real connections need an authorized vendor." },
  { name: "Alerts and watchlists", live: false, body: "Line-move and price alerts on the markets you follow." },
  { name: "Community", live: false, body: "Profiles, public picks and leaderboards that separate verified results from self-reported ones." },
  { name: "Mobile apps", href: "/download", live: false, body: "iOS and Android apps are in development and not yet in the stores." },
];

export default function Page() {
  return (
    <>
      <PageIntro
        title="What's in OddVex, and what isn't yet"
        lede="The preview covers research, math and tracking end to end. Here is each part of the product and where it stands."
      >
        <ButtonLink href="/app" size="lg">
          Open the app
        </ButtonLink>
      </PageIntro>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <ul className="divide-y divide-line border-y border-line">
          {AREAS.map((area) => (
            <li key={area.name} className="grid gap-2 py-5 md:grid-cols-[16rem_1fr_auto] md:items-baseline md:gap-8">
              <h2 className="font-semibold">
                {area.href ? (
                  <Link href={area.href} className="underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                    {area.name}
                  </Link>
                ) : (
                  area.name
                )}
              </h2>
              <p className="max-w-prose text-muted">{area.body}</p>
              <Badge tone={area.live ? "accent" : "neutral"}>{area.live ? "In the preview" : "Planned"}</Badge>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
