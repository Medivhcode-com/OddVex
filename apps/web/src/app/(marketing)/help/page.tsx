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
  ["What does \"best price\" mean?", "The highest open price for an outcome among the books shown. Stale and suspended prices are excluded. On spreads and totals, prices are only compared at the same line."],
  ["What is no-vig probability?", "A book's two prices imply probabilities that add up to more than 100%. The extra is the book's margin. Removing it proportionally gives the no-vig, or fair, probability."],
  ["What is expected value?", "The average profit per dollar staked if your win probability were correct. It depends entirely on that probability, which OddVex does not supply for you."],
  ["Why does a hit rate show a range?", "Because a small sample can't pin down a true rate. The range is a 95% Wilson interval. A wider range means less evidence."],
  ["Why won't the parlay tool show a probability for some parlays?", "Legs from the same game are correlated, so multiplying their probabilities gives a wrong answer. OddVex shows the combined price and warns you instead."],
  ["How do I enter fractional or decimal odds?", "Pick the format next to the odds field when logging a bet or using a calculator. OddVex converts and stores the price exactly."],
  ["How do I delete my data?", "Settings, then Delete account. Your account, bets and any sync connections are removed immediately."],
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
