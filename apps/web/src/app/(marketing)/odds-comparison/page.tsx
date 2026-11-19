import type { Metadata } from "next";
import { FeaturePage } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Odds comparison",
  description: "Compare moneylines, spreads and totals across sportsbooks, with the best price marked and every price timestamped.",
  alternates: { canonical: "/odds-comparison" },
};

export default function Page() {
  return (
    <FeaturePage
      copy={{
        title: "Compare every book's price in one table",
        lede: "Moneylines, spreads and totals side by side. The best available price is marked for each outcome, and you can see exactly how old each number is.",
        cta: { href: "/app/odds", label: "Open odds comparison" },
        points: [
          { title: "Best price, marked", body: "For each outcome OddVex marks the highest open price. On spreads and totals it compares like with like, so a better number at a different line is shown as a different line." },
          { title: "Implied and no-vig probability", body: "Each price is converted to the probability it implies. Then the book's margin is removed so you can see the market's own estimate, and each book's hold." },
          { title: "Freshness on every cell", body: "Prices carry the time they were last updated. Past a threshold they are labelled stale and no longer count toward best price or consensus." },
          { title: "Suspended and unavailable, said plainly", body: "If a book has pulled a market or doesn't offer it, the cell says so. An empty cell never means \"we don't know\"." },
          { title: "Line movement", body: "A history chart per market shows where each book opened and how it moved, with the best current price emphasized." },
          { title: "American or decimal", body: "Switch formats once and prices in the odds tables and boards follow. Fractional odds are accepted anywhere you type a price." },
        ],
        limits: [
          "The preview runs on synthetic data with fictional teams and sportsbooks. Licensed feeds have not been connected yet.",
          "A better price is not a reason to bet. It only means the same bet costs less.",
          "Sportsbook availability depends on where you are. OddVex does not verify your eligibility to bet with any book.",
        ],
      }}
    />
  );
}
