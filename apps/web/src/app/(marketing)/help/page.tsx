import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/chrome";

export const metadata: Metadata = {
  title: "Help center",
  description: "Answers to common questions about OddVex.",
  alternates: { canonical: "/help" },
};

const FAQ: [string, string][] = [
  ["Does OddVex take bets?", "No. OddVex is a research and tracking tool. It never accepts, places or facilitates a wager and it doesn't hold money."],
  ["Is the data real?", "Not yet. The preview runs on synthetic data with fictional teams, players and sportsbooks, and the app says so on every screen. Licensed data will replace it before launch."],
  ["What does \"best price\" mean?", "The highest open price for an outcome among the books shown. Stale and suspended prices are excluded. During a game, a price last updated before the latest score change counts as stale. On spreads and totals, prices are only compared at the same line."],
  ["What is no-vig probability?", "A book's two prices imply probabilities that add up to more than 100%. The extra is the book's margin. Removing it proportionally gives the no-vig, or fair, probability."],
  ["What is expected value?", "The average profit per dollar staked if your win probability were correct. It depends entirely on that probability, which OddVex does not supply for you."],
  ["Why does a hit rate show a range?", "Because a small sample can't pin down a true rate. The range is a 95% Wilson interval. A wider range means less evidence."],
  ["Does the parlay tool show the chance that every leg wins?", "No. It shows the combined price, the payout and the break-even rate, which is how often the parlay has to win to break even at that price. It does not show a chance that every leg wins. Legs from the same game are correlated, so multiplying their probabilities gives a wrong answer; OddVex warns you when legs share a game. A fair price for a parlay, built from the no-vig prices of its legs, is planned and not built."],
  ["How do I enter fractional or decimal odds?", "Pick the format next to the odds field when logging a bet or using a calculator. OddVex converts and stores the price exactly."],
  ["How do alerts work?", "Open a game and choose Set an alert to watch a price, a line, the start or the final score. Alerts are checked when you open OddVex; nothing is sent by push or email. An alert that has fired shows up under Alerts inside OddVex."],
  ["What is the weekly staking reminder?", "A weekly amount you choose in Settings. If the stakes you log in a week reach it, OddVex tells you once. It is a reminder, not a limit: OddVex does not stop you logging bets and cannot stop a bet at a sportsbook."],
  ["How do I follow a team, player or game?", "Use the Follow button on a game or a player's props page. What you follow is saved to your account as a watchlist and appears on your home screen. Unfollow at any time to remove it."],
  ["How does settling from final scores work?", "A bet logged from a game screen is tied to that game. Once the game is final, choose Settle from final scores in the tracker and OddVex grades those bets from the score. Bets you typed in by hand, or that the score cannot decide, stay open for you to settle yourself. One run settles up to 200 bets; when open bets are left unchecked, the tracker says so and you can run it again."],
  ["How do I delete my data?", "Settings, then Delete account. Your account, bets, watchlist, alerts, notifications and sync connections are deleted from the live database as soon as the request completes. Security log entries are kept: they hold an internal account ID, the IP address and the detail of each action, such as the result of a bet or the ID of a team you followed, and the retention period is to be confirmed before launch. Backups made before the deletion still hold the account until they are removed. If you cannot sign in, write to the address on the contact page and staff can delete the account for you. The privacy policy has the full list."],
  ["Who can use OddVex?", "Adults 21 and over. You confirm this when you create an account."],
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
};

export default function Page() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <PageIntro title="Help center" lede="Short answers to the questions people ask most." />
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:mx-[max(1.5rem,calc((100vw-72rem)/2+1.5rem))]">
        <div className="divide-y divide-line border-y border-line">
          {FAQ.map(([question, answer]) => (
            <details key={question} className="group py-1">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 py-2 font-medium">
                {question}
                <span aria-hidden="true" className="num text-muted group-open:rotate-45 motion-safe:transition-transform">
                  +
                </span>
              </summary>
              <p className="pb-4 leading-relaxed text-muted">{answer}</p>
            </details>
          ))}
        </div>
      </div>
    </>
  );
}
